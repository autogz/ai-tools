"""
Pricing display — shows pricing plans with urgency and Early Access slots.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .tracker import USDT_ADDRESS, PRICING, get_first_100_count

console = Console()


def show_pricing():
    """Display pricing with Early Access urgency."""
    first_100_count = get_first_100_count()
    early_remaining = max(0, PRICING["early_access"]["slots"] - first_100_count)

    console.clear()
    console.print(Panel.fit(
        "[bold yellow]AI Dev Tools Bundle[/bold yellow] — Pricing\n"
        "Unlock all 5 professional AI developer tools with one purchase",
        border_style="yellow"
    ))
    console.print()

    # Urgency banner
    if early_remaining > 0:
        console.print(Panel(
            f"[bold yellow]Early Access: $10 USDT[/bold yellow] — "
            f"Only {early_remaining} of {PRICING['early_access']['slots']} slots remaining!\n"
            "Lock in the lowest price forever. Regular price will be $29.",
            border_style="yellow"
        ))
    else:
        console.print(Panel(
            "[bold red]Early Access Sold Out![/bold red]\n"
            "All 100 Early Access slots have been claimed. "
            "Regular pricing of $29 is now in effect.",
            border_style="red"
        ))
    console.print()

    # Pricing table
    t = Table(box=box.ROUNDED, show_header=True)
    t.add_column("Plan", style="bold", width=18)
    t.add_column("Price", style="bold", width=16)
    t.add_column("Features", width=50)

    t.add_row(
        "[yellow]Early Access[/yellow]" if early_remaining > 0 else "[dim]Early Access[/dim]",
        "[bold yellow]$10 USDT[/bold yellow]" if early_remaining > 0 else "[dim]Sold Out[/dim]",
        "All 5 tools: PR Review, SQL Gen, Image Gen,\n"
        "Doc Gen, Shell Hub + Launch Pack. Unlimited runs.\n"
        "Lifetime access with free updates."
    )
    t.add_row(
        "Regular",
        "$29 USDT",
        "Same full bundle. Standard pricing.\n"
        "Lifetime access."
    )
    t.add_row(
        "[bold]Founder[/bold]",
        "[bold]$49 USDT[/bold]",
        "Full bundle + priority support +\n"
        "name in credits + early feature access."
    )

    console.print(t)
    console.print()

    # Payment info
    console.print(Panel(
        "[bold]Payment via USDT (ERC20)[/bold]\n\n"
        f"  Address: [yellow]{USDT_ADDRESS}[/yellow]\n"
        f"  Token:   USDT (ERC20)\n"
        f"  Network: Ethereum\n\n"
        "After sending payment, run:\n"
        "  [bold cyan]aitools claim <your_tx_hash>[/bold cyan]\n\n"
        "System will automatically verify and activate your bundle.\n"
        "All 5 tools will be unlocked immediately.",
        title="How to Pay", border_style="green"
    ))

    console.print()
    console.print("[dim]Questions? Contact: support@ai-dev-tools.com[/dim]")
