#!/usr/bin/env python3
"""
AI Dev Tools Bundle — Unified CLI Entry Point
==============================================
5 professional AI developer tools under one CLI.

Usage:
  aitools              Show help and free run status
  aitools demo         Show a demo of all tools working together
  aitools price        Show pricing plans with Early Access urgency
  aitools claim <tx>   Verify USDT payment and activate bundle
  aitools launch .     Analyze current project, generate launch pack
  aitools diagnose <p> Analyze repo and give 5 improvement suggestions
"""
import sys
import os
import json
import hashlib
import urllib.parse
import urllib.request
import asyncio
from pathlib import Path
from datetime import datetime, date
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box
from rich.syntax import Syntax

from . import __version__, VERSION
from .tracker import (
    load_tracker, get_remaining, record_run, is_paid,
    activate_bundle, get_first_100_count, USDT_ADDRESS,
    USDT_CONTRACT, DAILY_LIMIT, PRICING,
)
from .demo import run_demo
from .pricing import show_pricing
from .launcher import generate_launch_pack, diagnose_project

console = Console()

BANNER = r"""
    ___    ________  _______  ___      ___   ___
   /   |  /  _/ __ \/ ___/ / / / | /| / /  / _ \
  / /| |  / // / / /\__ \/ / /| |/ |/ /  / ___/
 / ___ |_/ // /_/ /___/ / /_/ |__/|__/  /_/
/_/  |_/___/\____//____/\____/           v{ver}

   AI Dev Tools Bundle — 5 Tools, One CLI
""".format(ver=VERSION)


def show_status():
    """Show welcome message with remaining run count."""
    remaining = get_remaining()
    paid = is_paid()
    first_100 = get_first_100_count()
    early_left = max(0, PRICING["early_access"]["slots"] - first_100)

    console.print(BANNER)

    if paid:
        console.print(Panel(
            "[bold green]Bundle activated![/bold green] Unlimited runs on all tools.\n"
            "Run [cyan]aitools demo[/cyan] to see what's available.",
            border_style="green", title="Status"
        ))
    else:
        if remaining > 0:
            console.print(Panel(
                f"[bold]Free tier:[/bold] {remaining}/{DAILY_LIMIT} runs remaining today\n"
                "Try [cyan]aitools diagnose .[/cyan] or [cyan]aitools launch .[/cyan]",
                border_style="blue", title="Free Trial"
            ))
        else:
            console.print(Panel(
                "[bold yellow]Free runs exhausted for today.[/bold yellow]\n"
                f"Run [bold cyan]aitools price[/bold cyan] to see upgrade options.\n"
                f"[dim]Early Access $10 — only {early_left} slots left![/dim]",
                border_style="yellow", title="Upgrade Required"
            ))

    # Quick reference
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("Command", style="cyan", width=22)
    t.add_column("Description", style="white")

    t.add_row("aitools demo", "Show a demo of all tools working together")
    t.add_row("aitools price", "Show pricing with Early Access urgency")
    t.add_row("aitools claim <tx>", "Verify USDT payment and activate bundle")
    t.add_row("aitools launch .", "Generate full project launch pack")
    t.add_row("aitools diagnose .", "Get 5 improvement suggestions (free)")

    console.print(t)
    console.print()

    if not paid and remaining > 0:
        remaining_txt = "run" if remaining == 1 else "runs"
        console.print(
            f"[dim]You have {remaining} free {remaining_txt} remaining today. "
            f"Run [bold]aitools price[/bold] when you're ready to upgrade.[/dim]"
        )


def cmd_demo():
    """Run the demo command."""
    paid = is_paid()
    remaining = get_remaining()

    if not paid and remaining <= 0:
        first_100 = get_first_100_count()
        early_left = max(0, PRICING["early_access"]["slots"] - first_100)
        console.print(Panel(
            "[bold yellow]Free runs exhausted for today.[/bold yellow]\n\n"
            f"Early Access pricing: $10 USDT (only {early_left} of 100 slots remain)\n"
            "Regular price: $29  |  Founder: $49\n\n"
            "Run [bold cyan]aitools price[/bold cyan] for details\n"
            "Run [bold cyan]aitools claim <tx_hash>[/bold cyan] to activate",
            title="Upgrade Required", border_style="yellow"
        ))
        return

    run_demo()
    if not paid:
        record_run()
        rem = get_remaining()
        console.print(f"\n[dim]Free runs remaining today: {rem}/{DAILY_LIMIT}[/dim]")


def cmd_price():
    """Show pricing command."""
    show_pricing()


def cmd_claim(tx_hash: str):
    """Verify USDT payment and activate bundle."""
    if not tx_hash:
        console.print("[yellow]Usage: aitools claim <transaction_hash>[/yellow]")
        console.print("After sending USDT to the bundle address, provide the TxID.")
        console.print(f"  Address: {USDT_ADDRESS}")
        return

    tx_hash = tx_hash.strip()
    # Extract from URL if needed
    if tx_hash.startswith("https://etherscan.io/tx/"):
        tx_hash = tx_hash.split("/tx/")[1].split("?")[0]
    elif tx_hash.startswith("https://"):
        parts = tx_hash.rstrip("/").split("/")
        tx_hash = parts[-1] if parts else tx_hash
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash

    console.print(f"[bold blue]Verifying transaction:[/bold blue] {tx_hash[:20]}...{tx_hash[-6:]}")
    console.print()

    # Query Etherscan
    api_key = os.environ.get("ETHERSCAN_API_KEY", "")

    with console.status("[bold blue]Querying blockchain...", spinner="dots"):
        try:
            params = urllib.parse.urlencode({
                "chainid": 1,
                "module": "account",
                "action": "tokentx",
                "address": USDT_ADDRESS,
                "contractaddress": USDT_CONTRACT,
                "sort": "desc",
                "apikey": api_key,
            })
            url = f"https://api.etherscan.io/v2/api?{params}"
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            console.print(f"[red]Error querying blockchain: {e}[/red]")
            console.print("Please try again or contact support.")
            return

    found_tx = None
    for tx in data.get("result", []):
        if tx.get("hash", "").lower() == tx_hash.lower():
            found_tx = tx
            break

    if not found_tx:
        console.print("[red]Transaction not found.[/red]")
        console.print("Please verify:")
        console.print("  1. The transaction hash is correct")
        console.print("  2. Payment was sent to the correct address")
        console.print("  3. The transaction has been confirmed on-chain")
        console.print(f"\n  Our address: [yellow]{USDT_ADDRESS}[/yellow]")
        return

    to_addr = found_tx.get("to", "").lower()
    if to_addr != USDT_ADDRESS.lower():
        console.print("[red]This transaction was not sent to our address.[/red]")
        return

    amount = int(found_tx.get("value", 0)) / 10**6
    sender = found_tx.get("from", "")

    # Match pricing
    price_tiers = {10.0: "early_access", 29.0: "regular", 49.0: "founder"}
    matched_tier = None
    matched_price = None

    for price, tier in price_tiers.items():
        if abs(amount - price) / price <= 0.05:
            matched_tier = tier
            matched_price = price
            break

    if not matched_tier:
        console.print(f"[yellow]Received ${amount:.2f} USDT, which doesn't match our pricing ($10/$29/$49).[/yellow]")
        console.print("Please contact support for manual activation.")
        return

    # Activate
    raw = f"{tx_hash}-{sender}-{matched_tier}-{USDT_ADDRESS}"
    code = "BUNDLE-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

    activate_bundle()

    # Record first 100
    first_100_count = get_first_100_count()

    console.print()
    console.print(Panel(
        f"[bold green]Bundle activated successfully![/bold green]\n\n"
        f"  Product: AI Dev Tools Bundle ({matched_tier.title()})\n"
        f"  Amount:  ${amount:.2f} USDT\n"
        f"  Activation Code: [bold]{code}[/bold]\n\n"
        f"All 5 tools are now unlocked with unlimited runs.\n"
        f"Run [bold cyan]aitools demo[/bold cyan] to get started.\n\n"
        f"[dim]Early Access slot: #{first_100_count} of {PRICING['early_access']['slots']}[/dim]",
        title="Activation Complete", border_style="green"
    ))


def cmd_launch(project_path: str):
    """Generate launch pack for a project."""
    paid = is_paid()
    remaining = get_remaining()

    if not paid and remaining <= 0:
        first_100 = get_first_100_count()
        early_left = max(0, PRICING["early_access"]["slots"] - first_100)
        console.print(Panel(
            "[bold yellow]Free runs exhausted for today.[/bold yellow]\n\n"
            f"Early Access pricing: $10 USDT (only {early_left} of 100 slots remain)\n"
            "Regular price: $29  |  Founder: $49\n\n"
            "Run [bold cyan]aitools price[/bold cyan] for details",
            title="Upgrade Required", border_style="yellow"
        ))
        return

    if not project_path or project_path == ".":
        project_path = os.getcwd()

    console.print(f"[bold]Analyzing project at:[/bold] {project_path}")
    console.print()

    with console.status("[bold blue]Scanning project structure...", spinner="dots"):
        result = generate_launch_pack(project_path)

    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        return

    launch_dir = result["launch_dir"]
    info = result["project"]

    if not paid:
        record_run()
        rem = get_remaining()
        console.print(f"[dim]Free runs remaining today: {rem}/{DAILY_LIMIT}[/dim]")

    console.print(f"\n[bold green]Launch pack generated![/bold green]")
    console.print(f"  Project: [cyan]{info['project_name']}[/cyan]")
    console.print(f"  Version: {info['project_version']}")
    console.print(f"  Python files: {len(info['python_files'])}")
    console.print(f"  Total LOC: {info['total_lines']}")
    console.print(f"  Launch directory: [cyan]{launch_dir}/[/cyan]")
    console.print()

    # Show generated files
    gen_table = Table(box=box.SIMPLE, show_header=False)
    gen_table.add_column("File", style="cyan", width=30)
    gen_table.add_column("Description", style="white")

    gen_table.add_row("README.md", "Full README with install, usage, and structure docs")
    gen_table.add_row("ARCHITECTURE.md", "Mermaid architecture diagram")
    gen_table.add_row("INSTALL.md", "Installation instructions for all platforms")
    gen_table.add_row("USAGE.md", "Usage examples and integration patterns")
    gen_table.add_row("SECURITY.md", "Security policy and vulnerability reporting")
    gen_table.add_row("DISCLAIMER.md", "Legal disclaimer and liability notice")
    gen_table.add_row(".github/workflows/ci.yml", "GitHub Actions CI/CD pipeline")
    gen_table.add_row("PYPI_RELEASE_CHECKLIST.md", "Step-by-step PyPI release checklist")
    gen_table.add_row("SOCIAL_LAUNCH.md", "Social media launch post template")

    console.print(gen_table)
    console.print()

    console.print(Panel(
        "[bold]Next steps:[/bold]\n\n"
        "  1. Review the generated files in the launch-pack/ directory\n"
        "  2. Customize README.md with your specific details\n"
        "  3. Set up the GitHub Actions workflow\n"
        "  4. Follow the PyPI release checklist to publish\n"
        f"\n[dim]Run [cyan]aitools launch .[/cyan] again after changes to regenerate.[/dim]",
        title="Next Steps", border_style="green"
    ))


def cmd_diagnose(path: str):
    """Analyze repo and give 5 improvement suggestions."""
    paid = is_paid()
    remaining = get_remaining()

    if not paid and remaining <= 0:
        first_100 = get_first_100_count()
        early_left = max(0, PRICING["early_access"]["slots"] - first_100)
        console.print(Panel(
            "[bold yellow]Free runs exhausted for today.[/bold yellow]\n\n"
            f"Early Access pricing: $10 USDT (only {early_left} of 100 slots remain)\n"
            "Regular price: $29  |  Founder: $49\n\n"
            "Run [bold cyan]aitools price[/bold cyan] for details\n"
            "Run [bold cyan]aitools claim <tx_hash>[/bold cyan] to activate",
            title="Upgrade Required", border_style="yellow"
        ))
        return

    if not path or path == ".":
        path = os.getcwd()

    console.print(f"[bold]Diagnosing repository at:[/bold] {path}")
    console.print()

    with console.status("[bold blue]Analyzing project...", spinner="dots"):
        result = diagnose_project(path)

    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        return

    if not paid:
        record_run()
        rem = get_remaining()
        console.print(f"[dim]Free runs remaining today: {rem}/{DAILY_LIMIT}[/dim]")

    console.print()
    console.print(f"[bold]Project:[/bold] {result['project']}")
    console.print(f"  Files: {result['files']} total, {result['python_files']} Python")
    console.print(f"  Lines of code: {result['lines_of_code']}")
    console.print()

    # Show suggestions
    suggestions = result.get("suggestions", [])
    console.print(Panel.fit(
        "[bold]5 Improvement Suggestions[/bold]",
        border_style="cyan"
    ))
    console.print()

    priority_colors = {"high": "red", "medium": "yellow", "low": "dim"}
    for i, s in enumerate(suggestions, 1):
        pri = s.get("priority", "Medium").lower()
        color = priority_colors.get(pri, "white")
        console.print(f"  [bold]{i}. {s['title']}[/bold]  [{color}]{s['priority']}[/{color}]")
        console.print(f"     [dim]Area: {s['area']}[/dim]")
        console.print(f"     {s['detail']}")
        console.print()

    if not paid:
        console.print(Panel(
            "[bold]Want more?[/bold]\n\n"
            "  - [cyan]aitools launch .[/cyan] — Generate full launch pack\n"
            "  - [cyan]aitools price[/cyan] — Unlock unlimited diagnoses\n"
            "  - [cyan]aitools demo[/cyan] — See all tools in action",
            border_style="blue", title="Next Steps"
        ))


def main_entry():
    """Main CLI entry point — parse argv and dispatch."""
    argv = sys.argv[1:] if len(sys.argv) > 1 else []

    if not argv:
        show_status()
        return

    cmd = argv[0]

    if cmd in ("-h", "--help", "help"):
        show_status()
        return

    if cmd in ("-V", "--version", "version"):
        console.print(f"[bold]ai-dev-tools[/bold] v{VERSION}")
        console.print("[dim]AI Dev Tools Bundle — 5 professional AI developer tools[/dim]")
        return

    if cmd == "demo":
        cmd_demo()
        return

    if cmd == "price":
        cmd_price()
        return

    if cmd == "claim":
        tx_hash = argv[1] if len(argv) > 1 else ""
        cmd_claim(tx_hash)
        return

    if cmd == "launch":
        project_path = argv[1] if len(argv) > 1 else "."
        cmd_launch(project_path)
        return

    if cmd == "diagnose":
        path = argv[1] if len(argv) > 1 else "."
        cmd_diagnose(path)
        return

    # Unknown command
    console.print(f"[red]Unknown command: {cmd}[/red]")
    console.print("Run [cyan]aitools --help[/cyan] for available commands.")
    sys.exit(1)


if __name__ == "__main__":
    try:
        main_entry()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)
