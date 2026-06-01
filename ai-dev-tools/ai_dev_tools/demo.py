"""
Demo command — shows all 5 tools working together in one unified demo.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.syntax import Syntax

console = Console()


def run_demo():
    """Run a comprehensive demo of all AI dev tools."""
    console.clear()

    console.print(Panel.fit(
        "[bold blue]AI Dev Tools Bundle[/bold blue] — Complete Demo\n"
        "5 professional AI developer tools in one CLI",
        border_style="blue"
    ))
    console.print()

    # Tool 1: PR Review
    console.print("[bold cyan]1. ai-pr-review  — AI Code Review[/bold cyan]")
    console.print("   Automated PR reviews with security pattern scanning")
    code = Syntax(
        "# Review a PR URL\npr-review https://github.com/owner/repo/pull/123\n\n"
        "# Deep review with LLM\npr-review https://github.com/owner/repo/pull/123 --deep\n\n"
        "# Post review as PR comment\npr-review https://github.com/owner/repo/pull/123 --post",
        "bash", theme="monokai", line_numbers=False
    )
    console.print(Panel(code, border_style="cyan"))
    console.print()

    # Tool 2: SQL
    console.print("[bold green]2. ai-sqlx  — AI SQL Generator[/bold green]")
    console.print("   Turn natural language into SQL queries")
    code = Syntax(
        '# Generate SQL from plain English\naio-sqlx "find users who registered in the last 7 days"\n\n'
        '# Specify dialect\nai-sqlx -d postgres "total orders per customer with amounts"\n\n'
        '# Include schema context\nai-sqlx -s "users(id,name),orders(id,user_id,amount)" "monthly sales"',
        "bash", theme="monokai", line_numbers=False
    )
    console.print(Panel(code, border_style="green"))
    console.print()

    # Tool 3: Image CLI
    console.print("[bold magenta]3. ai-img-cli  — AI Image Generator[/bold magenta]")
    console.print("   Generate images from terminal using DALL-E 3")
    code = Syntax(
        '# Generate an image\naio-img "a cat in space wearing a hoodie"\n\n'
        '# Specify size and output\nai-img -s 1792x1024 "wide landscape" -o landscape.png\n\n'
        '# Batch mode\nai-img "cyberpunk city" "serene mountain lake" --batch',
        "bash", theme="monokai", line_numbers=False
    )
    console.print(Panel(code, border_style="magenta"))
    console.print()

    # Tool 4: DocGen
    console.print("[bold yellow]4. aidocs-cli  — AI Documentation Generator[/bold yellow]")
    console.print("   Auto-generate README, API docs, changelogs from code")
    code = Syntax(
        '# Generate README from any project directory\naidocs-cli /path/to/project\n\n'
        '# Generate changelog\naidocs-cli /path/to/project -t changelog\n\n'
        '# Generate all docs\naidocs-cli /path/to/project -t all',
        "bash", theme="monokai", line_numbers=False
    )
    console.print(Panel(code, border_style="yellow"))
    console.print()

    # Tool 5: Shell Hub
    console.print("[bold red]5. ai-shell-hub  — AI Terminal Assistant[/bold red]")
    console.print("   Natural language to shell commands, error diagnosis")
    code = Syntax(
        '# Natural language to shell command\nai "show disk usage in human readable format"\n\n'
        '# Explain a command\nai -e "docker-compose up -d"\n\n'
        '# Diagnose an error\nai -f "docker: command not found"\n\n'
        '# Analyze shell history\nai -H',
        "bash", theme="monokai", line_numbers=False
    )
    console.print(Panel(code, border_style="red"))
    console.print()

    # Bundle command
    console.print("[bold white]6. aitools launch .  — Full Project Launch Pack[/bold white]")
    console.print("   Analyze any Python project and generate a complete launch kit")
    code = Syntax(
        '# From your project root, run:\naitools launch .\n\n'
        '# Generates in /launch-pack/:\n'
        '#  - README.md, ARCHITECTURE.md, INSTALL.md, USAGE.md\n'
        '#  - SECURITY.md, DISCLAIMER.md\n'
        '#  - GitHub Actions CI/CD workflow\n'
        '#  - PyPI release checklist\n'
        '#  - Social media launch post',
        "bash", theme="monokai", line_numbers=False
    )
    console.print(Panel(code, border_style="white"))
    console.print()

    # Summary table
    t = Table(title="AI Dev Tools Bundle — Tool Overview", box=box.ROUNDED)
    t.add_column("Tool", style="bold")
    t.add_column("Command", style="cyan")
    t.add_column("Purpose")
    t.add_column("Free Tier")

    t.add_row("PR Review", "pr-review", "Automated code review with security scanning", "3/day")
    t.add_row("SQL Gen", "ai-sqlx", "Natural language to SQL queries", "3/day")
    t.add_row("Image Gen", "ai-img", "AI image generation from terminal", "3/day")
    t.add_row("Doc Gen", "aidocs-cli", "Auto-generate project documentation", "3/day")
    t.add_row("Shell Hub", "ai", "Natural language shell commands", "3/day")
    t.add_row("Launch Pack", "aitools launch", "Full project launch kit generator", "3/day")

    console.print(t)
    console.print()

    console.print(Panel(
        "[bold]Ready to unlock the full bundle?[/bold]\n\n"
        "  [bold yellow]Early Access: $10 USDT[/bold yellow] (first 100 users)\n"
        "  Regular: $29  |  Founder: $49\n\n"
        "  Run [bold cyan]aitools price[/bold cyan] for details\n"
        "  Run [bold cyan]aitools claim <tx_hash>[/bold cyan] to activate",
        title="Upgrade", border_style="green"
    ))
