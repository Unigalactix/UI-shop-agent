"""
main.py
────────
Entry-point for the UI Shop Agent.

Usage
─────
  # Interactive chat mode (default)
  python main.py

  # Run the fully automated Walmart workflow and exit
  python main.py --workflow

  # Run in headless browser mode
  BROWSER_HEADLESS=true python main.py --workflow

Architecture overview
─────────────────────

  ┌──────────────────────────────────────────────────────────────┐
  │  main.py                                                     │
  │   │                                                          │
  │   ├─► MCPServer  ──────────────────────────────────────────► │
  │   │    │  (HTTP JSON-RPC on localhost:8765)                  │
  │   │    └─► BrowserHelper (Playwright / Chromium)            │
  │   │                                                          │
  │   └─► MCPClient ──────────────────────────────────────────► │
  │        │  (shared by all agents)                             │
  │        ▼                                                     │
  │   Orchestrator                                               │
  │    ├─► AuthAgent       (login)                              │
  │    ├─► CartAgent       (clear cart / checkout nav)          │
  │    ├─► SearchAgent     (search + add to cart)               │
  │    └─► CheckoutAgent   (continue to checkout)               │
  │        │                                                     │
  │        ▼                                                     │
  │   ChatInterface  (Rich terminal UI)                          │
  └──────────────────────────────────────────────────────────────┘

Start-up sequence
─────────────────
  1. Validate environment configuration (.env / env vars).
  2. Start the MCPServer (launches Chromium via Playwright).
  3. Start the MCPClient.
  4a. In --workflow mode: run walmart_shopping.run_workflow().
  4b. In chat mode:       run ChatInterface.run() (interactive loop).
  5. On exit: stop MCPServer, close browser.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from rich.console import Console

from config.settings import settings
from mcp_server.server import MCPServer
from mcp_server.client import MCPClient

console = Console()


def _configure_logging() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy third-party loggers
    for lib in ("httpx", "httpcore", "openai", "anthropic", "playwright"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="shop-agent",
        description="UI chat-based multi-agent Walmart shopping system",
    )
    parser.add_argument(
        "--workflow",
        action="store_true",
        help="Run the predefined 12-step Walmart shopping workflow and exit.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Force headless browser mode (overrides BROWSER_HEADLESS env var).",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip credential validation (for testing without real credentials).",
    )
    return parser.parse_args()


async def _run_chat(mcp_client: MCPClient) -> None:
    """Launch the interactive Rich chat interface."""
    from ui.chat_interface import ChatInterface
    chat = ChatInterface(mcp_client)
    await chat.run()


async def _run_workflow(mcp_client: MCPClient) -> None:
    """Run the fully automated workflow."""
    from workflows.walmart_shopping import run_workflow
    await run_workflow(mcp_client)


async def _main() -> None:
    args = _parse_args()
    _configure_logging()

    # Allow CLI flag to override env setting
    if args.headless:
        settings.BROWSER_HEADLESS = True

    if not args.no_validate:
        try:
            settings.validate()
        except ValueError as exc:
            console.print(f"[bold red]Configuration error:[/bold red] {exc}")
            console.print(
                "\nPlease copy [bold].env.example[/bold] to [bold].env[/bold] "
                "and fill in your credentials."
            )
            sys.exit(1)

    console.print("[dim]Starting MCP server and browser…[/dim]")
    server = MCPServer()
    await server.start()

    try:
        async with MCPClient() as client:
            if args.workflow:
                await _run_workflow(client)
            else:
                await _run_chat(client)
    finally:
        console.print("[dim]Shutting down browser…[/dim]")
        await server.stop()


def run() -> None:
    """Synchronous entry-point registered in pyproject.toml."""
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Goodbye![/dim]")


if __name__ == "__main__":
    run()
