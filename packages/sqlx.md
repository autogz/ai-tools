# AI SQL

Turn natural language into SQL queries. Supports MySQL, PostgreSQL, SQLite.

## Installation

```bash
pip install ai-sqlx
```

## Usage

```bash
# Generate SQL from natural language
ai-sqlx "find users who registered in the last 7 days"

# Specify database dialect
ai-sqlx -d postgres "total orders per customer"

# With schema context
ai-sqlx -s "products(id,name,price,stock)" "items with low inventory"

# Explain the generated SQL
ai-sqlx -e "count products by category"
```

## Pricing

| Plan | Price | Scope |
|------|-------|-------|
| **Bundle** (recommended) | **$10 USDT** | All 4 tools |
| SQL Pro | $7 USDT | This tool only |
| Free | $0 | 1 trial | |

Payment: USDT (ERC20) — `0xafc32581a9e4ea30aa03cb8ef5879c2366d35f46`

After payment, run: `ai-sqlx claim <tx_hash>`

## Configuration

```bash
ai-sqlx --config
```

Requires OpenAI API key.

## License

MIT
