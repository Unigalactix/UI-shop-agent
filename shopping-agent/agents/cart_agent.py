"""
agents/cart_agent.py
─────────────────────
Manages the shopping cart:
  • Navigate to the cart page.
  • Remove every item until the cart is empty.
  • Return to the home page.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from mcp_server.client import MCPClient

logger = logging.getLogger(__name__)


class CartAgent(BaseAgent):
    """
    Clears all items from the Walmart cart.

    The LLM is instructed to repeatedly check for remove buttons and
    click them until none remain.
    """

    SYSTEM_PROMPT = """You are a browser automation agent responsible for managing the Walmart shopping cart.

Your task:
1. Navigate to https://www.walmart.com/cart
2. Check how many items are in the cart.
3. If the cart is empty, report "Cart is already empty."
4. If there are items, remove them one by one:
   - Look for a "Remove" button next to each item. Common selectors:
     [data-automation-id="cart-item-remove"], button[aria-label*="Remove"],
     [data-testid="cart-item-remove"], button[class*="remove"].
   - Click Remove, wait for the item to disappear, then repeat.
5. After all items are removed, confirm the cart is empty.
6. Navigate back to https://www.walmart.com (home page).
7. Return a message like: "Cart cleared. X item(s) removed. Now on home page."

Tips:
- After each removal, use get_page_info or count_elements to check remaining items.
- Scroll down if there are many items.
- A cart item count badge (e.g. [data-testid="header-cart-count"]) going to 0 confirms success.
"""

    def __init__(self, mcp_client: MCPClient) -> None:
        super().__init__(mcp_client)

    async def run(self, **kwargs: Any) -> str:
        """Navigate to cart, clear it, return to home page."""
        logger.info("CartAgent: clearing cart")
        result = await self._run_loop(
            "Please navigate to the Walmart cart, remove all items, "
            "and then return to the home page."
        )
        logger.info("CartAgent: %s", result)
        return result

    async def add_item_and_checkout(self) -> str:
        """Navigate to cart after adding an item and proceed to checkout."""
        logger.info("CartAgent: navigating to cart for checkout")
        result = await self._run_loop(
            "Navigate to https://www.walmart.com/cart. "
            "Find and click the 'Continue to Checkout' button. "
            "Report the page you land on."
        )
        logger.info("CartAgent: %s", result)
        return result
