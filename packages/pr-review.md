# AI PR Review

Automated code review tool. Pattern-based security scanning for common vulnerabilities. Catch bugs before they ship.

## Installation

```bash
pip install ai-pr-review
```

## Usage

```bash
# Review a PR
pr-review https://github.com/example/repo/pull/123

# Review and post comments (requires GITHUB_TOKEN)
pr-review https://github.com/example/repo/pull/123 --post

# Deep review with LLM
pr-review https://github.com/example/repo/pull/123 --deep
```

## Pricing

| Plan | Price | Scope |
|------|-------|-------|
| **Bundle** (recommended) | **$10 USDT** | All 4 tools |
| PR Review Pro | $7 USDT | This tool only |
| Free | $0 | 1 trial | |

Payment: USDT (ERC20) — `0xafc32581a9e4ea30aa03cb8ef5879c2366d35f46`

After payment, run: `pr-review --claim <tx_hash>`

## Disclaimer

Scan results are advisory only. Not a substitute for professional security audit.
