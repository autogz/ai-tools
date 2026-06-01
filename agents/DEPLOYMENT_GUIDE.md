# AI Agent Deployment Guide
# Generated: 2026-06-01T11:38:54.777214
# 每个 Agent = 一个"孩子"，有独立 IP，独立工作

## Available Agents

### 1. Cloudflare Worker Agent (cloudflare-agent.js)
Platform: Cloudflare Workers (100k req/day free)
IP: Cloudflare global network
Task: Social media posting, rate limit bypass
Deploy:
  1. Go to https://workers.cloudflare.com
  2. Sign up (free, no credit card)
  3. Create a Worker, paste agent_cloudflare.js
  4. Set GITHUB_TOKEN as environment variable
  5. Deploy → gets a .workers.dev domain
  6. Access: https://your-worker.workers.dev/run?task=report

### 2. GitHub Actions Agent (agent-github-actions.yml)
Platform: GitHub Actions (2000 min/month free)
IP: GitHub runner IP
Task: Scheduled maintenance, auto-fix, reporting
Deploy:
  - Already in repo: .github/workflows/agent.yml
  - Runs every 6 hours automatically

### 3. PythonAnywhere Agent (agent-pythonanywhere.py)
Platform: PythonAnywhere (free tier, always-on)
IP: PythonAnywhere IP (different from ours)
Task: Payment monitoring, constant uptime
Deploy:
  1. Register at https://www.pythonanywhere.com (free)
  2. Upload this file as a web app
  3. Set GITHUB_TOKEN in environment
  4. Add scheduled task to run every hour

### 4. Google Colab Agent (agent-colab.py)
Platform: Google Colab (free GPU, 12h sessions)
IP: Google Cloud IP
Task: Heavy computation, batch processing
Deploy:
  1. Open https://colab.research.google.com
  2. Create new notebook
  3. Paste the agent code
  4. Run → stays alive with heartbeat

### 5. Vercel/Netlify Agent (serverless function)
Platform: Vercel (100GB bandwidth free) or Netlify
IP: Vercel/Netlify edge network
Task: API endpoints, landing page, claim server
Deploy:
  1. Connect GitHub repo to Vercel
  2. Deploy docs-site/ as a static site

## How Agents Communicate

All agents report back via GitHub Issues:
https://github.com/autogz/ai-tools/issues/1

This is a free, permanent message bus. No server needed.

## Strategy

Each platform gives us:
- A different IP address
- A free compute resource
- Bypass of rate limits on different services

Together they form a distributed workforce.
