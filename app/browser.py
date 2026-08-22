"""Launches a visible, persistent Google Chrome window pointed at Google Maps.

Uses the user's *installed* Google Chrome (via Playwright's ``channel='chrome'``
mode) rather than Playwright's own bundled Chromium.  This keeps the
distributable installer small — no browser download required.

Persistent context = a real on-disk browser profile (cookies, local storage,
consent choices persist across runs), which:
  1) lets the user search manually in a normal-feeling browser window
  2) reduces "fresh incognito bot" signals compared to a throwaway context

Requirement: Google Chrome must be installed on the end-user's machine.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

# Use persistent LocalAppData directory for frozen executable builds, or local dir for dev
if getattr(sys, "frozen", False):
    USER_DATA_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "PinScout" / "browser_profile"
else:
    USER_DATA_DIR = Path(__file__).parent.parent / ".browser_profile"

MAPS_URL = "https://www.google.com/maps"



async def launch_maps_session() -> tuple[BrowserContext, Page]:
    """Start Playwright, open a persistent Chrome window at Google Maps.

    Uses the system-installed Google Chrome (channel='chrome') so that no
    Playwright browser download is required on the end-user's machine.

    Returns the context and the active page. Caller is responsible for
    eventually closing the context (see main.py's shutdown handling).
    """
    USER_DATA_DIR.mkdir(exist_ok=True)

    playwright = await async_playwright().start()
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        channel="chrome",  # Use system Google Chrome, not bundled Chromium
        headless=False,
        viewport={"width": 1400, "height": 900},
        ignore_default_args=["--no-sandbox"],
        args=[
            # Keep this list minimal — avoid flags that make automation more
            # fingerprintable than a stock Chrome window.
            "--disable-blink-features=AutomationControlled",
            "--test-type",  # Suppresses the 'unsupported command-line flag' banner
        ],
    )

    # Stash the playwright object on the context so we can stop it cleanly
    # later without needing a separate global.
    context._playwright_ref = playwright  # type: ignore[attr-defined]

    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(MAPS_URL, wait_until="domcontentloaded")

    await _dismiss_consent_if_present(page)

    return context, page


async def _dismiss_consent_if_present(page: Page) -> None:
    """Click through the EU cookie-consent interstitial if it appears."""
    try:
        accept_btn = page.get_by_role("button", name="Accept all")
        await accept_btn.click(timeout=4000)
    except Exception:
        # No consent dialog shown (common outside the EU, or already
        # accepted in this persistent profile) — nothing to do.
        pass


async def close_session(context: BrowserContext) -> None:
    playwright = getattr(context, "_playwright_ref", None)
    await context.close()
    if playwright is not None:
        await playwright.stop()
