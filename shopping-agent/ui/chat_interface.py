"""
ui/chat_interface.py
─────────────────────
Rich-powered terminal chat interface for the shopping agent.

Layout
──────
  ┌─────────────────────────────────────────────────────┐
  │  🛒 Walmart Shopping Agent  [status bar]            │
  ├─────────────────────────────────────────────────────┤
  │  [chat history – scrollable]                        │
  │                                                     │
  │  You:   search milk                                 │
  │  Agent: 🔍 Searching Walmart for 'milk'…            │
  │  Agent: ✅ Added Horizon Organic Milk ($4.97) …     │
  │                                                     │
  ├─────────────────────────────────────────────────────┤
  │  > _                                                │
  └─────────────────────────────────────────────────────┘

The interface reads user input in a loop and passes it to the
Orchestrator, which yields response chunks that are printed as they
arrive (streaming feel without actual streaming).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import AsyncGenerator

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text
from rich import print as rprint

from agents.orchestrator import Orchestrator, HELP_TEXT
from mcp_server.client import MCPClient
from config.settings import settings

logger = logging.getLogger(__name__)

console = Console()

BANNER = """
[bold cyan]╔══════════════════════════════════════════════════════════╗[/]
[bold cyan]║        🛒  Walmart UI Shop Agent  ·  MCP + Playwright   ║[/]
[bold cyan]╚══════════════════════════════════════════════════════════╝[/]

Type [bold green]help[/] for available commands.   Type [bold red]exit[/] to quit.
"""


class ChatInterface:
    """
    Interactive terminal chat UI.

    Usage::

        async with MCPClient() as client:
            chat = ChatInterface(client)
            await chat.run()
    """

    def __init__(self, mcp_client: MCPClient) -> None:
        self.orchestrator = Orchestrator(mcp_client)
        self._history: list[tuple[str, str]] = []   # (role, message)

    def _print_banner(self) -> None:
        console.print(BANNER)

    def _print_user(self, message: str) -> None:
        console.print(f"\n[bold blue]You:[/]  {message}")

    def _print_agent(self, message: str) -> None:
        # Detect markdown-like content and render it
        if message.startswith("#") or "**" in message or "- " in message:
            console.print("[bold green]Agent:[/]")
            console.print(Markdown(message))
        else:
            console.print(f"[bold green]Agent:[/] {message}")

    def _print_error(self, message: str) -> None:
        console.print(f"[bold red]Error:[/] {message}")

    def _print_divider(self) -> None:
        console.rule(style="dim")

    async def run(self) -> None:
        """Start the interactive chat loop."""
        self._print_banner()

        # Show initial status
        try:
            info = await self.orchestrator.mcp.call("get_page_info")
            if isinstance(info, dict):
                console.print(
                    f"[dim]Browser ready — current page: [italic]{info.get('title', '?')}[/][/dim]"
                )
        except Exception:
            console.print("[dim]Browser ready.[/dim]")

        console.print()

        while True:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: Prompt.ask("[bold cyan]You[/]"),
                )
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "bye"):
                console.print("[dim]Goodbye! 👋[/dim]")
                break

            self._history.append(("user", user_input))
            self._print_user(user_input)

            # Stream agent responses
            try:
                async for chunk in self.orchestrator.handle(user_input):
                    self._print_agent(chunk)
                    self._history.append(("agent", chunk))
            except Exception as exc:
                self._print_error(str(exc))
                logger.exception("Error handling message: %s", user_input)

            self._print_divider()

    def print_history(self) -> None:
        """Print the full conversation history."""
        console.print(Rule("Conversation History"))
        for role, message in self._history:
            if role == "user":
                self._print_user(message)
            else:
                self._print_agent(message)
