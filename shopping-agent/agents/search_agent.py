"""
agents/search_agent.py
───────────────────────
Handles product search and selection on Walmart.com.

Workflow
────────
  1. Use the search bar to search for a query term.
  2. From the results, identify a product that is eligible for delivery.
  3. Click on the product to open the item-details page.
  4. Add the item to the cart.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from mcp_server.client import MCPClient

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """
    Searches for a product on Walmart, picks a delivery-eligible result,
    opens the product page, and adds the item to the cart.
    """

    SYSTEM_PROMPT = """You are a browser automation agent that searches for products on Walmart.com.

Given a search term, your tasks are:
1. Locate the search bar (selector: input[name="query"] or [data-automation-id="search-bar"]).
2. Clear the field, type the search term, and press Enter.
3. Wait for the search results page to load.
4. Scan the results for a product that shows a "Delivery" or "Ship" badge
   (look for text containing "Delivery", "Ships to", "Get it by").
5. Click on the first delivery-eligible product title/link to open its detail page.
6. On the product detail page, confirm the product name and price.
7. Look for an "Add to cart" button. Common selectors:
   [data-automation-id="add-to-cart-btn"], button[aria-label*="Add to cart"],
   [data-testid="add-to-cart-button"].
8. Click "Add to cart".
9. Wait for the cart confirmation modal or badge update.
10. Return a summary: product name, price, and confirmation it was added to cart.

Notes:
- If no delivery-eligible result is visible in the first row, scroll down to check more.
- Avoid "Pickup only" or "In-store only" products.
- Use get_page_info and get_element_text to read product names and labels.
"""

    def __init__(self, mcp_client: MCPClient) -> None:
        super().__init__(mcp_client)

    async def run(self, query: str = "milk", **kwargs: Any) -> str:
        """
        Search for *query*, add a delivery-eligible product to cart.

        Parameters
        ----------
        query:
            The search term (default: "milk").
        """
        logger.info("SearchAgent: searching for %r", query)
        result = await self._run_loop(
            f"Search Walmart for '{query}', find a delivery-eligible product, "
            f"open its detail page, and add it to the cart."
        )
        logger.info("SearchAgent: %s", result)
        return result
