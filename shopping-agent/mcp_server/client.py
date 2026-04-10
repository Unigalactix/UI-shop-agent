"""
mcp_server/client.py
─────────────────────
HTTP client for the MCP server.

Agents use this class to call browser tools without needing to know
anything about the underlying transport or Playwright internals.

Example::

    client = MCPClient()
    await client.call("navigate", url="https://www.walmart.com")
    info = await client.call("get_page_info")
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class MCPClientError(RuntimeError):
    """Raised when the MCP server returns an error response."""


class MCPClient:
    """
    Thin JSON-RPC 2.0 client that talks to the MCP server over HTTP.

    One instance per agent is fine; the underlying httpx.AsyncClient is
    reused across calls for connection pooling.
    """

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        _host = host or settings.MCP_SERVER_HOST
        _port = port or settings.MCP_SERVER_PORT
        self._base_url = f"http://{_host}:{_port}/mcp"
        self._http = httpx.AsyncClient(timeout=settings.BROWSER_TIMEOUT / 1000 + 10)
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tools exposed by the MCP server."""
        result = await self._rpc("tool/list", {})
        return result.get("tools", [])

    async def call(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Call a named tool with keyword arguments.

        Returns the *text* content of the first result item, or the raw
        result dict if it cannot be interpreted as plain text.
        """
        result = await self._rpc("tool/call", {"name": tool_name, "arguments": kwargs})
        contents = result.get("content", [])
        if contents and contents[0].get("type") == "text":
            text = contents[0]["text"]
            # Try to parse JSON so callers get native Python objects
            try:
                return json.loads(text.replace("'", '"'))
            except (json.JSONDecodeError, ValueError):
                return text
        return result

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        logger.debug("MCP → %s %s", method, params)
        response = await self._http.post(self._base_url, json=payload)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise MCPClientError(
                f"MCP error [{data['error']['code']}]: {data['error']['message']}"
            )
        logger.debug("MCP ← %s", data.get("result"))
        return data["result"]

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "MCPClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()
