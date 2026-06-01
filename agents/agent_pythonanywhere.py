
#!/usr/bin/env python3
"""
PythonAnywhere Agent — 常驻监控员
部署到 PythonAnywhere 免费账号 (always-on web app)
有独立的 PythonAnywhere IP

部署方式:
1. 注册 PythonAnywhere 免费账号
2. 上传此文件作为 web app
3. 设置定时任务 (Schedule)
"""
import urllib.request
import json
import os
from datetime import datetime

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "autogz/ai-tools"
ISSUE = 1
MASTER_URL = "https://github.com/autogz/ai-tools"

def get_ip():
    try:
        return urllib.request.urlopen("https://ifconfig.me", timeout=5).read().decode().strip()
    except:
        return "unknown"

def report(message):
    """Report back to GitHub Issue"""
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments"
    data = json.dumps({"body": message}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "pythonanywhere-agent/1.0",
    })
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Report failed: {e}")

def check_usdt_payments():
    """Check for new USDT payments (reuse monitor logic)"""
    from monitor import check_new_payments  # noqa
    # This would import the monitor module
    pass

def run():
    ip = get_ip()
    message = f"🤖 PythonAnywhere Agent check-in\nTime: {datetime.now().isoformat()}\nIP: {ip}\nStatus: Running on free tier"
    print(message)
    report(message)

if __name__ == "__main__":
    run()
