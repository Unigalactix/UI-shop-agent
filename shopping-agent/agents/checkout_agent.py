"""
agents/checkout_agent.py
─────────────────────────
Navigates to the Walmart cart and clicks "Continue to Checkout".
"""

from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from mcp_server.client import MCPClient

logger = logging.getLogger(__name__)


class CheckoutAgent(BaseAgent):
    """
    Initiates checkout from the cart page.

    The agent clicks "Continue to Checkout" and reports what page it
    lands on (typically the checkout/payment page).
    """

    SYSTEM_PROMPT = """You are a browser automation agent responsible for initiating checkout on Walmart.com.

Your tasks:
1. Navigate to https://www.walmart.com/cart
2. Verify there is at least one item in the cart. If the cart is empty, report it and stop.
3. Find the "Continue to checkout" button. Common selectors:
   [data-automation-id="checkout-btn"], button[aria-label*="Continue to checkout"],
   [data-testid="cart-checkout-button"], a[href*="checkout"].
4. Click the button.
5. Wait for the checkout page to load (URL will contain /checkout).
6. Report the page you've reached, e.g.:
   "Reached checkout page: <page title>. URL: <url>"

Notes:
- If you are asked to sign in again at checkout, note it and report.
- Do NOT submit payment or place an order.
"""

    def __init__(self, mcp_client: MCPClient) -> None:
        super().__init__(mcp_client)

    async def run(self, **kwargs: Any) -> str:
        """Navigate to cart and click Continue to Checkout."""
        logger.info("CheckoutAgent: initiating checkout")
        result = await self._run_loop(
            "Navigate to the Walmart cart and click 'Continue to checkout'. "
            "Report the page you land on."
        )
        logger.info("CheckoutAgent: %s", result)
        return result
