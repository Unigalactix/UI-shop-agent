"""
agents/auth_agent.py
─────────────────────
Responsible for logging in to Walmart.com and verifying the home page.

Workflow
────────
  1. Navigate to walmart.com
  2. Click the Sign In button
  3. Enter email → click Continue
  4. Enter password → click Sign In
  5. Confirm landing on the authenticated home page
"""

from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from config.settings import settings
from mcp_server.client import MCPClient

logger = logging.getLogger(__name__)


class AuthAgent(BaseAgent):
    """
    Logs the user into Walmart.com.

    The agent uses the LLM to navigate the login UI, which is useful
    because Walmart occasionally changes the layout of its auth flow.
    """

    SYSTEM_PROMPT = f"""You are a browser automation agent responsible for logging in to Walmart.com.

Your credentials:
  Email:    {settings.WALMART_EMAIL}
  Password: {settings.WALMART_PASSWORD}

Step-by-step task:
1. Navigate to https://www.walmart.com
2. Find and click the "Sign In" link (it's usually in the top-right account area).
3. On the sign-in page, fill in the email field and click Continue (or Next).
4. Fill in the password field and click Sign In.
5. Wait for the home page to load.
6. Verify you are on the home page by checking the URL and page title.
7. Return a confirmation message like: "Successfully logged in. Now on Walmart home page."

Important notes:
- If you encounter a CAPTCHA, report it and stop.
- If the page asks for a phone verification, report it and stop.
- Use get_page_info frequently to understand the current state of the page.
- Use screenshot if you are confused about what's on the page.
- Selectors may vary; try common patterns like [data-automation-id="signin-link"],
  #email, input[type="email"], input[type="password"], [data-automation-id="signin-submit-btn"].
"""

    def __init__(self, mcp_client: MCPClient) -> None:
        super().__init__(mcp_client)

    async def run(self, **kwargs: Any) -> str:
        """Log in to Walmart and return a status message."""
        logger.info("AuthAgent: starting Walmart login")
        result = await self._run_loop(
            "Please log in to Walmart.com using the provided credentials and "
            "confirm that you are on the home page."
        )
        logger.info("AuthAgent: %s", result)
        return result
