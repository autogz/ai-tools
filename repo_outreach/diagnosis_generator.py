#!/usr/bin/env python3
"""
diagnosis_generator.py — For a given repo URL, generates a diagnosis report
with 5 specific improvement suggestions, estimates effort, and recommends
'aitools launch .' command.

Saves to: /root/.ai-growth/repo_outreach/diagnoses/{repo_name}.md

Usage:
  python diagnosis_generator.py <github_url_or_full_name>
  python diagnosis_generator.py --from-cache
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

BASE_DIR = Path("/root/.ai-growth/repo_outreach")
DIAGNOSES_DIR = BASE_DIR / "diagnoses"
CACHE_FILE = BASE_DIR / "targets_cache.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://github.com"

IMPROVEMENT_TEMPLATES = {
    "readme_structure": {
        "title": "Restructure README with standard sections",
        "description": "Your README has content but lacks standard sections like Installation, Usage, API, and Contributing. A well-structured README helps users understand your project in seconds.",
        "effort": "Low (15-30 min)",
        "impact": "High",
        "tools": ["aitools launch .", "markdown formatter"],
    },
    "add_license": {
        "title": "Add a LICENSE file",
        "description": "Your repo has no license file. Without one, other developers cannot legally use or contribute to your project. Adding an MIT or Apache 2.0 license takes 2 minutes and signals trust.",
        "effort": "Minimal (5 min)",
        "impact": "High",
        "tools": ["aitools launch ."],
    },
    "add_security_policy": {
        "title": "Add SECURITY.md policy",
        "description": "A SECURITY.md file tells users and researchers how to report vulnerabilities responsibly. Essential for any public repo that accepts contributions.",
        "effort": "Minimal (10 min)",
        "impact": "Medium",
        "tools": ["aitools launch ."],
    },
    "add_contributing_guide": {
        "title": "Create CONTRIBUTING.md guide",
        "description": "A contributing guide sets expectations for PRs, coding style, and testing. Even for small projects, it reduces friction for new contributors.",
        "effort": "Low (15 min)",
        "impact": "Medium",
        "tools": ["aitools launch ."],
    },
    "setup_ci": {
        "title": "Set up GitHub Actions CI",
        "description": "Your repo has no CI/CD pipeline. Adding automated testing via GitHub Actions catches regressions early and builds trust with users and contributors.",
        "effort": "Medium (30-60 min)",
        "impact": "High",
        "tools": ["aitools launch ."],
    },
    "add_examples": {
        "title": "Add code examples and a demo GIF",
        "description": "Your README lacks runnable examples or a demo screenshot. A quick-start section with 2-3 examples and a GIF showing the tool in action dramatically improves conversion.",
        "effort": "Low (20-40 min)",
        "impact": "High",
        "tools": ["aitools launch ."],
    },
    "pypi_package": {
        "title": "Publish to PyPI for pip install",
        "description": "Your project is not on PyPI. Users expect 'pip install your-package'. Publishing takes ~30 min with proper setup.py/pyproject.toml and makes adoption frictionless.",
        "effort": "Low (30 min)",
        "impact": "Very High",
        "tools": ["aitools launch ."],
    },
    "badges": {
        "title": "Add status badges to README",
        "description": "Your README lacks badges for PyPI version, license, Python versions, or build status. Badges are visual trust signals that instantly communicate project health.",
        "effort": "Minimal (10 min)",
        "impact": "Medium",
        "tools": ["aitools launch ."],
    },
    "issue_templates": {
        "title": "Add GitHub issue templates",
        "description": "Issue templates (bug report, feature request) help users file structured feedback. This reduces noise and makes it easier to triage incoming issues.",
        "effort": "Low (15 min)",
        "impact": "Low",
        "tools": ["aitools launch ."],
    },
    "changelog": {
        "title": "Create a CHANGELOG.md",
        "description": "A changelog tracks what changed between versions. Users and maintainers rely on this to understand updates. Essential before any public release.",
        "effort": "Low (15 min)",
        "impact": "Medium",
        "tools": ["aitools launch ."],
    },
    "config_auto": {
        "title": "Add auto-configuration support",
        "description": "Tools like 'aitools launch .' can auto-generate README sections, CI config, license files, badges, and more from your existing codebase — saving hours of manual work.",
        "effort": "Minimal (run the command)",
        "impact": "Very High",
        "tools": ["aitools launch ."],
    },
    "code_quality": {
        "title": "Add code quality tools (linter + formatter)",
        "description": "Your repo would benefit from automated code quality checks. Adding ruff or black + pre-commit hooks ensures consistent code style and catches bugs early.",
        "effort": "Low (20 min)",
        "impact": "Medium",
        "tools": ["aitools launch ."],
    },
    "tests_setup": {
        "title": "Add automated tests",
        "description": "Your repo has minimal or no tests. Adding pytest tests is the single best investment for long-term maintainability and user trust.",
        "effort": "Medium (1-2 hours)",
        "impact": "Very High",
        "tools": ["aitools launch ."],
    },
    "screenshot": {
        "title": "Add a screenshot or demo GIF",
        "description": "Visual demos increase trust and understanding. A single screenshot showing your tool in action can double engagement on GitHub.",
        "effort": "Minimal (10 min)",
        "impact": "High",
        "tools": ["aitools launch ."],
    },
}


def _api_get(path: str) -> dict | list:
    """GitHub API GET."""
    url = f"https://api.github.com{path}"
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


def _get_repo_info(owner: str, repo: str) -> dict:
    """Fetch basic repo info."""
    data = _api_get(f"/repos/{owner}/{repo}")
    if isinstance(data, dict) and "id" in data:
        return data
    return {}


def _check_file_exists(owner: str, repo: str, filename: str) -> bool:
    """Check if a specific file exists in repo root."""
    try:
        data = _api_get(f"/repos/{owner}/{repo}/contents/{filename}")
        return isinstance(data, dict) and "name" in data
    except Exception:
        return False


def _get_license_info(owner: str, repo: str) -> str | None:
    """Get license info if present."""
    try:
        data = _api_get(f"/repos/{owner}/{repo}/license")
        if isinstance(data, dict) and data.get("license"):
            return data["license"].get("spdx_id") or data["license"].get("name")
    except Exception:
        pass
    return None


def diagnose_repo(repo_input: str) -> dict:
    """
    Generate a full diagnosis for a repo.
    Returns dict with diagnosis data.
    """
    parsed = _parse_repo_ident(repo_input)
    if not parsed:
        return {"error": f"Invalid repo input: {repo_input}"}
    owner, repo_name = parsed

    print(f"[INFO] Diagnosing {owner}/{repo_name}...", file=sys.stderr)

    # Gather data
    repo_info = _get_repo_info(owner, repo_name)
    time.sleep(0.2)
    readme_text = _get_readme(owner, repo_name)
    time.sleep(0.2)

    description = repo_info.get("description") or "(no description)"
    stars = repo_info.get("stargazers_count", 0)
    forks = repo_info.get("forks_count", 0)
    open_issues = repo_info.get("open_issues_count", 0)

    # Analyze README
    readme_lines = readme_text.splitlines() if readme_text else []
    readme_line_count = len(readme_lines)
    readme_sections = set()
    if readme_text:
        for line in readme_lines:
            m = re.match(r'^#+\s+(.+?)\s*$', line.strip())
            if m:
                readme_sections.add(m.group(1).strip().lower())
    has_examples = bool(re.findall(r'```', readme_text or ""))
    has_images = bool(re.findall(r'!\[.*?\]\(.*?\)', readme_text or ""))

    # Check file existence
    has_license = _check_file_exists(owner, repo_name, "LICENSE") or \
                  _check_file_exists(owner, repo_name, "LICENSE.md") or \
                  _check_file_exists(owner, repo_name, "LICENSE.txt")
    has_security = _check_file_exists(owner, repo_name, "SECURITY.md") or \
                   _check_file_exists(owner, repo_name, "SECURITY")
    has_contributing = _check_file_exists(owner, repo_name, "CONTRIBUTING.md") or \
                       _check_file_exists(owner, repo_name, "CONTRIBUTING")
    has_changelog = _check_file_exists(owner, repo_name, "CHANGELOG.md")
    has_ci = _check_file_exists(owner, repo_name, ".github/workflows")
    license_info = _get_license_info(owner, repo_name)

    # Determine top 5 issues
    issues = []
    suggestions = []

    # Issue 1: README structure
    good_sections = {"installation", "install", "usage", "example", "examples",
                     "getting started", "quickstart", "quick start", "setup",
                     "api", "documentation", "docs"}
    found_good = readme_sections & good_sections
    if len(found_good) < 3:
        issues.append("weak_readme")
        suggestions.append("readme_structure")

    # Issue 2: Missing license
    if not has_license:
        issues.append("no_license")
        suggestions.append("add_license")

    # Issue 3: Missing security policy
    if not has_security:
        issues.append("no_security")
        suggestions.append("add_security_policy")

    # Issue 4: Missing contributing guide
    if not has_contributing:
        issues.append("no_contributing")
        suggestions.append("add_contributing_guide")

    # Issue 5: CI
    if not has_ci:
        issues.append("no_ci")
        suggestions.append("setup_ci")

    # Issue 6: Examples missing
    if not has_examples and readme_line_count < 50:
        if "add_examples" not in suggestions:
            suggestions.append("add_examples")

    # Issue 7: No screenshots
    if not has_images:
        if "screenshot" not in suggestions:
            suggestions.append("screenshot")

    # Issue 8: No changelog
    if not has_changelog:
        if "changelog" not in suggestions:
            suggestions.append("changelog")

    # Issue 9: Badges missing
    if readme_text and "badge" not in readme_text.lower() and "shields.io" not in readme_text.lower():
        if "badges" not in suggestions:
            suggestions.append("badges")

    # Issue 10: No issue templates
    if "add_examples" not in suggestions and len(suggestions) < 5:
        suggestions.append("add_examples")

    # Pick exactly 5 suggestions (prioritize high impact)
    priority_map = {s: IMPROVEMENT_TEMPLATES[s].get("impact", "Medium") for s in suggestions}
    priority_order = {"Very High": 0, "High": 1, "Medium": 2, "Low": 3, "Minimal": 4}
    suggestions.sort(key=lambda s: (priority_order.get(priority_map.get(s, "Medium"), 5), s))

    top_suggestions = suggestions[:5]
    if len(top_suggestions) < 5:
        # Fill with config_auto (our product recommendation)
        fallbacks = ["config_auto", "setup_ci", "tests_setup", "code_quality", "pypi_package"]
        for fb in fallbacks:
            if fb not in top_suggestions:
                top_suggestions.append(fb)
            if len(top_suggestions) >= 5:
                break

    # Calculate effort estimate
    effort_levels = [IMPROVEMENT_TEMPLATES[s]["effort"] for s in top_suggestions]
    total_effort_parts = []
    for e in effort_levels:
        if "Minimal" in e:
            total_effort_parts.append(0.5)
        elif "Low" in e:
            total_effort_parts.append(1)
        elif "Medium" in e:
            total_effort_parts.append(2)
        elif "High" in e:
            total_effort_parts.append(3)
    total_hours = sum(total_effort_parts)
    if total_hours < 2:
        effort_estimate = f"~{int(total_hours * 60)} minutes"
    else:
        effort_estimate = f"~{total_hours} hours"

    recommendation = IMPROVEMENT_TEMPLATES["config_auto"]["description"]

    diagnosis = {
        "repo": f"{owner}/{repo_name}",
        "url": f"https://github.com/{owner}/{repo_name}",
        "description": description,
        "stars": stars,
        "forks": forks,
        "open_issues": open_issues,
        "readme_line_count": readme_line_count,
        "readme_sections_found": sorted(readme_sections),
        "has_license": has_license,
        "has_security": has_security,
        "has_contributing": has_contributing,
        "has_changelog": has_changelog,
        "has_ci": has_ci,
        "has_examples": has_examples,
        "has_images": has_images,
        "license": license_info,
        "issues_found": issues,
        "top_suggestions": [
            {
                "title": IMPROVEMENT_TEMPLATES[s]["title"],
                "description": IMPROVEMENT_TEMPLATES[s]["description"],
                "effort": IMPROVEMENT_TEMPLATES[s]["effort"],
                "impact": IMPROVEMENT_TEMPLATES[s]["impact"],
                "id": s,
            }
            for s in top_suggestions
        ],
        "total_effort": effort_estimate,
        "recommended_command": "aitools launch .",
        "recommendation": recommendation,
        "diagnosed_at": datetime.now(timezone.utc).isoformat(),
    }

    return diagnosis


def render_diagnosis_md(diagnosis: dict) -> str:
    """Render diagnosis as a Markdown report."""
    if "error" in diagnosis:
        return f"# Diagnosis Error\n\n{diagnosis['error']}\n"

    lines = []
    lines.append(f"# Repo Diagnosis: {diagnosis['repo']}")
    lines.append("")
    lines.append(f"> **URL:** {diagnosis['url']}")
    lines.append(f"> **Description:** {diagnosis['description']}")
    lines.append(f"> **Stars:** {diagnosis['stars']}  |  **Forks:** {diagnosis['forks']}  |  **Issues:** {diagnosis['open_issues']}")
    lines.append(f"> **Diagnosed:** {diagnosis['diagnosed_at'][:19]}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Current State Analysis")
    lines.append("")
    lines.append(f"- **README:** {diagnosis['readme_line_count']} lines, {len(diagnosis['readme_sections_found'])} sections found")
    if diagnosis['readme_sections_found']:
        lines.append(f"  - Sections: {', '.join(diagnosis['readme_sections_found'])}")
    lines.append(f"- **LICENSE:** {'✅ Present' if diagnosis['has_license'] else '❌ Missing'}")
    lines.append(f"- **SECURITY.md:** {'✅ Present' if diagnosis['has_security'] else '❌ Missing'}")
    lines.append(f"- **CONTRIBUTING.md:** {'✅ Present' if diagnosis['has_contributing'] else '❌ Missing'}")
    lines.append(f"- **CHANGELOG:** {'✅ Present' if diagnosis['has_changelog'] else '❌ Missing'}")
    lines.append(f"- **CI/CD:** {'✅ Present' if diagnosis['has_ci'] else '❌ Missing'}")
    lines.append(f"- **Code Examples:** {'✅ Present' if diagnosis['has_examples'] else '❌ Missing'}")
    lines.append(f"- **Screenshots/Images:** {'✅ Present' if diagnosis['has_images'] else '❌ Missing'}")
    lines.append(f"- **License Type:** {diagnosis['license'] or 'None'}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Launch Readiness Score")
    lines.append("")
    # Calculate approximate score
    score = 0
    score += min(20, diagnosis['readme_line_count'] // 5)
    score += 20 if diagnosis['has_license'] else 0
    score += 15 if diagnosis['has_security'] else 0
    score += 15 if diagnosis['has_contributing'] else 0
    score += 15 if diagnosis['has_ci'] else 0
    score += 10 if diagnosis['has_changelog'] else 0
    score += 5 if diagnosis['has_images'] else 0
    score = max(1, min(100, score))
    lines.append(f"**Score: {score}/100**")
    level = "Excellent" if score >= 80 else "Good" if score >= 60 else "Fair" if score >= 40 else "Poor" if score >= 20 else "Needs Work"
    lines.append(f"**Level: {level}**")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Top 5 Improvement Suggestions")
    lines.append("")

    for i, s in enumerate(diagnosis["top_suggestions"], 1):
        lines.append(f"### {i}. {s['title']}")
        lines.append("")
        lines.append(f"**Effort:** {s['effort']}  |  **Impact:** {s['impact']}")
        lines.append("")
        lines.append(s['description'])
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Estimated Total Effort")
    lines.append("")
    lines.append(f"**{diagnosis['total_effort']}** to implement all 5 suggestions.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## AI Tools Recommendation")
    lines.append("")
    lines.append("Run the **AI Tools** unified CLI to automate most of these improvements:")
    lines.append("")
    lines.append("```bash")
    lines.append("pip install ai-dev-tools")
    lines.append(f"cd /path/to/{diagnosis['repo'].split('/')[1]}")
    lines.append("aitools launch .")
    lines.append("```")
    lines.append("")
    lines.append(f"> {diagnosis['recommendation']}")
    lines.append("")
    lines.append("The `aitools launch .` command will:")
    lines.append("- Analyze your codebase structure")
    lines.append("- Generate standard README sections")
    lines.append("- Create LICENSE, SECURITY.md, CONTRIBUTING.md, and CHANGELOG.md")
    lines.append("- Set up GitHub Actions CI")
    lines.append("- Add status badges to your README")
    lines.append("- Configure PyPI publishing")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Diagnosis generated automatically by AI Tools Outreach System*")
    lines.append(f"*{diagnosis['diagnosed_at'][:19]}*")

    return "\n".join(lines)


def save_diagnosis(diagnosis: dict) -> Path | None:
    """Save diagnosis to markdown file. Returns path or None."""
    if "error" in diagnosis:
        print(f"[ERROR] {diagnosis['error']}", file=sys.stderr)
        return None

    # Create safe filename
    repo_path = diagnosis["repo"].replace("/", "_").replace(" ", "_")
    out_path = DIAGNOSES_DIR / f"{repo_path}.md"

    DIAGNOSES_DIR.mkdir(parents=True, exist_ok=True)
    md = render_diagnosis_md(diagnosis)
    out_path.write_text(md)

    print(f"[OK] Diagnosis saved: {out_path}", file=sys.stderr)
    return out_path


def diagnose_from_cache() -> list[dict]:
    """Diagnose all repos from the targets cache."""
    if not CACHE_FILE.exists():
        print(f"[ERROR] No cache file at {CACHE_FILE}", file=sys.stderr)
        return []

    data = json.loads(CACHE_FILE.read_text())
    targets = data.get("targets", [])
    if not targets:
        print("[WARN] No targets in cache", file=sys.stderr)
        return []

    results = []
    for t in targets:
        full_name = t["full_name"]
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[INFO] Diagnosing {full_name}...", file=sys.stderr)
        diagnosis = diagnose_repo(full_name)
        path = save_diagnosis(diagnosis)
        results.append(diagnosis)
        if path:
            print(f"[OK] Saved to {path}", file=sys.stderr)
        time.sleep(0.5)

    return results


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  python diagnosis_generator.py <github_url_or_full_name>")
        print("  python diagnosis_generator.py --from-cache")
        sys.exit(0)

    if args[0] == "--from-cache":
        results = diagnose_from_cache()
    elif args[0] == "--save" and len(args) >= 2:
        diagnosis = diagnose_repo(args[1])
        path = save_diagnosis(diagnosis)
        if path:
            print(f"\nDiagnosis saved to: {path}")
    else:
        diagnosis = diagnose_repo(args[0])
        print(render_diagnosis_md(diagnosis))


if __name__ == "__main__":
    main()
