"""
browser/playwright_helper.py
─────────────────────────────
Low-level Playwright wrapper that the MCP server and agents use.

Design notes
────────────
* A single `BrowserHelper` instance is shared for the lifetime of the
  session so that all agents operate in the same browser context (same
  cookies, same logged-in state, same cart).
* All public methods are *async* and raise `BrowserError` on failure so
  callers can catch a single exception type.
* Screenshots are saved to /tmp/shop_agent_screenshots/ for debugging.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PWTimeoutError,
    async_playwright,
)

from config.settings import settings

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path("/tmp/shop_agent_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class BrowserError(RuntimeError):
    """Raised when a Playwright operation fails."""


class BrowserHelper:
    """
    Async Playwright browser wrapper.

    Usage::

        helper = BrowserHelper()
        await helper.start()
        await helper.navigate("https://www.walmart.com")
        # … perform actions …
        await helper.stop()

    Or use as an async context manager::

        async with BrowserHelper() as helper:
            await helper.navigate("https://www.walmart.com")
    """

    def __init__(self) -> None:
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch Chromium and create a browser context + page."""
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            slow_mo=settings.BROWSER_SLOW_MO,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        self._context.set_default_timeout(settings.BROWSER_TIMEOUT)
        self._page = await self._context.new_page()
        logger.info("Browser started (headless=%s)", settings.BROWSER_HEADLESS)

    async def stop(self) -> None:
        """Close browser and Playwright instance."""
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("Browser stopped")

    async def __aenter__(self) -> "BrowserHelper":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()

    # ── Page helpers ──────────────────────────────────────────────────────────

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserError("Browser not started. Call start() first.")
        return self._page

    # ── Navigation ────────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> str:
        """Navigate to *url* and return the final page title."""
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            title = await self.page.title()
            logger.debug("Navigated to %s  (title=%r)", url, title)
            return title
        except PWTimeoutError as exc:
            raise BrowserError(f"Timeout navigating to {url}") from exc

    async def get_current_url(self) -> str:
        """Return the browser's current URL."""
        return self.page.url

    async def get_title(self) -> str:
        """Return the current page title."""
        return await self.page.title()

    # ── Element interaction ───────────────────────────────────────────────────

    async def click(self, selector: str, timeout: Optional[int] = None) -> None:
        """Click an element identified by *selector*."""
        try:
            await self.page.click(selector, timeout=timeout or settings.BROWSER_TIMEOUT)
            logger.debug("Clicked: %s", selector)
        except PWTimeoutError as exc:
            raise BrowserError(f"Timeout clicking '{selector}'") from exc

    async def fill(self, selector: str, text: str, clear_first: bool = True) -> None:
        """Fill an input field."""
        try:
            if clear_first:
                await self.page.fill(selector, "")
            await self.page.fill(selector, text)
            logger.debug("Filled '%s' with %r", selector, text)
        except PWTimeoutError as exc:
            raise BrowserError(f"Timeout filling '{selector}'") from exc

    async def type_text(self, selector: str, text: str, delay: int = 50) -> None:
        """Type text character-by-character (avoids detection)."""
        try:
            await self.page.type(selector, text, delay=delay)
        except PWTimeoutError as exc:
            raise BrowserError(f"Timeout typing into '{selector}'") from exc

    async def press_key(self, key: str) -> None:
        """Press a keyboard key (e.g. 'Enter', 'Tab')."""
        await self.page.keyboard.press(key)

    async def hover(self, selector: str) -> None:
        """Move the mouse over an element."""
        await self.page.hover(selector)

    # ── Element discovery ─────────────────────────────────────────────────────

    async def wait_for_selector(
        self, selector: str, state: str = "visible", timeout: Optional[int] = None
    ) -> None:
        """Wait until *selector* reaches *state* ('visible', 'hidden', 'attached')."""
        try:
            await self.page.wait_for_selector(
                selector, state=state, timeout=timeout or settings.BROWSER_TIMEOUT
            )
        except PWTimeoutError as exc:
            raise BrowserError(f"Timeout waiting for '{selector}' (state={state})") from exc

    async def is_visible(self, selector: str) -> bool:
        """Return True if the selector is currently visible on the page."""
        try:
            return await self.page.is_visible(selector)
        except Exception:
            return False

    async def get_text(self, selector: str) -> str:
        """Return the inner-text of the first matching element."""
        try:
            return (await self.page.inner_text(selector)).strip()
        except PWTimeoutError as exc:
            raise BrowserError(f"Timeout getting text of '{selector}'") from exc

    async def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Return an attribute value of the first matching element."""
        return await self.page.get_attribute(selector, attribute)

    async def count_elements(self, selector: str) -> int:
        """Return the number of elements matching *selector*."""
        return await self.page.locator(selector).count()

    async def query_all_texts(self, selector: str) -> list[str]:
        """Return inner-text of all matching elements."""
        locator = self.page.locator(selector)
        count = await locator.count()
        return [(await locator.nth(i).inner_text()).strip() for i in range(count)]

    # ── Page-level helpers ────────────────────────────────────────────────────

    async def wait_for_navigation(self, timeout: Optional[int] = None) -> None:
        """Wait for a navigation to complete."""
        await self.page.wait_for_load_state(
            "domcontentloaded", timeout=timeout or settings.BROWSER_TIMEOUT
        )

    async def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the page."""
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)

    async def scroll_into_view(self, selector: str) -> None:
        """Scroll an element into the viewport."""
        await self.page.locator(selector).scroll_into_view_if_needed()

    async def get_page_content(self) -> str:
        """Return a trimmed version of the page's visible text content."""
        return await self.page.evaluate(
            """() => {
                // Remove scripts and styles before extracting text
                const clone = document.body.cloneNode(true);
                clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
                return clone.innerText.replace(/\\s+/g, ' ').trim().slice(0, 8000);
            }"""
        )

    # ── Screenshot ────────────────────────────────────────────────────────────

    async def screenshot(self, name: str = "screenshot") -> str:
        """
        Take a full-page screenshot and return its base-64 encoded PNG.

        The file is also saved under SCREENSHOT_DIR for manual inspection.
        """
        path = SCREENSHOT_DIR / f"{name}.png"
        await self.page.screenshot(path=str(path), full_page=False)
        data = path.read_bytes()
        logger.debug("Screenshot saved: %s", path)
        return base64.b64encode(data).decode()

    # ── Utility ───────────────────────────────────────────────────────────────

    async def sleep(self, seconds: float) -> None:
        """Pause execution (use sparingly)."""
        await asyncio.sleep(seconds)

    async def evaluate(self, expression: str) -> object:
        """Execute arbitrary JavaScript and return the result."""
        return await self.page.evaluate(expression)
