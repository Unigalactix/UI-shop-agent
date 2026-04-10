"""
agents/base_agent.py
─────────────────────
Base class for all LLM agents.

Each agent:
  1. Holds a reference to the MCPClient for browser tool access.
  2. Maintains a conversation history (system prompt + messages).
  3. Calls the configured LLM (OpenAI or Anthropic) to decide which
     browser tool to invoke next.
  4. Loops until the LLM signals completion (no more tool calls).

Design choices
──────────────
* We use OpenAI's *function calling* API (tool use) and Anthropic's
  tool-use API.  Both map naturally to MCP's tool/list schema.
* Each sub-agent focuses on one responsibility (single-responsibility
  principle) so its system prompt is small and precise.
* A hard recursion limit (MAX_ITERATIONS) prevents infinite loops if
  the LLM gets confused.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from config.settings import settings
from mcp_server.client import MCPClient

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 20   # safety cap for LLM ↔ tool loop


class AgentError(RuntimeError):
    """Raised when an agent cannot complete its task."""


class BaseAgent(ABC):
    """
    Abstract base for all shopping agents.

    Subclasses must implement:
      • ``SYSTEM_PROMPT`` – class-level string describing the agent's role.
      • ``run(**kwargs)``  – entry point called by the orchestrator.
    """

    SYSTEM_PROMPT: str = "You are a helpful browser automation agent."

    def __init__(self, mcp_client: MCPClient) -> None:
        self.mcp = mcp_client
        self._tools_cache: list[dict[str, Any]] | None = None
        logger.debug("%s initialised", self.__class__.__name__)

    # ── Tool discovery ────────────────────────────────────────────────────────

    async def _get_tools(self) -> list[dict[str, Any]]:
        """Fetch and cache the tool list from the MCP server."""
        if self._tools_cache is None:
            raw = await self.mcp.list_tools()
            # Reformat MCP tool schema → OpenAI function schema
            self._tools_cache = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["inputSchema"],
                    },
                }
                for t in raw
            ]
        return self._tools_cache

    # ── LLM call ─────────────────────────────────────────────────────────────

    async def _call_llm(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Send *messages* to the configured LLM and return the assistant message.

        Supports OpenAI and Anthropic.
        """
        tools = await self._get_tools()

        if settings.LLM_PROVIDER == "openai":
            return await self._call_openai(messages, tools)
        if settings.LLM_PROVIDER == "anthropic":
            return await self._call_anthropic(messages, tools)
        raise AgentError(f"Unknown LLM provider: {settings.LLM_PROVIDER!r}")

    async def _call_openai(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        from openai import AsyncOpenAI  # lazy import

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        # Normalise to a plain dict
        return {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (msg.tool_calls or [])
            ],
        }

    async def _call_anthropic(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        import anthropic  # lazy import

        # Convert OpenAI-style tool schema to Anthropic format
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]

        # Separate system prompt from the rest
        system_msgs = [m for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] != "system"]
        system_text = system_msgs[0]["content"] if system_msgs else self.SYSTEM_PROMPT

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=4096,
            system=system_text,
            messages=user_msgs,
            tools=anthropic_tools,
        )

        tool_calls = []
        content_text = ""
        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )

        return {"role": "assistant", "content": content_text, "tool_calls": tool_calls}

    # ── Agentic loop ──────────────────────────────────────────────────────────

    async def _run_loop(self, user_message: str) -> str:
        """
        Run the ReAct-style agent loop:

          1. Send user_message + system prompt to LLM.
          2. If LLM returns tool calls → execute each via MCP, append results.
          3. Repeat until LLM returns no tool calls (= task complete).
          4. Return the final text response.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        for iteration in range(MAX_ITERATIONS):
            logger.debug("[%s] iteration %d", self.__class__.__name__, iteration)
            response = await self._call_llm(messages)
            messages.append(response)

            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                # LLM has finished – return its text
                return response.get("content", "Done.")

            # Execute every tool call requested by the LLM
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                logger.info("[%s] → %s(%s)", self.__class__.__name__, tool_name, arguments)
                try:
                    result = await self.mcp.call(tool_name, **arguments)
                except Exception as exc:
                    result = f"ERROR: {exc}"
                    logger.warning("[%s] tool error: %s", self.__class__.__name__, exc)

                # Append tool result back to conversation
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    }
                )

        raise AgentError(
            f"{self.__class__.__name__} exceeded MAX_ITERATIONS ({MAX_ITERATIONS})"
        )

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def run(self, **kwargs: Any) -> str:
        """Execute the agent's task and return a human-readable result."""
