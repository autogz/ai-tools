"""
Launch pack generator — analyzes a Python project and generates a complete
launch pack including README, architecture diagram, SECURITY.md, CI/CD, etc.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()


def analyze_project(path: str) -> dict:
    """Scan a directory for Python project info."""
    project_path = Path(path).expanduser().resolve()
    if not project_path.exists():
        return {"error": f"Path does not exist: {path}"}
    if not project_path.is_dir():
        return {"error": f"Path is not a directory: {path}"}

    info = {
        "project_name": project_path.name,
        "project_path": str(project_path),
        "python_files": [],
        "total_files": 0,
        "has_pyproject": False,
        "has_setup_py": False,
        "has_setup_cfg": False,
        "has_requirements": False,
        "has_readme": False,
        "has_tests": False,
        "has_src_layout": False,
        "total_lines": 0,
        "dependencies": [],
        "entry_points": [],
        "project_version": "0.1.0",
        "description": "",
    }

    for entry in project_path.rglob("*"):
        if entry.is_file():
            info["total_files"] += 1
            # Skip hidden dirs and venvs
            parts = entry.relative_to(project_path).parts
            if any(p.startswith(".") or p == "__pycache__" or p == "node_modules" or p == ".venv" or p == "venv" for p in parts):
                continue

            if entry.suffix == ".py":
                info["python_files"].append(str(entry.relative_to(project_path)))
                try:
                    info["total_lines"] += len(entry.read_text().splitlines())
                except Exception:
                    pass

            if entry.name == "pyproject.toml":
                info["has_pyproject"] = True
                try:
                    text = entry.read_text()
                    for line in text.splitlines():
                        line = line.strip()
                        if line.startswith("name ="):
                            info["project_name"] = line.split("=")[1].strip().strip('"').strip("'")
                        elif line.startswith("version ="):
                            info["project_version"] = line.split("=")[1].strip().strip('"').strip("'")
                        elif line.startswith("description ="):
                            info["description"] = line.split("=")[1].strip().strip('"').strip("'")
                except Exception:
                    pass

            if entry.name == "setup.py":
                info["has_setup_py"] = True
            if entry.name == "setup.cfg":
                info["has_setup_cfg"] = True
            if entry.name == "requirements.txt":
                info["has_requirements"] = True
                try:
                    info["dependencies"] = [
                        line.strip() for line in entry.read_text().splitlines()
                        if line.strip() and not line.startswith("#") and not line.startswith("-")
                    ]
                except Exception:
                    pass

    info["has_readme"] = (project_path / "README.md").exists()
    info["has_tests"] = any(
        p.name.startswith("test_") or p.name.endswith("_test.py")
        for p in project_path.rglob("*.py")
        if "site-packages" not in str(p)
    )
    info["has_src_layout"] = (project_path / "src").is_dir()

    return info


def generate_readme(info: dict) -> str:
    """Generate README.md content."""
    name = info["project_name"]
    desc = info.get("description") or f"{name} — a Python project"
    files_count = len(info["python_files"])
    loc = info["total_lines"]

    deps_section = ""
    if info["dependencies"]:
        deps_section = "## Dependencies\n\n```\n" + "\n".join(info["dependencies"]) + "\n```\n"

    return f"""# {name}

{desc}

## Overview

- **Python files:** {files_count}
- **Total lines of code:** {loc}
- **Python version:** >=3.10
- **License:** MIT

## Installation

```bash
# Install from source
git clone https://github.com/your-org/{name}.git
cd {name}
pip install -e .

# Or install via pip
pip install {name}
```

## Quick Start

```bash
# Basic usage
{name} --help

# Run the tool
{name} <your-input>
```

{deps_section}
## Project Structure

```
{info['project_path'].split('/')[-1]}/
├── {name}/          # Main package
│   ├── __init__.py
│   └── ...
├── tests/           # Test suite
├── pyproject.toml   # Project config
└── README.md        # This file
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check .
```

## License

MIT
"""


def generate_architecture_mermaid(info: dict) -> str:
    """Generate Mermaid architecture diagram."""
    name = info["project_name"]
    py_files = info["python_files"][:15]  # Limit to 15 files
    modules = [Path(f).stem for f in py_files if not f.startswith("__")]
    modules = list(dict.fromkeys(modules))  # Deduplicate preserve order

    flows = []
    for m in modules[:8]:
        flows.append(f"    {m}[{m}]")
    flow_edges = []
    for i in range(len(flows) - 1):
        flow_edges.append(f"    {flows[i].strip()} --> {flows[i+1].strip()}")

    return f"""```mermaid
graph TD
    CLI[CLI Entry Point] --> Core[Core Engine]
    Core --> Modules[Module System]
    Core --> Utils[Utilities]
    CLI --> Config[Configuration]
    Modules --> Output[Output]

    subgraph "{name} Architecture"
        CLI
        Core
        Modules
        Utils
        Config
        Output
    end

    style CLI fill:#4a90d9,color:#fff
    style Core fill:#50c878,color:#fff
    style Modules fill:#f5a623,color:#fff
```
"""


def generate_security_md(info: dict) -> str:
    return """# Security Policy

## Supported Versions

We currently support the latest stable release with security updates.

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability,
please follow these steps:

1. **Do not** open a public GitHub issue
2. Email us at security@ai-dev-tools.com
3. Provide detailed information about the vulnerability
4. Allow up to 48 hours for initial response

We will acknowledge receipt, investigate, and deploy a fix as soon as possible.

## Security Best Practices

- Always use the latest version
- Review dependencies regularly
- Run security scans as part of CI/CD
- Never commit API keys or secrets
- Use environment variables for configuration

## Responsible Disclosure

We appreciate responsible disclosure of security issues. We will credit
researchers who responsibly report vulnerabilities.
"""


def generate_disclaimer_md() -> str:
    return """# Disclaimer

## General Disclaimer

This software is provided "as is", without warranty of any kind, express or
implied, including but not limited to the warranties of merchantability,
fitness for a particular purpose, and noninfringement.

## No Liability

In no event shall the authors or copyright holders be liable for any claim,
damages, or other liability, whether in an action of contract, tort, or
otherwise, arising from, out of, or in connection with the software or the
use or other dealings in the software.

## AI-Generated Content

This tool uses AI models to generate content. The generated content:

- Should be reviewed by a human before use
- May contain inaccuracies or errors
- Is not a substitute for professional advice
- Should not be used in safety-critical systems without verification

## Third-Party Services

This tool may interact with third-party services (e.g., GitHub, OpenAI).
Users are responsible for complying with the terms of service of any
third-party services they use with this tool.

## Usage at Your Own Risk

By using this software, you acknowledge that you have read this disclaimer
and agree to use the software at your own risk.
"""


def generate_github_actions(info: dict) -> str:
    name = info["project_name"]
    return f"""name: CI/CD

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]
  release:
    types: [ published ]

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{{{ matrix.python-version }}}}
      uses: actions/setup-python@v5
      with:
        python-version: ${{{{ matrix.python-version }}}}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
        pip install pytest pytest-cov black ruff

    - name: Lint with ruff
      run: ruff check .

    - name: Format check with black
      run: black --check .

    - name: Test with pytest
      run: pytest --cov=./ --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3

  publish:
    needs: test
    if: github.event_name == 'release' && github.event.action == 'published'
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.12"

    - name: Install build tools
      run: |
        python -m pip install --upgrade pip
        pip install build twine

    - name: Build package
      run: python -m build

    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{{{ secrets.PYPI_API_TOKEN }}}}
      run: twine upload dist/*
"""


def generate_pypi_release_checklist() -> str:
    return """# PyPI Release Checklist

## Pre-Release

- [ ] All tests pass: `pytest`
- [ ] Code is formatted: `black .`
- [ ] No lint errors: `ruff check .`
- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG.md updated
- [ ] README.md is current
- [ ] All dependencies are listed in `pyproject.toml`
- [ ] Security scan completed

## Build

- [ ] Clean previous builds: `rm -rf dist/`
- [ ] Build package: `python -m build`
- [ ] Verify sdist: `tar tzf dist/*.tar.gz`
- [ ] Verify wheel: `unzip -l dist/*.whl`

## TestPyPI (optional)

- [ ] Upload to TestPyPI: `twine upload --repository testpypi dist/*`
- [ ] Install from TestPyPI: `pip install --index-url https://test.pypi.org/simple/ <package-name>`
- [ ] Run smoke tests

## PyPI Release

- [ ] Upload to PyPI: `twine upload dist/*`
- [ ] Verify on PyPI: `pip install <package-name>`
- [ ] Smoke test the installed package
- [ ] Tag release in git: `git tag v<version> && git push --tags`

## Post-Release

- [ ] Announce on social media
- [ ] Update documentation if needed
- [ ] Monitor for issues
- [ ] Celebrate!
"""


def generate_social_launch_post(info: dict) -> str:
    name = info["project_name"]
    desc = info.get("description") or f"Check out {name}!"

    return f"""We just shipped {name} v{info['project_version']}!

{desc}

Key features:
- Clean CLI interface
- Python 3.10+ support
- MIT licensed

Install: pip install {name}
GitHub: https://github.com/your-org/{name}

#Python #OpenSource #DevTools #AI
"""


def generate_install_instructions(info: dict) -> str:
    name = info["project_name"]
    return f"""# Installation Guide

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

## Install from PyPI (Recommended)

```bash
pip install {name}
```

## Install from Source

```bash
git clone https://github.com/your-org/{name}.git
cd {name}
pip install -e .
```

## Verify Installation

```bash
{name} --help
```

## Optional Dependencies

Some features may require additional setup (API keys, etc.).
Check the README for details.
"""


def generate_usage_examples(info: dict) -> str:
    name = info["project_name"]
    return f"""# Usage Examples

## Basic Usage

```bash
# Show help
{name} --help

# Run with default options
{name} <input>

# Specify output format
{name} --output json
```

## Advanced Examples

```bash
# With verbose logging
{name} --verbose

# Save output to file
{name} --output report.md

# Use custom configuration
{name} --config
```

## Integration

```python
# Use as a Python library
from {name.replace('-', '_')} import Client

client = Client()
result = client.run("your input")
print(result)
```

## Automation

```bash
# In CI/CD pipeline
{name} --ci-mode

# Batch processing
for file in ./inputs/*; do
    {name} "$file" --output "./outputs/$(basename $file).out"
done
```
"""


def generate_launch_pack(project_path: str, output_dir: str = None) -> dict:
    """Generate full launch pack for a project."""
    info = analyze_project(project_path)

    if "error" in info:
        return info

    project_name = info["project_name"]

    # Determine output directory
    if output_dir:
        launch_dir = Path(output_dir) / "launch-pack"
    else:
        launch_dir = Path(project_path) / "launch-pack"

    launch_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Generate README.md
    readme = generate_readme(info)
    (launch_dir / "README.md").write_text(readme)
    results["README.md"] = str(launch_dir / "README.md")

    # Generate architecture diagram
    arch = generate_architecture_mermaid(info)
    (launch_dir / "ARCHITECTURE.md").write_text(arch)
    results["ARCHITECTURE.md"] = str(launch_dir / "ARCHITECTURE.md")

    # Generate install instructions
    install = generate_install_instructions(info)
    (launch_dir / "INSTALL.md").write_text(install)
    results["INSTALL.md"] = str(launch_dir / "INSTALL.md")

    # Generate usage examples
    usage = generate_usage_examples(info)
    (launch_dir / "USAGE.md").write_text(usage)
    results["USAGE.md"] = str(launch_dir / "USAGE.md")

    # Generate SECURITY.md
    security = generate_security_md(info)
    (launch_dir / "SECURITY.md").write_text(security)
    results["SECURITY.md"] = str(launch_dir / "SECURITY.md")

    # Generate DISCLAIMER.md
    disclaimer = generate_disclaimer_md()
    (launch_dir / "DISCLAIMER.md").write_text(disclaimer)
    results["DISCLAIMER.md"] = str(launch_dir / "DISCLAIMER.md")

    # Generate GitHub Actions workflow
    workflow = generate_github_actions(info)
    workflow_dir = launch_dir / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "ci.yml").write_text(workflow)
    results["ci.yml"] = str(workflow_dir / "ci.yml")

    # Generate PyPI release checklist
    checklist = generate_pypi_release_checklist()
    (launch_dir / "PYPI_RELEASE_CHECKLIST.md").write_text(checklist)
    results["PYPI_RELEASE_CHECKLIST.md"] = str(launch_dir / "PYPI_RELEASE_CHECKLIST.md")

    # Generate social launch post
    social = generate_social_launch_post(info)
    (launch_dir / "SOCIAL_LAUNCH.md").write_text(social)
    results["SOCIAL_LAUNCH.md"] = str(launch_dir / "SOCIAL_LAUNCH.md")

    results["project"] = info
    results["launch_dir"] = str(launch_dir)

    return results


def diagnose_project(path: str) -> dict:
    """Analyze a repo and give 5 improvement suggestions."""
    info = analyze_project(path)
    if "error" in info:
        return info

    suggestions = []
    project_path = Path(info["project_path"])

    # Suggestion 1: Missing tests
    if not info["has_tests"]:
        suggestions.append({
            "priority": "High",
            "area": "Testing",
            "title": "No test suite detected",
            "detail": "Add unit tests using pytest to ensure code reliability. Create a tests/ directory with test files.",
        })
    else:
        suggestions.append({
            "priority": "Medium",
            "area": "Testing",
            "title": "Consider increasing test coverage",
            "detail": "Tests exist but coverage may be low. Aim for 80%+ coverage with pytest-cov.",
        })

    # Suggestion 2: Missing README
    if not info["has_readme"]:
        suggestions.append({
            "priority": "High",
            "area": "Documentation",
            "title": "Missing README.md",
            "detail": "A README helps users understand your project. Add installation instructions, usage examples, and API docs.",
        })
    else:
        suggestions.append({
            "priority": "Low",
            "area": "Documentation",
            "title": "Review existing README",
            "detail": "Ensure README includes installation, usage examples, and contribution guidelines.",
        })

    # Suggestion 3: Missing pyproject.toml or setup.py
    if not info["has_pyproject"] and not info["has_setup_py"]:
        suggestions.append({
            "priority": "High",
            "area": "Packaging",
            "title": "No package configuration found",
            "detail": "Add a pyproject.toml to make your project pip-installable and publishable to PyPI.",
        })
    else:
        suggestions.append({
            "priority": "Medium",
            "area": "Packaging",
            "title": "Consider modern packaging standards",
            "detail": "If using setup.py, consider migrating to pyproject.toml for modern Python packaging.",
        })

    # Suggestion 4: Code organization
    if info["total_files"] > 50:
        suggestions.append({
            "priority": "Medium",
            "area": "Structure",
            "title": "Large project — consider modularization",
            "detail": f"Your project has {info['total_files']} files. Consider organizing into subpackages by feature.",
        })
    else:
        py_files = info["python_files"]
        if len(py_files) > 1 and not any("cli" in f for f in py_files):
            suggestions.append({
                "priority": "Medium",
                "area": "Structure",
                "title": "No CLI entry point detected",
                "detail": "Add a CLI interface using typer or argparse for better usability. Define entry_points in pyproject.toml.",
            })
        else:
            suggestions.append({
                "priority": "Low",
                "area": "Structure",
                "title": "Consider adding type hints",
                "detail": "Add Python type hints to improve code readability and enable static analysis with mypy.",
            })

    # Suggestion 5: CI/CD
    has_ci = any(
        (project_path / ".github" / "workflows").exists(),
    )
    if not has_ci:
        suggestions.append({
            "priority": "Medium",
            "area": "CI/CD",
            "title": "No CI/CD pipeline configured",
            "detail": "Add GitHub Actions for automated testing and linting. This ensures code quality on every PR.",
        })
    else:
        suggestions.append({
            "priority": "Low",
            "area": "CI/CD",
            "title": "Add PyPI auto-publishing to CI/CD",
            "detail": "Configure GitHub Actions to automatically publish to PyPI when a release is tagged.",
        })

    return {
        "project": info["project_name"],
        "path": path,
        "files": info["total_files"],
        "python_files": len(info["python_files"]),
        "lines_of_code": info["total_lines"],
        "suggestions": suggestions[:5],
    }
