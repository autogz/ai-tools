#!/usr/bin/env python3
"""
repo_scorer.py — Scores a repo on "launch readiness".

Scoring dimensions (each 0-20, total 1-100):
1. README quality (length + sections)
2. Documentation files present (LICENSE, SECURITY, CONTRIBUTING)
3. CI presence
4. PyPI presence
5. Screenshot/media presence

Usage:
  python repo_scorer.py <github_url_or_full_name>
  python repo_scorer.py --batch <file_with_repo_list>
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

BASE_DIR = Path("/root/.ai-growth/repo_outreach")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
PYPI_API = "https://pypi.org/pypi"

GOOD_SECTIONS = {"installation", "install", "usage", "example", "examples",
                 "getting started", "quickstart", "quick start", "setup",
                 "configuration", "config", "api", "documentation", "docs",
                 "contributing", "contributor", "license", "changelog",
                 "features", "why", "motivation", "status", "roadmap"}

REQUIRED_DOCS = {"LICENSE", "LICENSE.md", "LICENSE.txt",
                 "SECURITY", "SECURITY.md", "SECURITY.txt",
                 "CONTRIBUTING", "CONTRIBUTING.md", "CONTRIBUTING.txt"}


def _api_get(path: str, params: str = "") -> dict | list:
    """GitHub API GET."""
    url = f"{GITHUB_API}{path}"
    if params:
        url += f"?{params}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ai-tools-outreach/1.0",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        if e.code in (403, 404):
            return {}
        raise


def _parse_repo_ident(repo_input: str) -> tuple[str, str] | None:
    """Parse 'owner/repo' or full URL into (owner, repo)."""
    m = re.match(r'https?://github\.com/([^/]+)/([^/\s?#]+)', repo_input)
    if m:
        return m.group(1), m.group(2).replace(".git", "")
    m = re.match(r'^([\w.-]+)/([\w.-]+)$', repo_input)
    if m:
        return m.group(1), m.group(2)
    return None


def _get_readme(owner: str, repo: str) -> str | None:
    """Fetch README text."""
    try:
        data = _api_get(f"/repos/{owner}/{repo}/readme")
        if isinstance(data, dict) and "content" in data and data.get("encoding") == "base64":
            import base64
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        pass
    return None


def _get_repo_contents(owner: str, repo: str, path: str = "") -> list[dict]:
    """Fetch directory listing."""
    try:
        data = _api_get(f"/repos/{owner}/{repo}/contents/{path}")
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _check_pypi(package_name: str) -> dict:
    """Check if package exists on PyPI. Returns info dict."""
    try:
        req = Request(
            f"{PYPI_API}/{package_name}/json",
            headers={"User-Agent": "ai-tools-outreach/1.0"},
        )
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            info = data.get("info", {})
            return {
                "exists": True,
                "name": info.get("name", package_name),
                "version": info.get("version", "?"),
                "summary": info.get("summary", ""),
            }
    except HTTPError:
        pass
    except Exception:
        pass
    return {"exists": False, "name": package_name, "version": None, "summary": ""}


def _score_readme_quality(readme_text: str | None) -> tuple[int, dict]:
    """
    Score README quality (0-20).
    Criteria: length, section coverage, content depth.
    """
    if not readme_text:
        return 0, {"score": 0, "reason": "No README found"}

    lines = readme_text.splitlines()
    line_count = len(lines)
    text_len = len(readme_text)
    details = {"line_count": line_count, "char_count": text_len}

    # Length score (0-8)
    if line_count >= 150:
        length_score = 8
        details["length_rating"] = "excellent"
    elif line_count >= 80:
        length_score = 6
        details["length_rating"] = "good"
    elif line_count >= 30:
        length_score = 4
        details["length_rating"] = "adequate"
    elif line_count >= 10:
        length_score = 2
        details["length_rating"] = "minimal"
    else:
        length_score = 1
        details["length_rating"] = "tiny"

    # Sections score (0-8)
    sections_found = set()
    for line in lines:
        m = re.match(r'^#+\s+(.+?)\s*$', line.strip())
        if m:
            section_name = m.group(1).lower().strip()
            if section_name in GOOD_SECTIONS:
                sections_found.add(section_name)

    num_sections = len(sections_found)
    if num_sections >= 6:
        section_score = 8
    elif num_sections >= 4:
        section_score = 6
    elif num_sections >= 2:
        section_score = 4
    elif num_sections >= 1:
        section_score = 2
    else:
        section_score = 0
    details["sections_found"] = sorted(sections_found)
    details["sections_score"] = section_score

    # Code blocks / examples score (0-4)
    code_blocks = len(re.findall(r'```', readme_text)) // 2
    if code_blocks >= 5:
        example_score = 4
    elif code_blocks >= 3:
        example_score = 3
    elif code_blocks >= 1:
        example_score = 2
    else:
        example_score = 0
    details["code_blocks"] = code_blocks
    details["example_score"] = example_score

    total = length_score + section_score + example_score
    details["total"] = total
    return total, details


def _score_doc_files(owner: str, repo: str) -> tuple[int, dict]:
    """Check for documentation files (0-20)."""
    contents = _get_repo_contents(owner, repo)
    filenames = {f["name"] for f in contents if isinstance(f, dict)} if contents else set()

    found_docs = []
    for fname in filenames:
        for pattern in REQUIRED_DOCS:
            if fname.lower() == pattern.lower() or fname == pattern:
                found_docs.append(fname)

    # Also check docs/ directory
    has_docs_dir = any(
        isinstance(f, dict) and f.get("type") == "dir" and f["name"] in ("docs", "documentation")
        for f in contents or []
    )
    if has_docs_dir:
        found_docs.append("docs/")

    score = min(20, len(found_docs) * 7)  # ~7 points each, max 20
    return score, {"found": found_docs, "score": score}


def _score_ci(owner: str, repo: str) -> tuple[int, dict]:
    """Check for CI/CD setup (0-20)."""
    details = {"has_github_actions": False, "has_other_ci": False, "has_build_config": False}
    score = 0

    # Check GitHub Actions
    try:
        data = _api_get(f"/repos/{owner}/{repo}/actions/workflows")
        if isinstance(data, dict) and data.get("total_count", 0) > 0:
            details["has_github_actions"] = True
            score += 10
    except Exception:
        pass

    # Check common CI files in root
    contents = _get_repo_contents(owner, repo)
    filenames = {f["name"].lower() for f in contents if isinstance(f, dict)} if contents else set()
    ci_files = {
        ".travis.yml": "travis",
        "circle.yml": "circleci",
        ".circleci": "circleci",
        "jenkinsfile": "jenkins",
        "appveyor.yml": "appveyor",
        ".gitlab-ci.yml": "gitlab",
    }
    for cf, ci_name in ci_files.items():
        if cf in filenames:
            details[f"has_{ci_name}"] = True
            score += 6

    # Build configs (moderate signal)
    build_files = {"setup.py", "setup.cfg", "pyproject.toml", "makefile", "tox.ini", "noxfile.py"}
    detected_build = filenames & build_files
    if detected_build:
        details["has_build_config"] = True
        details["build_files"] = list(detected_build)
        score += 4

    details["score"] = min(20, score)
    return min(20, score), details


def _score_pypi(package_name: str) -> tuple[int, dict]:
    """Check PyPI presence (0-20)."""
    info = _check_pypi(package_name)
    if info["exists"]:
        version = info.get("version", "0.0.0")
        parts = [int(p) for p in version.split(".") if p.isdigit()]
        version_maturity = parts[0] if parts else 0
        if version_maturity >= 1:
            return 20, {"exists": True, "version": version, "maturity": "stable"}
        else:
            return 15, {"exists": True, "version": version, "maturity": "pre-release"}
    # Also try with dashes/underscores
    alt_name = package_name.replace("_", "-").replace("-", "_")
    if alt_name != package_name:
        alt_info = _check_pypi(alt_name)
        if alt_info["exists"]:
            version = alt_info.get("version", "0.0.0")
            parts = [int(p) for p in version.split(".") if p.isdigit()]
            version_maturity = parts[0] if parts else 0
            if version_maturity >= 1:
                return 18, {"exists": True, "as": alt_name, "version": version, "maturity": "stable"}
            else:
                return 13, {"exists": True, "as": alt_name, "version": version, "maturity": "pre-release"}
    return 0, {"exists": False, "tried": [package_name, alt_name]}


def _score_screenshots(owner: str, repo: str, readme_text: str | None) -> tuple[int, dict]:
    """Check for screenshots/images in repo (0-20)."""
    score = 0
    details = {}

    # Check README for image links
    if readme_text:
        img_patterns = [
            r'!\[.*?\]\(.*?\.(png|jpg|jpeg|gif|svg|webp)\)',
            r'<img\s+[^>]*src=',
            r'!\[.*?\]\(.*?\)',  # Any image markdown
        ]
        total_images = 0
        for pat in img_patterns:
            found = re.findall(pat, readme_text, re.IGNORECASE)
            total_images += len(found)

        if total_images >= 4:
            score += 10
            details["images_in_readme"] = total_images
        elif total_images >= 2:
            score += 7
            details["images_in_readme"] = total_images
        elif total_images >= 1:
            score += 4
            details["images_in_readme"] = total_images

    # Check for assets/, screenshots/, images/ directories
    try:
        contents = _api_get(f"/repos/{owner}/{repo}/contents")
        if isinstance(contents, list):
            dirs = {f["name"] for f in contents if isinstance(f, dict) and f.get("type") == "dir"}
            media_dirs = dirs & {"assets", "screenshots", "images", "media", "img", "demo"}
            if media_dirs:
                details["media_dirs"] = list(media_dirs)
                score += 6
    except Exception:
        pass

    # Check for GIF in README (highly valuable)
    if readme_text and re.search(r'\.gif\)', readme_text, re.IGNORECASE):
        score += 4
        details["has_gif"] = True

    details["score"] = min(20, score)
    return min(20, score), details


def score_repo(repo_input: str) -> dict:
    """
    Full scoring pipeline for a single repo.
    Returns dict with overall score and dimension breakdown.
    """
    parsed = _parse_repo_ident(repo_input)
    if not parsed:
        return {"error": f"Invalid repo input: {repo_input}", "score": 0}
    owner, repo = parsed

    print(f"[INFO] Scoring {owner}/{repo}...", file=sys.stderr)

    readme_text = _get_readme(owner, repo)
    time.sleep(0.2)

    # Score each dimension
    readme_score, readme_details = _score_readme_quality(readme_text)
    time.sleep(0.2)
    doc_score, doc_details = _score_doc_files(owner, repo)
    time.sleep(0.2)
    ci_score, ci_details = _score_ci(owner, repo)
    time.sleep(0.2)
    pypi_score, pypi_details = _score_pypi(repo)
    time.sleep(0.2)
    screenshot_score, screenshot_details = _score_screenshots(owner, repo, readme_text)

    total = readme_score + doc_score + ci_score + pypi_score + screenshot_score
    # Ensure 1-100 range
    total = max(1, min(100, total))

    result = {
        "repo": f"{owner}/{repo}",
        "url": f"https://github.com/{owner}/{repo}",
        "score": total,
        "dimensions": {
            "readme_quality": {"score": readme_score, "max": 20, "details": readme_details},
            "documentation_files": {"score": doc_score, "max": 20, "details": doc_details},
            "ci_presence": {"score": ci_score, "max": 20, "details": ci_details},
            "pypi_presence": {"score": pypi_score, "max": 20, "details": pypi_details},
            "screenshots_media": {"score": screenshot_score, "max": 20, "details": screenshot_details},
        },
        "readiness_level": (
            "Excellent" if total >= 80 else
            "Good" if total >= 60 else
            "Fair" if total >= 40 else
            "Poor" if total >= 20 else
            "Needs Work"
        ),
        "scored_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    print(f"[OK] {owner}/{repo} → Score: {total}/100 ({result['readiness_level']})", file=sys.stderr)
    return result


def batch_score(file_path: str) -> list[dict]:
    """Score all repos listed in a file (one per line)."""
    with open(file_path) as f:
        repos = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    results = []
    for r in repos:
        results.append(score_repo(r))
        time.sleep(0.5)
    return results


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: python repo_scorer.py <github_url_or_full_name>")
        print("   or: python repo_scorer.py --batch <file>")
        sys.exit(1)

    if args[0] == "--batch" and len(args) >= 2:
        results = batch_score(args[1])
    else:
        results = [score_repo(args[0])]

    print("\n" + "=" * 60)
    print("SCORING RESULTS:")
    print("=" * 60)
    for r in results:
        if "error" in r:
            print(f"  ERROR: {r['error']}")
            continue
        print(f"\n  Repo:  {r['repo']}")
        print(f"  Score: {r['score']}/100 — {r['readiness_level']}")
        for dim, info in r["dimensions"].items():
            bar = "█" * (info["score"] // 2) + "░" * ((20 - info["score"]) // 2)
            print(f"    {dim:25s} {info['score']:2d}/20 {bar}")
        print(f"  URL:   {r['url']}")

    # Save results
    out_path = BASE_DIR / "scoring_results.json"
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n[OK] Results saved to {out_path}")


if __name__ == "__main__":
    main()
