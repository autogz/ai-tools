#!/usr/bin/env python3
"""
Source IP Protection — 合法源站 IP 保护
不搭建代理，不绕过风控，只做标准网络安全防护
"""
import json
import re
import os
import urllib.request
from pathlib import Path

BASE = Path("/root/.hermes-revenue-agents")
REPORT_DIR = BASE / "reports"
RULES = BASE / "rules" / "ip_protection_rules.yaml"


def load_rules() -> dict:
    """加载 IP 保护规则"""
    if not RULES.exists():
        return {
            "cloudflare_only": True,
            "deny_direct_ip": True,
            "hsts_required": True,
            "turnstile_required": True,
            "rate_limiting_enabled": True,
            "webhook_signature_required": True,
            "origin_ip_never_in_code": True,
            "origin_ip_never_in_readme": True,
            "origin_ip_never_in_js": True,
            "origin_ip_never_in_logs": True,
        }
    content = RULES.read_text()
    rules = {}
    for line in content.split("\n"):
        m = re.match(r'^(\w+):\s*(true|false)', line)
        if m:
            rules[m.group(1)] = m.group(2).lower() == "true"
    return rules


def scan_file_for_ip_leaks(filepath: Path) -> list[dict]:
    """扫描单个文件是否泄露 IP"""
    findings = []
    
    if not filepath.exists():
        return findings
    
    content = filepath.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    
    # IP 正则
    ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
    
    # 允许的 IP（本地和 Cloudflare）
    allowed_ips = ["127.0.0.1", "0.0.0.0", "::1", "192.168.", "10.", "172.16.", "172.17."]
    cloudflare_ranges = ["103.21.244.", "103.22.200.", "103.31.4.", "104.16.", "104.17.",
                         "104.18.", "104.19.", "104.20.", "104.21.", "104.22.", "104.23.",
                         "104.24.", "104.25.", "104.26.", "104.27.", "104.28.", "104.29.",
                         "131.0.72.", "141.101.", "162.158.", "172.64.", "172.65.",
                         "173.245.", "188.114.", "190.93.", "197.234.", "198.41."]
    
    for i, line in enumerate(lines, 1):
        matches = ip_pattern.findall(line)
        for ip in matches:
            # 检查是否允许
            is_allowed = any(ip.startswith(p) for p in allowed_ips + cloudflare_ranges)
            
            if not is_allowed:
                findings.append({
                    "file": str(filepath),
                    "line": i,
                    "ip": ip,
                    "risk": "high" if ip.startswith("104.28.") else "medium",
                    "context": line.strip()[:80],
                })
    
    return findings


def scan_directory_for_ip_leaks(directory: Path) -> list[dict]:
    """扫描目录下所有文件是否泄露 IP"""
    all_findings = []
    
    # 跳过目录
    skip_dirs = {".git", "__pycache__", ".venv", "node_modules", ".hermes", "dist", "build"}
    
    for filepath in directory.rglob("*"):
        if filepath.is_dir():
            continue
        if any(p in str(filepath.relative_to(directory)) for p in skip_dirs):
            continue
        
        # 只扫描文本文件
        ext = filepath.suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot"):
            continue
        
        findings = scan_file_for_ip_leaks(filepath)
        all_findings.extend(findings)
    
    return all_findings


def scan_readme_for_ip() -> list[dict]:
    """扫描 README 是否泄露 IP"""
    paths = [
        Path("/root/ai-tools-repo/README.md"),
        Path("/root/ai-terminal/README.md"),
        Path("/root/ai-pr-review/README.md"),
        Path("/root/ai-sql/README.md"),
        Path("/root/ai-img-cli/README.md"),
    ]
    
    findings = []
    for p in paths:
        if p.exists():
            findings.extend(scan_file_for_ip_leaks(p))
    
    return findings


def scan_js_for_ip() -> list[dict]:
    """扫描 JS 文件是否泄露 IP"""
    findings = []
    js_paths = [
        Path("/root/ai-tools-repo/docs-site"),
    ]
    for base in js_paths:
        if base.exists():
            for f in base.rglob("*.js"):
                findings.extend(scan_file_for_ip_leaks(f))
    return findings


def check_public_dns(domain: str = "github.com/autogz/ai-tools") -> list[dict]:
    """检查公开 DNS 是否泄露源站 IP"""
    findings = []
    try:
        # 检查 A 记录
        req = urllib.request.Request(f"https://dns.google/resolve?name={domain}&type=A")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            for answer in data.get("Answer", []):
                ip = answer.get("data", "")
                if ip and not ip.startswith("104.") and not ip.startswith("172."):
                    findings.append({
                        "type": "dns_a_record",
                        "domain": domain,
                        "ip": ip,
                        "risk": "medium" if ip.startswith("10.") or ip.startswith("192.") else "high",
                    })
    except Exception as e:
        findings.append({"type": "dns_check_error", "detail": str(e)})
    
    return findings


def generate_report() -> str:
    """生成 IP 泄露报告"""
    report_dir = REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    
    from datetime import datetime
    
    lines = [
        f"# IP Leak Report",
        f"",
        f"**Generated**: {datetime.now().isoformat()}",
        f"**Rules**: IP protection rules from {RULES}",
        f"",
    ]
    
    # 扫描 README
    readme_leaks = scan_readme_for_ip()
    lines.append(f"## README IP Scan")
    lines.append(f"")
    if readme_leaks:
        lines.append(f"⚠️ Found {len(readme_leaks)} potential IP leaks in README files:")
        for leak in readme_leaks[:10]:
            lines.append(f"- {leak['file']}:{leak['line']} → `{leak['ip']}`")
    else:
        lines.append(f"✅ No IP leaks found in README files")
    lines.append("")
    
    # 扫描 JS
    js_leaks = scan_js_for_ip()
    lines.append(f"## JavaScript IP Scan")
    lines.append(f"")
    if js_leaks:
        lines.append(f"⚠️ Found {len(js_leaks)} potential IP leaks in JS files")
    else:
        lines.append(f"✅ No IP leaks found in JS files")
    lines.append("")
    
    # 扫描 repo
    repo_leaks = scan_directory_for_ip_leaks(Path("/root/ai-tools-repo"))
    lines.append(f"## Repository IP Scan")
    lines.append(f"")
    if repo_leaks:
        lines.append(f"⚠️ Found {len(repo_leaks)} potential IP leaks in repository:")
        for leak in repo_leaks[:15]:
            lines.append(f"- {leak['file']}:{leak['line']} → `{leak['ip']}` ({leak['risk']})")
    else:
        lines.append(f"✅ No IP leaks found in repository")
    lines.append("")
    
    # DNS 检查
    dns_leaks = check_public_dns()
    lines.append(f"## DNS Check")
    lines.append(f"")
    if dns_leaks:
        for d in dns_leaks:
            if d.get("risk") == "high":
                lines.append(f"🔴 {d['type']}: {d.get('domain','')} → {d.get('ip','')}")
            else:
                lines.append(f"🟡 {d['type']}: {d.get('domain','')} → {d.get('ip','')}")
    else:
        lines.append(f"✅ DNS records appear properly proxied")
    lines.append("")
    
    # 建议
    lines.append("## Recommendations")
    lines.append("")
    rules = load_rules()
    if rules.get("origin_ip_never_in_readme"):
        lines.append("- ✅ README IP scan: enabled")
    if rules.get("origin_ip_never_in_js"):
        lines.append("- ✅ JS IP scan: enabled")
    if rules.get("cloudflare_only"):
        lines.append("- [ ] Action: Ensure domain DNS is proxied through Cloudflare")
    if rules.get("turnstile_required"):
        lines.append("- [ ] Action: Add Cloudflare Turnstile to all forms")
    if rules.get("rate_limiting_enabled"):
        lines.append("- [ ] Action: Enable rate limiting on API endpoints")
    
    report_content = "\n".join(lines)
    report_path = report_dir / "ip_leak_report.md"
    report_path.write_text(report_content)
    
    return report_content


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        report = generate_report()
        print(report[:1000])
        print(f"\n---\nFull report: {REPORT_DIR / 'ip_leak_report.md'}")
    else:
        # 快速扫描
        repo_leaks = scan_directory_for_ip_leaks(Path("/root/ai-tools-repo"))
        if repo_leaks:
            print(f"⚠️ Found {len(repo_leaks)} potential IP leaks:")
            for l in repo_leaks[:10]:
                print(f"  {l['file']}:{l['line']} → {l['ip']}")
        else:
            print("✅ No IP leaks found in repository")
