"""Runs the actual scrape when the GUI's Start button is clicked.

Called from a plain threading.Thread spawned by the GUI (see gui.py). The
real Playwright work is scheduled onto the AutomationLoop's dedicated event
loop/thread; this function just blocks (in its own throwaway thread) until
that work completes, forwarding progress via `event_queue`.
"""

from __future__ import annotations

import queue
import threading

from app.scraper.results_panel import collect_all_cards
from app.scraper.listing_detail import extract_listing
from app.scraper.keyword_reader import read_current_keyword
from app.enrichment.website_crawler import enrich_listings
from app.enrichment.image_downloader import download_photos


def run_scrape_in_thread(
    page_ref: dict,
    keyword: str | None,
    event_queue: "queue.Queue",
    stop_flag: threading.Event,
    existing_urls: set[str] | None = None,
) -> None:
    automation = page_ref["automation"]
    page = page_ref["page"]

    future = automation.submit(_scrape_coro(page, keyword, event_queue, stop_flag, existing_urls or set()))
    try:
        future.result()
    except Exception as exc:  # surfaced in the GUI's progress log
        event_queue.put({"type": "error", "message": str(exc)})
    finally:
        event_queue.put({"type": "done"})


async def _scrape_coro(page, keyword, event_queue, stop_flag, existing_urls: set[str]) -> None:
    search_url = page.url

    if not keyword:
        keyword = await read_current_keyword(page)

    event_queue.put({"type": "log", "message": f"Detected keyword: {keyword or '(none)'}"})
    event_queue.put({"type": "log", "message": "Collecting result cards from the page..."})
    cards = await collect_all_cards(page)
    event_queue.put({"type": "log", "message": f"Found {len(cards)} results total on page."})

    new_cards = [c for c in cards if c.maps_url not in existing_urls]
    skipped_count = len(cards) - len(new_cards)
    if skipped_count > 0:
        event_queue.put({"type": "log", "message": f"Skipping {skipped_count} previously scraped listing(s)."})

    if not new_cards:
        event_queue.put({"type": "log", "message": "All visible results have already been scraped."})
        return

    collected = []
    try:
        for card in new_cards:
            if stop_flag.is_set():
                event_queue.put({"type": "log", "message": "Stopped by user."})
                break
            try:
                listing = await extract_listing(page, card, keyword)
                listing.id = len(existing_urls) + len(collected) + 1
            except Exception as exc:
                event_queue.put({"type": "log", "message": f"Skipped '{card.name}': {exc}"})
                continue
            collected.append(listing)
            event_queue.put({"type": "listing", "listing": listing})

        # Second pass: visit websites for email/social data
        if collected and not stop_flag.is_set():
            event_queue.put({"type": "log", "message": "Enriching with email/social data from websites..."})
            await enrich_listings(collected)
            for index, listing in enumerate(collected):
                event_queue.put({"type": "update", "index": index, "listing": listing})


    finally:
        # Auto-restore browser state to the search results list page so subsequent runs work seamlessly
        if search_url and search_url != page.url:
            try:
                event_queue.put({"type": "log", "message": "Restoring search results panel in browser..."})
                await page.goto(search_url, wait_until="domcontentloaded")
            except Exception:
                pass


