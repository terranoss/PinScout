"""Reads the current active search term from the Google Maps search box, URL, or page title."""

from __future__ import annotations

import re
import urllib.parse
from playwright.async_api import Page
from app.config import SEL

SEARCH_INPUT_SELECTORS = [
    "input#searchboxinput",
    "input[name='q']",
    "input.searchboxinput",
    "input[aria-label*='Search']",
]

URL_KEYWORD_RE = re.compile(r"/maps/search/([^/@?]+)", re.IGNORECASE)


async def read_current_keyword(page: Page) -> str | None:
    """Read the active search term using input box, URL, or page title fallbacks."""
    # 1. Try input elements
    for sel in [SEL.search.get("input_selector"), *SEARCH_INPUT_SELECTORS]:
        if not sel:
            continue
        try:
            input_el = page.locator(sel).first
            if await input_el.count() > 0:
                val = await input_el.input_value(timeout=1500)
                if val and val.strip():
                    return val.strip()
        except Exception:
            pass

    # 2. Try URL regex parsing (e.g. /maps/search/Restaurants/@...)
    try:
        url = page.url
        m = URL_KEYWORD_RE.search(url)
        if m:
            raw_kw = m.group(1)
            decoded = urllib.parse.unquote_plus(raw_kw).strip()
            if decoded and decoded.lower() != "maps":
                return decoded
    except Exception:
        pass

    # 3. Try Page Title fallback (e.g. "Restaurants - Google Maps")
    try:
        title = await page.title()
        if title:
            clean_title = title.replace(" - Google Maps", "").replace(" – Google Maps", "").strip()
            if clean_title and clean_title.lower() != "google maps":
                return clean_title
    except Exception:
        pass

    return None

