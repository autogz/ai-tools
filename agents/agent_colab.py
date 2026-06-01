
# Google Colab Agent — 计算员
# 使用免费 GPU (T4/K80)
# 有 Google 云 IP
# 
# 部署: 复制到 https://colab.research.google.com 运行

import urllib.request
import json
import os
import threading
import time

GITHUB_TOKEN = ""  # Set via secrets
REPO = "autogz/ai-tools"
ISSUE = 1

def get_ip():
    try:
        return urllib.request.urlopen("https://ifconfig.me", timeout=5).read().decode().strip()
    except:
        return "unknown"

def report(message):
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments"
    data = json.dumps({"body": message}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "colab-agent/1.0",
    })
    try:
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

# Report that we are alive
ip = get_ip()
report(f"🤖 Colab Agent online!\nIP: {ip}\nGPU: Available\nMode: Free tier")

# Keep alive loop
def heartbeat():
    while True:
        time.sleep(3600)  # Every hour
        report(f"🤖 Colab Agent heartbeat\nStill alive")

threading.Thread(target=heartbeat, daemon=True).start()

print(f"Colab Agent running on {ip}")
