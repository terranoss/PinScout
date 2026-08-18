"""Scrolls the Google Maps results panel and collects one entry per listing
card (name + place URL at minimum). This is the fast, card-level pass —
see listing_detail.py for the deeper per-listing extraction pass.
"""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass

from playwright.async_api import Page
from app.config import SEL


@dataclass
class CardRef:
    position: int
    name: str
    maps_url: str
    latitude: float | None
    longitude: float | None


LAT_LNG_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")


def _parse_lat_lng(url: str) -> tuple[float | None, float | None]:
    """Google's internal place URLs embed coordinates like ...!3d<lat>!4d<lng>..."""
    m = LAT_LNG_RE.search(url)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


async def collect_all_cards(page: Page, max_results: int | None = None) -> list[CardRef]:
    """Scroll the results feed until all cards are loaded (or max_results hit),
    then return a lightweight reference (name, url, position) for each card.
    """
    feed_selector = SEL.results_feed.get("css_fallback", "div[role='feed']")
    card_link_selector = SEL.result_card.get("name_selector", "a.hfpxzc")
    end_of_list_text = SEL.result_card.get("end_of_list_text", "You've reached the end of the list")

    feed = page.locator(feed_selector)
    try:
        await feed.wait_for(state="visible", timeout=3000)
    except Exception:
        # Feed not visible immediately — try navigating back in history
        try:
            await page.go_back(wait_until="domcontentloaded")
            await feed.wait_for(state="visible", timeout=4000)
        except Exception:
            raise RuntimeError(
                "Search results panel ('div[role=feed]') is not visible on page. "
                "Please perform a search on Google Maps first."
            )


    seen_urls: set[str] = set()
    cards: list[CardRef] = []

    stagnant_rounds = 0
    max_stagnant_rounds = 4  # stop after N scrolls with no new cards

    while True:
        anchors = await feed.locator(card_link_selector).all()

        new_found = False
        for anchor in anchors:
            href = await anchor.get_attribute("href")
            if not href or href in seen_urls:
                continue
            name = await anchor.get_attribute("aria-label") or ""
            lat, lng = _parse_lat_lng(href)

            seen_urls.add(href)
            cards.append(
                CardRef(
                    position=len(cards) + 1,
                    name=name,
                    maps_url=href,
                    latitude=lat,
                    longitude=lng,
                )
            )
            new_found = True

            if max_results and len(cards) >= max_results:
                return cards

        if not new_found:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0

        # Check for the "end of list" marker.
        feed_text = await feed.inner_text()
        if end_of_list_text in feed_text:
            break

        if stagnant_rounds >= max_stagnant_rounds:
            # No new results after several scroll attempts — likely at the
            # end even if the exact end-of-list text wasn't matched (Google
            # sometimes changes this string).
            break

        await _human_like_scroll(page, feed)

    return cards


async def _human_like_scroll(page: Page, feed) -> None:
    """Scroll the feed by a randomized amount with a randomized pause,
    to avoid perfectly uniform/robotic scrolling patterns.
    """
    delta = random.randint(600, 1100)
    await feed.evaluate("(el, d) => el.scrollBy(0, d)", delta)
    await asyncio.sleep(random.uniform(0.5, 1.3))


