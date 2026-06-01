# AI Shell Hub

Turn natural language into shell commands. Diagnose errors, analyze shell history, and get command explanations.

## Installation

```bash
pip install ai-shell-hub
ai setup
```

## Usage

```bash
# Natural language to shell command
ai "show disk usage"
ai "find files larger than 100MB"

# Explain a command
ai -e "docker-compose up -d"

# Diagnose an error
ai -f "docker: command not found"

# Analyze shell history
ai -H
```

## Features

| Feature | Free | Pro |
|---------|------|-----|
| NL to command | 1 trial | Unlimited |
| Error diagnosis | ✅ | ✅ |
| Command classification | ✅ | ✅ |
| Command explanation | ❌ | ✅ |
| Shell history analysis | ❌ | ✅ |
| Web search diagnosis | ❌ | ✅ |

## Pricing

| Plan | Price | Scope |
|------|-------|-------|
| **Bundle** (recommended) | **$10 USDT** | All 4 tools |
| Shell Hub Pro | $7 USDT | This tool only |

Payment: USDT (ERC20) — `0xafc32581a9e4ea30aa03cb8ef5879c2366d35f46`

After payment, run: `ai claim <tx_hash>`

## Configuration

```bash
ai --config
```

Requires OpenAI API key. Supports OpenAI, Anthropic, Ollama.

## License

MIT
