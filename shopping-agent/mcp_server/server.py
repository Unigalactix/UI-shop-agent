"""
mcp_server/server.py
─────────────────────
Model Context Protocol (MCP) server that exposes Walmart browser-automation
tools to connected LLM agents.

Architecture
────────────
                ┌───────────────────────────────┐
                │        MCP Server              │
                │  (runs as asyncio HTTP server) │
                │                                │
                │  Tool registry                 │
                │   • navigate                   │
                │   • click_element              │
                │   • fill_field                 │
                │   • get_page_info              │
                │   • screenshot                 │
                │   • wait_for                   │
                │   • scroll                     │
                │   • get_element_text           │
                │   • count_elements             │
                │   • evaluate_js                │
                └──────────────┬────────────────┘
                               │  JSON-RPC 2.0
          ┌────────────────────┼───────────────────────┐
          │                    │                        │
    AuthAgent           SearchAgent             CartAgent
    CheckoutAgent       OrchestratorAgent

Protocol notes
──────────────
We implement a *subset* of the MCP specification:
  • tool/list  – returns available tools with JSON-Schema definitions
  • tool/call  – invokes a tool and returns its result

The transport is plain HTTP JSON-RPC over POST /mcp so that multiple
agents can share one server without managing stdio processes.

References
──────────
  https://spec.modelcontextprotocol.io/specification/
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import web

from browser.playwright_helper import BrowserHelper, BrowserError
from config.settings import settings

logger = logging.getLogger(__name__)


# ── Tool registry ─────────────────────────────────────────────────────────────

class Tool:
    """Describes one MCP tool: its name, description, JSON-Schema params, and handler."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters   # JSON Schema object
        self.handler = handler

    def to_mcp_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                **self.parameters,
            },
        }


class MCPServer:
    """
    Lightweight MCP-compliant HTTP server.

    Each agent process connects via HTTP POST /mcp and sends JSON-RPC
    requests.  The server keeps one shared BrowserHelper so all agents
    operate in the same browser session (same cookies / login state).
    """

    def __init__(self) -> None:
        self._browser = BrowserHelper()
        self._tools: dict[str, Tool] = {}
        self._app = web.Application()
        self._app.router.add_post("/mcp", self._handle_request)
        self._app.router.add_get("/health", self._health)
        self._register_tools()

    # ── HTTP handlers ─────────────────────────────────────────────────────────

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _handle_request(self, request: web.Request) -> web.Response:
        """Dispatch a JSON-RPC 2.0 request to the appropriate tool."""
        try:
            payload = await request.json()
        except Exception:
            return self._error_response(None, -32700, "Parse error")

        req_id = payload.get("id")
        method = payload.get("method", "")
        params = payload.get("params", {})

        try:
            if method == "tool/list":
                result = await self._tool_list()
            elif method == "tool/call":
                result = await self._tool_call(params)
            else:
                return self._error_response(req_id, -32601, f"Unknown method: {method}")
        except BrowserError as exc:
            logger.warning("BrowserError: %s", exc)
            return self._error_response(req_id, -32000, str(exc))
        except Exception as exc:
            logger.error("Unhandled error: %s\n%s", exc, traceback.format_exc())
            return self._error_response(req_id, -32000, f"Internal error: {exc}")

        return web.json_response({"jsonrpc": "2.0", "id": req_id, "result": result})

    @staticmethod
    def _error_response(req_id: Any, code: int, message: str) -> web.Response:
        return web.json_response(
            {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
        )

    # ── Tool dispatch ─────────────────────────────────────────────────────────

    async def _tool_list(self) -> dict[str, Any]:
        return {"tools": [t.to_mcp_dict() for t in self._tools.values()]}

    async def _tool_call(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name: str = params.get("name", "")
        arguments: dict[str, Any] = params.get("arguments", {})

        tool = self._tools.get(tool_name)
        if tool is None:
            raise BrowserError(f"Unknown tool: {tool_name}")

        logger.info("Tool call → %s(%s)", tool_name, arguments)
        result = await tool.handler(**arguments)
        return {"content": [{"type": "text", "text": str(result)}]}

    # ── Tool registration ─────────────────────────────────────────────────────

    def _register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def _register_tools(self) -> None:
        """Register all Playwright-backed tools."""
        b = self._browser   # shorthand

        # navigate ────────────────────────────────────────────────────────────
        self._register(Tool(
            name="navigate",
            description="Navigate the browser to a URL and return the page title.",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "Full URL to navigate to."},
                },
                "required": ["url"],
            },
            handler=b.navigate,
        ))

        # click_element ───────────────────────────────────────────────────────
        self._register(Tool(
            name="click_element",
            description="Click an element on the page using a CSS selector or text.",
            parameters={
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or text selector."},
                },
                "required": ["selector"],
            },
            handler=b.click,
        ))

        # fill_field ──────────────────────────────────────────────────────────
        self._register(Tool(
            name="fill_field",
            description="Fill an input field with the given text.",
            parameters={
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string", "description": "Text to fill in the field."},
                },
                "required": ["selector", "text"],
            },
            handler=b.fill,
        ))

        # type_text ───────────────────────────────────────────────────────────
        self._register(Tool(
            name="type_text",
            description="Type text character-by-character (safer, avoids bot detection).",
            parameters={
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "delay": {
                        "type": "integer",
                        "description": "Delay in ms between keystrokes (default 50).",
                        "default": 50,
                    },
                },
                "required": ["selector", "text"],
            },
            handler=b.type_text,
        ))

        # press_key ───────────────────────────────────────────────────────────
        self._register(Tool(
            name="press_key",
            description="Press a keyboard key such as 'Enter', 'Tab', 'Escape'.",
            parameters={
                "properties": {
                    "key": {"type": "string", "description": "Key name, e.g. 'Enter'."},
                },
                "required": ["key"],
            },
            handler=b.press_key,
        ))

        # wait_for_selector ───────────────────────────────────────────────────
        self._register(Tool(
            name="wait_for_selector",
            description="Wait for a CSS selector to appear on the page.",
            parameters={
                "properties": {
                    "selector": {"type": "string"},
                    "state": {
                        "type": "string",
                        "enum": ["visible", "hidden", "attached"],
                        "default": "visible",
                    },
                },
                "required": ["selector"],
            },
            handler=b.wait_for_selector,
        ))

        # is_visible ──────────────────────────────────────────────────────────
        self._register(Tool(
            name="is_visible",
            description="Return true/false whether the selector is visible.",
            parameters={
                "properties": {
                    "selector": {"type": "string"},
                },
                "required": ["selector"],
            },
            handler=b.is_visible,
        ))

        # get_element_text ────────────────────────────────────────────────────
        self._register(Tool(
            name="get_element_text",
            description="Get the inner text of the first element matching the selector.",
            parameters={
                "properties": {
                    "selector": {"type": "string"},
                },
                "required": ["selector"],
            },
            handler=b.get_text,
        ))

        # count_elements ──────────────────────────────────────────────────────
        self._register(Tool(
            name="count_elements",
            description="Return the number of elements matching a CSS selector.",
            parameters={
                "properties": {
                    "selector": {"type": "string"},
                },
                "required": ["selector"],
            },
            handler=b.count_elements,
        ))

        # get_page_info ───────────────────────────────────────────────────────
        async def _get_page_info() -> dict[str, str]:
            return {
                "url": await b.get_current_url(),
                "title": await b.get_title(),
                "content_snippet": (await b.get_page_content())[:2000],
            }

        self._register(Tool(
            name="get_page_info",
            description="Return the current URL, page title, and a text snippet.",
            parameters={"properties": {}, "required": []},
            handler=_get_page_info,
        ))

        # screenshot ──────────────────────────────────────────────────────────
        self._register(Tool(
            name="screenshot",
            description="Take a screenshot and return base-64 PNG.",
            parameters={
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Filename hint (no extension).",
                        "default": "screenshot",
                    },
                },
                "required": [],
            },
            handler=b.screenshot,
        ))

        # scroll_to_bottom ────────────────────────────────────────────────────
        self._register(Tool(
            name="scroll_to_bottom",
            description="Scroll to the bottom of the page.",
            parameters={"properties": {}, "required": []},
            handler=b.scroll_to_bottom,
        ))

        # evaluate_js ─────────────────────────────────────────────────────────
        self._register(Tool(
            name="evaluate_js",
            description="Execute JavaScript in the page context and return the result.",
            parameters={
                "properties": {
                    "expression": {"type": "string", "description": "JS expression to evaluate."},
                },
                "required": ["expression"],
            },
            handler=b.evaluate,
        ))

        # query_all_texts ─────────────────────────────────────────────────────
        self._register(Tool(
            name="query_all_texts",
            description="Return the text of every element matching a CSS selector.",
            parameters={
                "properties": {
                    "selector": {"type": "string"},
                },
                "required": ["selector"],
            },
            handler=b.query_all_texts,
        ))

    # ── Server lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the browser and the HTTP server."""
        await self._browser.start()
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, settings.MCP_SERVER_HOST, settings.MCP_SERVER_PORT)
        await site.start()
        logger.info(
            "MCP server listening on http://%s:%d/mcp",
            settings.MCP_SERVER_HOST,
            settings.MCP_SERVER_PORT,
        )

    async def stop(self) -> None:
        await self._browser.stop()

    async def run_forever(self) -> None:
        """Convenience method: start and block until cancelled."""
        await self.start()
        try:
            await asyncio.Event().wait()   # block forever
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            await self.stop()


# ── Standalone entry-point ────────────────────────────────────────────────────

async def _main() -> None:
    logging.basicConfig(level=settings.LOG_LEVEL)
    server = MCPServer()
    await server.run_forever()


if __name__ == "__main__":
    asyncio.run(_main())
