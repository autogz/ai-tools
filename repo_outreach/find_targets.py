#!/usr/bin/env python3
"""
find_targets.py — Scans GitHub API for Python repos matching our target profile.

Filters:
  - Language: Python
  - Pushed in last 30 days
  - Stars: 0–100
  - Has README but weak (< 200 lines in README)
  - No GitHub Actions / .github/workflows
  - Excludes: security tools, adult, gambling, crypto scams, finance promises

Outputs top 10 targets per day to stdout + JSON cache.
"""

import json
import os
import sys
import time
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

BASE_DIR = Path("/root/.ai-growth/repo_outreach")
CACHE_FILE = BASE_DIR / "targets_cache.json"
LOG_FILE = BASE_DIR / "find_targets_log.jsonl"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"

EXCLUDE_KEYWORDS = [
    # Security tools
    "penetration test", "penetration-test", "pentest", "vulnerability scanner",
    "exploit", "cve", "zero-day", "ransomware", "keylogger", "backdoor",
    "malware", "trojan", "spyware",
    # Adult
    "adult", "porn", "nsfw", "xxx", "sex", "onlyfans",
    # Gambling
    "gambling", "casino", "poker", "betting", "blackjack", "slot",
    # Crypto scams / finance promises
    "crypto bot", "trading bot", "arbitrage", "pump and dump", "pump-n-dump",
    "get rich", "passive income", "make money fast", "guaranteed profit",
    "investment advice", "financial advisor", "forex", "binary options",
    "crypto signal", "rug pull", "moon", "lambo", "100x",
]

# Common good README sections that indicate quality
GOOD_SECTIONS = {"installation", "install", "usage", "example", "examples",
                 "getting started", "quickstart", "quick start", "setup",
                 "configuration", "config", "api", "documentation", "docs",
                 "contributing", "contributor", "license", "changelog"}


def _api_get(path: str, params: str = "") -> dict:
    """Make an authenticated GitHub API GET request."""
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
            data = json.loads(resp.read().decode())
            # Handle rate limit info
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            reset_ts = int(resp.headers.get("X-RateLimit-Reset", "0"))
            reset_time = datetime.fromtimestamp(reset_ts, tz=timezone.utc)
            if int(remaining) < 5:
                print(f"[WARN] Rate limit low: {remaining} remaining, resets at {reset_time}",
                      file=sys.stderr)
            return data
    except HTTPError as e:
        if e.code == 403:
            body = e.read().decode()
            print(f"[WARN] Rate limited or forbidden: {body[:200]}", file=sys.stderr)
            return {"error": "rate_limited", "message": body[:200]}
        if e.code == 422:
            body = e.read().decode()
            print(f"[WARN] Validation error: {body[:200]}", file=sys.stderr)
            return {"error": "validation", "message": body[:200]}
        raise


def _get_readme(full_name: str) -> str | None:
    """Fetch README content for a repo. Returns text or None."""
    try:
        data = _api_get(f"/repos/{full_name}/readme")
        if "content" in data and data.get("encoding") == "base64":
            import base64
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        pass
    return None


def _check_github_actions(full_name: str) -> bool:
    """Check if repo has GitHub Actions workflows."""
    try:
        data = _api_get(f"/repos/{full_name}/actions/workflows")
        if isinstance(data, dict) and data.get("total_count", 0) > 0:
            return True
    except Exception:
        pass
    return False


def _check_dot_github_workflows(full_name: str) -> bool:
    """Check if .github/workflows directory exists."""
    try:
        data = _api_get(f"/repos/{full_name}/contents/.github/workflows")
        if isinstance(data, list) and len(data) > 0:
            return True
    except Exception:
        pass
    return False


def _excluded_by_topic(repo: dict) -> bool:
    """Check if repo topics or description contain excluded keywords."""
    text = f"{repo.get('description', '')} {' '.join(repo.get('topics', []))} {repo.get('name', '')}"
    text_lower = text.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def _evaluate_readme(readme_text: str | None) -> dict:
    """Score a README — returns dict with length, sections, quality."""
    if not readme_text:
        return {"has_readme": False, "length": 0, "line_count": 0, "sections_found": [], "weak": True}

    lines = readme_text.splitlines()
    line_count = len(lines)
    length = len(readme_text)

    # Find sections (markdown headings)
    sections_found = set()
    for line in lines:
        m = re.match(r'^#+\s+(.+?)\s*$', line.strip())
        if m:
            section_name = m.group(1).lower().strip()
            if section_name in GOOD_SECTIONS:
                sections_found.add(section_name)

    is_weak = length < 2000 and line_count < 200

    return {
        "has_readme": True,
        "length": length,
        "line_count": line_count,
        "sections_found": sorted(sections_found),
        "weak": is_weak,
    }


def search_python_repos(query_date: str | None = None) -> list[dict]:
    """
    Search GitHub for Python repos matching initial criteria.
    Returns list of raw repo dicts.
    """
    # Build query: Python, push date in last 30 days, stars 0-100
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    query = f"language:python pushed:>={since} stars:0..100"

    params = (
        f"q={query.replace(' ', '+')}"
        f"&sort=updated"
        f"&order=desc"
        f"&per_page=100"
        f"&page=1"
    )

    data = _api_get("/search/repositories", params)
    if "error" in data:
        print(f"[ERROR] Search failed: {data.get('message', 'unknown')}", file=sys.stderr)
        return []

    items = data.get("items", [])
    print(f"[INFO] Found {data.get('total_count', 0)} potential targets, checking page of {len(items)}",
          file=sys.stderr)
    return items


def filter_targets(repos: list[dict]) -> list[dict]:
    """
    Apply detailed filters to repos. Returns list of qualified targets
    with evaluation metadata.
    """
    targets = []
    checked = 0

    for repo in repos:
        checked += 1
        full_name = repo["full_name"]
        print(f"[INFO] Checking {checked}/{len(repos)}: {full_name}", file=sys.stderr)

        # Skip excluded categories
        if _excluded_by_topic(repo):
            print(f"  └ SKIP: excluded topic/description", file=sys.stderr)
            continue

        # Fetch readme
        readme_text = _get_readme(full_name)
        readme_eval = _evaluate_readme(readme_text)

        if not readme_eval["has_readme"]:
            print(f"  └ SKIP: no README", file=sys.stderr)
            continue

        if not readme_eval["weak"]:
            print(f"  └ SKIP: README too strong ({readme_eval['line_count']} lines)", file=sys.stderr)
            continue

        # Check GitHub Actions
        has_ci = _check_github_actions(full_name)
        if has_ci:
            print(f"  └ SKIP: has GitHub Actions", file=sys.stderr)
            continue

        has_workflows_dir = _check_dot_github_workflows(full_name)
        if has_workflows_dir:
            print(f"  └ SKIP: has .github/workflows", file=sys.stderr)
            continue

        # Also check for basic CI files
        has_ci_files = False
        try:
            ci_files = _api_get(f"/repos/{full_name}/contents")
            if isinstance(ci_files, list):
                names = {f["name"] for f in ci_files if isinstance(f, dict)}
                ci_patterns = {".travis.yml", "circle.yml", ".circleci", "Jenkinsfile",
                               ".github", "Makefile", "tox.ini", "setup.py", "setup.cfg",
                               "pyproject.toml", "noxfile.py"}
                if names & ci_patterns:
                    # Has some build config — not a dealbreaker but notable
                    has_ci_files = True
        except Exception:
            pass

        target = {
            "full_name": full_name,
            "name": repo["name"],
            "owner": repo["owner"]["login"],
            "html_url": repo["html_url"],
            "description": repo.get("description", ""),
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "open_issues": repo["open_issues_count"],
            "language": repo.get("language", "Python"),
            "pushed_at": repo["pushed_at"],
            "created_at": repo["created_at"],
            "topics": repo.get("topics", []),
            "has_ci_files": has_ci_files,
            "readme": readme_eval,
            "score": None,  # To be filled by repo_scorer
            "selected_at": datetime.now(timezone.utc).isoformat(),
        }
        targets.append(target)
        print(f"  └ ACCEPT: {full_name} ({readme_eval['line_count']} README lines, {repo['stargazers_count']} stars)", file=sys.stderr)

        # Small delay to avoid rate limiting
        time.sleep(0.3)

    return targets


def save_cache(targets: list[dict]) -> None:
    """Save today's targets to cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(targets),
        "targets": targets,
    }
    CACHE_FILE.write_text(json.dumps(data, indent=2, default=str))
    print(f"[INFO] Cache saved: {CACHE_FILE}", file=sys.stderr)


def log_find(targets: list[dict]) -> None:
    """Log finding session to JSONL."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "targets_found": len(targets),
        "repos": [t["full_name"] for t in targets],
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    """Main entry point."""
    targets = search_python_repos()
    qualified = filter_targets(targets)

    # Sort by stars (fewer stars = more in need of help)
    qualified.sort(key=lambda r: r["stars"])

    # Take top 10
    top = qualified[:10]

    print("\n" + "=" * 60)
    print(f"TOP {len(top)} TARGETS FOR TODAY:")
    print("=" * 60)

    for i, t in enumerate(top, 1):
        print(f"\n{i}. {t['full_name']}")
        print(f"   URL:    {t['html_url']}")
        print(f"   Stars:  {t['stars']}  |  Forks: {t['forks']}  |  Issues: {t['open_issues']}")
        print(f"   README: {t['readme']['line_count']} lines, {len(t['readme']['sections_found'])} sections")
        if t['readme']['sections_found']:
            print(f"   Sections: {', '.join(t['readme']['sections_found'])}")
        print(f"   Desc:   {t['description'][:80] if t['description'] else '(none)'}")
        print(f"   Pushed: {t['pushed_at'][:10]}")

    save_cache(top)
    log_find(top)

    print(f"\n[OK] Found {len(top)} targets. Cache saved to {CACHE_FILE}")


if __name__ == "__main__":
    main()
