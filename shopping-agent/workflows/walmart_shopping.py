"""
workflows/walmart_shopping.py
──────────────────────────────
Pre-defined, fully automated Walmart shopping workflow.

This module can be run standalone (python workflows/walmart_shopping.py)
or called programmatically from main.py with the --workflow flag.

Steps
─────
  1.  Navigate to walmart.com
  2.  Log in (email + password)
  3.  Verify home page
  4.  Navigate to cart
  5.  Remove all items
  6.  Return to home page
  7.  Search for "milk"
  8.  Select a delivery-eligible milk product
  9.  Open product detail page
  10. Add item to cart
  11. Navigate to cart
  12. Click Continue to Checkout

Each step is executed by the appropriate agent and the result is
printed to the console with a Rich-formatted progress display.
"""

from __future__ import annotations

import asyncio
import logging

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule

from agents.auth_agent import AuthAgent
from agents.cart_agent import CartAgent
from agents.checkout_agent import CheckoutAgent
from agents.search_agent import SearchAgent
from config.settings import settings
from mcp_server.client import MCPClient
from mcp_server.server import MCPServer

logger = logging.getLogger(__name__)
console = Console()


async def run_workflow(mcp_client: MCPClient) -> None:
    """Execute the full 12-step Walmart shopping workflow."""

    auth = AuthAgent(mcp_client)
    cart = CartAgent(mcp_client)
    search = SearchAgent(mcp_client)
    checkout = CheckoutAgent(mcp_client)

    steps: list[tuple[str, object, dict]] = [
        ("Steps 1–3: Login & verify home page", auth.run, {}),
        ("Steps 4–6: Clear cart & return home",  cart.run, {}),
        ("Steps 7–10: Search milk, pick delivery item, add to cart",
         search.run, {"query": "milk"}),
        ("Steps 11–12: Cart → Continue to Checkout",
         checkout.run, {}),
    ]

    console.print(Rule("[bold cyan]Walmart Shopping Workflow[/bold cyan]"))
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        for description, agent_fn, kwargs in steps:
            task = progress.add_task(description, total=None)
            try:
                result = await agent_fn(**kwargs)  # type: ignore[operator]
                progress.update(task, description=f"✅ {description}")
                console.print(f"   [dim]{result}[/dim]")
            except Exception as exc:
                progress.update(task, description=f"❌ {description}")
                console.print(f"   [bold red]Error:[/bold red] {exc}")
                logger.exception("Workflow step failed: %s", description)
                raise
            finally:
                progress.stop_task(task)

    console.print()
    console.print(Rule("[bold green]Workflow complete! 🎉[/bold green]"))


async def _main() -> None:
    """Standalone entry-point: start the MCP server then run the workflow."""
    logging.basicConfig(level=settings.LOG_LEVEL)
    settings.validate()

    server = MCPServer()
    await server.start()

    async with MCPClient() as client:
        await run_workflow(client)

    await server.stop()


if __name__ == "__main__":
    asyncio.run(_main())
