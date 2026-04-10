"""
agents/orchestrator.py
───────────────────────
The Orchestrator is the top-level agent that:

  1. Receives natural-language messages from the user (via the chat UI).
  2. Decides which sub-agent(s) to invoke based on intent.
  3. Delegates work and streams results back to the caller.

Intent routing
──────────────
The orchestrator uses a small LLM call to classify intent into one of:
  • "login"      → AuthAgent
  • "clear_cart" → CartAgent
  • "search"     → SearchAgent  (may include a search query)
  • "checkout"   → CheckoutAgent
  • "workflow"   → run the full predefined workflow
  • "status"     → get current page info via MCP
  • "help"       → return help text

If the user's message is free-form, the orchestrator answers directly
without invoking browser tools (general Q&A mode).
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from agents.auth_agent import AuthAgent
from agents.cart_agent import CartAgent
from agents.checkout_agent import CheckoutAgent
from agents.search_agent import SearchAgent
from mcp_server.client import MCPClient
from config.settings import settings

logger = logging.getLogger(__name__)

HELP_TEXT = """
Available commands
──────────────────
  login           – Log in to Walmart using configured credentials.
  clear cart      – Navigate to cart and remove all items.
  search <term>   – Search for a product and add a delivery-eligible result to cart.
                    e.g. "search milk"
  checkout        – Go to cart and click Continue to Checkout.
  workflow        – Run the complete automated Walmart shopping workflow.
  status          – Show the current browser URL and page title.
  help            – Show this message.
  exit / quit     – Exit the chat.
"""

_INTENT_SYSTEM = """
You are an intent classifier for a Walmart shopping automation system.
Classify the user message into exactly one of these intents:
  login, clear_cart, search, checkout, workflow, status, help, general

If the intent is "search", also extract the search query from the message.

Respond ONLY with JSON:
  {"intent": "<intent>", "query": "<optional search query>"}

Examples:
  "log me in" → {"intent": "login", "query": ""}
  "remove everything from my cart" → {"intent": "clear_cart", "query": ""}
  "find me some milk" → {"intent": "search", "query": "milk"}
  "go to checkout" → {"intent": "checkout", "query": ""}
  "run the full demo" → {"intent": "workflow", "query": ""}
  "what page am I on?" → {"intent": "status", "query": ""}
  "how does this work?" → {"intent": "general", "query": ""}
"""


class Orchestrator:
    """
    Routes user messages to the appropriate sub-agent and yields
    status/result strings for the chat UI to display.
    """

    def __init__(self, mcp_client: MCPClient) -> None:
        self.mcp = mcp_client
        self.auth = AuthAgent(mcp_client)
        self.cart = CartAgent(mcp_client)
        self.search = SearchAgent(mcp_client)
        self.checkout = CheckoutAgent(mcp_client)

    async def handle(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Process a user message and yield one or more response strings.

        The generator pattern lets the chat UI display intermediate
        progress as agents run.
        """
        intent_data = await self._classify_intent(user_message)
        intent = intent_data.get("intent", "general")
        query = intent_data.get("query", "")

        logger.info("Orchestrator intent=%r query=%r", intent, query)

        if intent == "help":
            yield HELP_TEXT
            return

        if intent == "login":
            yield "🔐 Logging in to Walmart…"
            result = await self.auth.run()
            yield result
            return

        if intent == "clear_cart":
            yield "🛒 Navigating to cart and clearing items…"
            result = await self.cart.run()
            yield result
            return

        if intent == "search":
            search_term = query or "milk"
            yield f"🔍 Searching Walmart for '{search_term}'…"
            result = await self.search.run(query=search_term)
            yield result
            return

        if intent == "checkout":
            yield "💳 Proceeding to checkout…"
            result = await self.checkout.run()
            yield result
            return

        if intent == "status":
            info = await self.mcp.call("get_page_info")
            if isinstance(info, dict):
                yield (
                    f"📍 Current page\n"
                    f"   URL:   {info.get('url', '?')}\n"
                    f"   Title: {info.get('title', '?')}"
                )
            else:
                yield str(info)
            return

        if intent == "workflow":
            async for msg in self._run_full_workflow():
                yield msg
            return

        # General / unknown intent – answer without browser tools
        yield await self._general_response(user_message)

    async def _run_full_workflow(self) -> AsyncGenerator[str, None]:
        """
        Execute the complete predefined Walmart shopping workflow:

          1. Log in
          2. Verify home page
          3. Navigate to cart
          4. Clear cart
          5. Return to home
          6. Search for milk
          7. Select delivery-eligible product
          8. Open product detail page
          9. Add to cart
         10. Navigate to cart
         11. Click Continue to Checkout
        """
        steps = [
            ("🔐 Step 1–3: Logging in and verifying home page…",
             self.auth.run, {}),
            ("🛒 Step 4–6: Clearing cart and returning home…",
             self.cart.run, {}),
            ("🔍 Step 7–10: Searching for milk and adding to cart…",
             self.search.run, {"query": "milk"}),
            ("💳 Step 11–12: Navigating to cart and proceeding to checkout…",
             self.checkout.run, {}),
        ]

        for description, agent_fn, kwargs in steps:
            yield description
            result = await agent_fn(**kwargs)
            yield f"   ✅ {result}"

        yield "🎉 Full workflow complete!"

    # ── LLM helpers ───────────────────────────────────────────────────────────

    async def _classify_intent(self, message: str) -> dict:
        """Call the LLM to classify *message* into an intent dict."""
        try:
            if settings.LLM_PROVIDER == "openai":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": _INTENT_SYSTEM},
                        {"role": "user", "content": message},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                )
                raw = response.choices[0].message.content or "{}"
            else:
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                response = await client.messages.create(
                    model=settings.LLM_MODEL,
                    max_tokens=256,
                    system=_INTENT_SYSTEM,
                    messages=[{"role": "user", "content": message}],
                )
                raw = response.content[0].text if response.content else "{}"

            return json.loads(raw)
        except Exception as exc:
            logger.warning("Intent classification failed: %s. Defaulting to 'general'.", exc)
            return {"intent": "general", "query": ""}

    async def _general_response(self, message: str) -> str:
        """Answer a general (non-browser) question using the LLM."""
        try:
            if settings.LLM_PROVIDER == "openai":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant for a Walmart shopping automation system. "
                                "Answer the user's question concisely."
                            ),
                        },
                        {"role": "user", "content": message},
                    ],
                    temperature=0.7,
                )
                return response.choices[0].message.content or "I'm not sure how to help with that."
            else:
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                response = await client.messages.create(
                    model=settings.LLM_MODEL,
                    max_tokens=512,
                    system="You are a helpful assistant for a Walmart shopping automation system.",
                    messages=[{"role": "user", "content": message}],
                )
                return response.content[0].text if response.content else "I'm not sure."
        except Exception as exc:
            return f"(Could not generate response: {exc})"
