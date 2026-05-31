# Contributing to AI Tools

Thanks for your interest. This project is maintained by a solo developer.

## How to Contribute

1. Open an issue describing your proposal before writing code.
2. Fork the repository and create a feature branch.
3. Run the verification script: `python3 verify_repo.py` from the repo root.
4. Submit a pull request against the `main` branch.

## Development Setup

Each tool has its own directory and virtual environment:

```bash
cd shell-hub
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## What We Accept

- Bug fixes and security improvements
- Documentation improvements
- Test coverage increases
- Performance optimizations

## What We May Decline

- New tool additions without prior discussion
- Changes that remove safety or security guardrails
- Changes that bypass the license activation system
- Cryptocurrency mining or wallet-related features
