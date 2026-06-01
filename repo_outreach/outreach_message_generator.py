#!/usr/bin/env python3
"""
outreach_message_generator.py — For a given repo, generates a personalized
outreach message (draft only) that references the repo's specific issues
and offers the free diagnosis. Must NOT be spammy, must be genuinely helpful.

Usage:
  python outreach_message_generator.py <github_url_or_full_name>
  python outreach_message_generator.py --from-cache
  python outreach_message_generator.py --batch <file>
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
LOG_FILE = BASE_DIR / "outreach_log.jsonl"
CACHE_FILE = BASE_DIR / "targets_cache.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"

# Templates for different outreach channels
CHANNEL_TEMPLATES = {
    "github_issue": {
        "salutation": "Hi there!",
        "tone": "professional",
        "format": "issue_comment",
    },
    "github_discussion": {
        "salutation": "Hello!",
        "tone": "professional",
        "format": "discussion",
    },
    "email": {
        "salutation": "Hello,",
        "tone": "professional",
        "format": "email",
    },
    "twitter_dm": {
        "salutation": "Hey!",
        "tone": "casual",
        "format": "dm",
    },
}


def _api_get(path: str) -> dict | list:
    """GitHub API GET."""
    url = f"{GITHUB_API}{path}"
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
    m = re.match(r'https?://github\.com/([^/]+)/([^/\s?#]+)', repo_input)
    if m:
        return m.group(1), m.group(2).replace(".git", "")
    m = re.match(r'^([\w.-]+)/([\w.-]+)$', repo_input)
    if m:
        return m.group(1), m.group(2)
    return None


def _get_readme(owner: str, repo: str) -> str | None:
    try:
        data = _api_get(f"/repos/{owner}/{repo}/readme")
        if isinstance(data, dict) and "content" in data and data.get("encoding") == "base64":
            import base64
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        pass
    return None


def _get_repo_info(owner: str, repo: str) -> dict:
    data = _api_get(f"/repos/{owner}/{repo}")
    if isinstance(data, dict) and "id" in data:
        return data
    return {}


def _get_recent_issues(owner: str, repo: str, limit: int = 3) -> list[dict]:
    """Fetch recent open issues for context."""
    data = _api_get(f"/repos/{owner}/{repo}/issues?state=open&sort=updated&per_page={limit}")
    if isinstance(data, list):
        return [
            {"number": i["number"], "title": i["title"], "url": i["html_url"]}
            for i in data if "pull_request" not in i
        ]
    return []


def _load_diagnosis(repo_name: str) -> dict | None:
    """Load existing diagnosis for a repo if available."""
    repo_path = repo_name.replace("/", "_").replace(" ", "_")
    md_path = DIAGNOSES_DIR / f"{repo_path}.md"
    if md_path.exists():
        return {"exists": True, "path": str(md_path)}
    return None


def _log_outreach(entry: dict) -> None:
    """Log an outreach generation to JSONL."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _find_repo_strengths(readme_text: str | None, repo_info: dict) -> list[str]:
    """Identify specific positive aspects to mention."""
    strengths = []
    desc = repo_info.get("description", "")
    if desc:
        # Extract key phrases
        for phrase in desc.split("."):
            phrase = phrase.strip()
            if len(phrase) > 15 and len(phrase) < 100:
                strengths.append(phrase)
    if readme_text:
        # Check if they have a logo
        if re.search(r'!\[.*?\]\(.*?\.(png|jpg|svg)\)', readme_text):
            strengths.append("has a project logo/icon")
        # Check for star history or shields
        if "badge" in readme_text.lower() or "shields.io" in readme_text.lower():
            strengths.append("includes status badges")
    return strengths[:3]  # Max 3


def _find_specific_issues(readme_text: str | None, repo_info: dict, owner: str, repo: str) -> list[dict]:
    """Identify 2-3 specific issues to mention in outreach."""
    issues = []

    # Check README length
    if readme_text:
        lines = readme_text.splitlines()
        if len(lines) < 30:
            issues.append({
                "type": "readme_too_short",
                "detail": f"README is only {len(lines)} lines. Adding structured sections would help users understand the project faster.",
            })
        elif len(lines) < 80:
            issues.append({
                "type": "readme_could_expand",
                "detail": f"README has good basics at {len(lines)} lines but could benefit from usage examples and installation instructions.",
            })

        # Check for missing sections
        sections = set()
        for line in lines:
            m = re.match(r'^#+\s+(.+?)\s*$', line.strip())
            if m:
                sections.add(m.group(1).strip().lower())

        missing = []
        if "installation" not in sections and "install" not in sections:
            missing.append("Installation")
        if "usage" not in sections and "example" not in sections:
            missing.append("Usage/Examples")
        if "license" not in sections:
            missing.append("License information")
        if missing:
            issues.append({
                "type": "missing_sections",
                "detail": f"README is missing key sections: {', '.join(missing[:2])}. These are critical for user adoption.",
            })
    else:
        issues.append({
            "type": "no_readme",
            "detail": "No README file found. A README is the first thing potential users see.",
        })

    # Check for license
    try:
        license_data = _api_get(f"/repos/{owner}/{repo}/license")
        if not isinstance(license_data, dict) or "license" not in license_data:
            issues.append({
                "type": "no_license",
                "detail": "No license file detected. Without a license, other developers cannot legally use or contribute.",
            })
    except Exception:
        pass

    # Check for CI
    try:
        workflows = _api_get(f"/repos/{owner}/{repo}/actions/workflows")
        if isinstance(workflows, dict) and workflows.get("total_count", 0) == 0:
            issues.append({
                "type": "no_ci",
                "detail": "No CI/CD pipeline found. Automated testing builds user trust and catches regressions.",
            })
    except Exception:
        pass

    return issues[:3]  # Max 3 specific issues


def generate_outreach(repo_input: str, channel: str = "github_discussion") -> dict:
    """
    Generate a personalized outreach message for a repo.
    
    Args:
        repo_input: GitHub URL or owner/repo format
        channel: One of 'github_issue', 'github_discussion', 'email', 'twitter_dm'
    
    Returns:
        Dict with outreach message data
    """
    parsed = _parse_repo_ident(repo_input)
    if not parsed:
        return {"error": f"Invalid repo input: {repo_input}"}
    owner, repo_name = parsed

    print(f"[INFO] Generating outreach for {owner}/{repo_name} ({channel})...", file=sys.stderr)

    # Gather data
    repo_info = _get_repo_info(owner, repo_name)
    time.sleep(0.2)
    readme_text = _get_readme(owner, repo_name)
    time.sleep(0.2)

    description = repo_info.get("description") or "a Python project"
    stars = repo_info.get("stargazers_count", 0)
    language = repo_info.get("language") or "Python"
    
    strengths = _find_repo_strengths(readme_text, repo_info)
    specific_issues = _find_specific_issues(readme_text, repo_info, owner, repo_name)
    existing_diagnosis = _load_diagnosis(f"{owner}/{repo_name}")
    recent_issues = _get_recent_issues(owner, repo_name)

    # Get channel template
    channel_info = CHANNEL_TEMPLATES.get(channel, CHANNEL_TEMPLATES["github_discussion"])
    salutation = channel_info["salutation"]
    tone = channel_info["tone"]

    # ---- Build the message ----
    
    # Opening paragraph — genuine, specific compliment about their work
    strength_phrases = []
    if strengths:
        for s in strengths[:2]:
            strength_phrases.append(f"I noticed your project {s}")

    if strength_phrases:
        opening = (
            f"{salutation} I came across {owner}/{repo_name} and was impressed by what "
            f"you're building — {', and '.join(strength_phrases)}. "
            f"It's clear you've put real thought into this."
        )
    else:
        opening = (
            f"{salutation} I found {owner}/{repo_name} while browsing Python projects "
            f"and it looks like a solid idea. The concept of \"{description[:80]}\" "
            f"resonates with work I've been doing."
        )

    # Middle section — specific, helpful observations
    issues_paragraphs = []
    if specific_issues:
        first_issue = specific_issues[0]
        if first_issue["type"] == "readme_too_short":
            issues_paragraphs.append(
                f"One thing I noticed: the README is on the shorter side. "
                f"{first_issue['detail']} "
                f"A more structured README could significantly boost your project's visibility."
            )
        elif first_issue["type"] == "missing_sections":
            issues_paragraphs.append(
                f"I was looking through the README and noticed it could use a few more sections. "
                f"{first_issue['detail']} "
                f"These are small changes that make a big difference for new visitors."
            )
        elif first_issue["type"] == "no_license":
            issues_paragraphs.append(
                f"One quick thing: your repo doesn't have a license yet. "
                f"{first_issue['detail']} "
                f"Adding an MIT license takes 2 minutes and immediately makes the project more approachable."
            )
        elif first_issue["type"] == "no_ci":
            issues_paragraphs.append(
                f"I also noticed there's no CI pipeline set up. "
                f"{first_issue['detail']} "
                f"GitHub Actions is free and can be configured in under 30 minutes."
            )
        else:
            issues_paragraphs.append(first_issue["detail"])

        # Add second issue if available
        if len(specific_issues) >= 2:
            si = specific_issues[1]
            issues_paragraphs.append(
                f"Also, {si['detail'][0].lower()}{si['detail'][1:]}"
            )
    
    # Offer section — genuine help offer, not spam
    has_diagnosis_msg = ""
    if existing_diagnosis:
        has_diagnosis_msg = (
            f"I actually ran a free diagnosis on your repo already "
            f"— it identified several specific improvements. I'm happy to share it."
        )
    
    offer = (
        f"I've been working on a tool called **AI Tools** that helps Python developers "
        f"improve their projects — auto-generating README sections, LICENSE files, "
        f"CI configs, and more with a single command (`aitools launch .`). "
        f"\n\n"
        f"I'd love to offer you a **free repo diagnosis** — a personalized report "
        f"that identifies specific issues and suggests fixes. No strings attached, "
        f"no commitment. If it's useful, great. If not, no worries."
    )

    # Closing — respectful, low pressure
    repo_url = f"https://github.com/{owner}/{repo_name}"
    closing = (
        f"Either way, keep up the good work on `{repo_name}`. "
        f"It's a cool project and I hope it gets the attention it deserves.\n\n"
        f"Best,\nAI Tools — https://github.com/autogz/ai-tools"
    )

    if tone == "casual" and channel == "twitter_dm":
        closing = (
            f"Anyway, keep building! `{repo_name}` has potential.\n\n"
            f"Full diagnosis here if you want it: "
            f"https://github.com/autogz/ai-tools\n"
            f"Just a dev trying to help other devs."
        )

    # Assemble full message
    message_parts = [opening, "", *issues_paragraphs, "", offer]
    if has_diagnosis_msg:
        message_parts.append("")
        message_parts.append(has_diagnosis_msg)
    message_parts.extend(["", closing])
    full_message = "\n".join(message_parts)

    # Build result
    result = {
        "repo": f"{owner}/{repo_name}",
        "repo_url": f"https://github.com/{owner}/{repo_name}",
        "channel": channel,
        "salutation": salutation,
        "tone": tone,
        "strengths_mentioned": strengths,
        "issues_mentioned": [i["type"] for i in specific_issues],
        "message": full_message,
        "character_count": len(full_message),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnosis_available": existing_diagnosis is not None,
        "status": "draft",
    }

    return result


def print_outreach(result: dict) -> None:
    """Pretty-print an outreach message."""
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    print("=" * 60)
    print(f"OUTREACH MESSAGE — {result['repo']}")
    print(f"Channel: {result['channel']}")
    print(f"Tone: {result['tone']}")
    print(f"Chars: {result['character_count']}")
    print("=" * 60)
    print()
    print(result["message"])
    print()
    print("=" * 60)


def generate_from_cache() -> list[dict]:
    """Generate outreach for all cached targets."""
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
        result = generate_outreach(full_name, channel="github_discussion")
        results.append(result)
        _log_outreach(result)
        print(f"[OK] Generated outreach for {full_name} ({result['character_count']} chars)", file=sys.stderr)
        time.sleep(0.5)

    return results


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  python outreach_message_generator.py <github_url_or_full_name>")
        print("  python outreach_message_generator.py <url> --channel <channel>")
        print("  python outreach_message_generator.py --from-cache")
        print("  python outreach_message_generator.py --batch <file>")
        print()
        print("Channels: github_issue, github_discussion, email, twitter_dm")
        sys.exit(0)

    channel = "github_discussion"
    repo_input = None

    if "--channel" in args:
        idx = args.index("--channel")
        if idx + 1 < len(args):
            channel = args[idx + 1]
        args = [a for a in args if a not in (args[idx], args[idx + 1] if idx + 1 < len(args) else "")]

    if args[0] == "--from-cache":
        results = generate_from_cache()
    elif args[0] == "--batch" and len(args) >= 2:
        with open(args[1]) as f:
            repos = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        results = []
        for r in repos:
            result = generate_outreach(r, channel)
            results.append(result)
            _log_outreach(result)
            time.sleep(0.5)
    else:
        result = generate_outreach(args[0], channel)
        results = [result]

    for r in results:
        print_outreach(r)

    # Log all
    for r in results:
        _log_outreach(r)

    print(f"\n[OK] Generated {len(results)} outreach message(s). Logged to {LOG_FILE}")


if __name__ == "__main__":
    main()
