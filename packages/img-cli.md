# AI Image CLI

Generate images from your terminal using DALL-E 3. Supports multiple sizes and batch generation.

## Installation

```bash
pip install ai-img-cli
```

## Usage

```bash
# Generate an image
ai-img "a cat in space wearing a hoodie"

# Specify output size
ai-img -s 1792x1024 "wide landscape"

# Save to specific file
ai-img -o output.png "your prompt here"

# View pricing
ai-img -p
```

## Pricing

| Plan | Price | Scope |
|------|-------|-------|
| **Bundle** (recommended) | **$10 USDT** | All 4 tools |
| Image CLI Pro | $4 USDT | This tool only |
| Free | $0 | 1 trial | |

Payment: USDT (ERC20) — `0xafc32581a9e4ea30aa03cb8ef5879c2366d35f46`

After payment, run: `ai-img claim <tx_hash>`

## Requirements

- Python 3.10+
- OpenAI API key with DALL-E 3 access

## License

MIT
