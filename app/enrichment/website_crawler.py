"""Phase 4: for each listing with a website, fetch the homepage (and /contact
if discoverable) and regex out an email address + social profile links.

Uses Playwright's request context (no full browser page needed) for speed —
these are plain HTTP fetches to arbitrary third-party sites, not Google Maps
itself, so no anti-bot pacing concerns here beyond basic politeness.
"""

from __future__ import annotations

import asyncio
import re

from playwright.async_api import async_playwright

from app.models import Listing

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(www\.)?facebook\.com/[^\s\"'<>]+", re.IGNORECASE),
    "twitter": re.compile(r"https?://(www\.)?(twitter|x)\.com/[^\s\"'<>]+", re.IGNORECASE),
    "instagram": re.compile(r"https?://(www\.)?instagram\.com/[^\s\"'<>]+", re.IGNORECASE),
    "youtube": re.compile(r"https?://(www\.)?youtube\.com/[^\s\"'<>]+", re.IGNORECASE),
    "linkedin": re.compile(r"https?://(www\.)?linkedin\.com/(company|in)/[^\s\"'<>]+", re.IGNORECASE),
    "tiktok": re.compile(r"https?://(www\.)?tiktok\.com/@[^\s\"'<>]+", re.IGNORECASE),
    "pinterest": re.compile(r"https?://(www\.)?pinterest\.com/[^\s\"'<>]+", re.IGNORECASE),
}


# Skip Google's own tracking/placeholder domains and common non-business emails.
EMAIL_BLOCKLIST_SUBSTRINGS = ("example.com", "sentry.io", "wixpress.com")

CONCURRENCY_LIMIT = 8
REQUEST_TIMEOUT_MS = 8000


async def enrich_listings(listings: list[Listing]) -> None:
    """Mutates each Listing in place with email/social fields, where found."""
    targets = [l for l in listings if l.website]
    if not targets:
        return

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async with async_playwright() as p:
        request_context = await p.request.new_context()
        try:
            tasks = [_enrich_one(listing, request_context, semaphore) for listing in targets]
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await request_context.dispose()


async def _enrich_one(listing: Listing, request_context, semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        html = await _fetch(request_context, listing.website)
        if not html:
            return

        email_match = EMAIL_RE.search(html)
        if email_match and not any(b in email_match.group(0) for b in EMAIL_BLOCKLIST_SUBSTRINGS):
            listing.email = email_match.group(0)

        for field, pattern in SOCIAL_PATTERNS.items():
            match = pattern.search(html)
            if match:
                setattr(listing, field, match.group(0))


async def _fetch(request_context, url: str) -> str | None:
    try:
        response = await request_context.get(url, timeout=REQUEST_TIMEOUT_MS)
        if response.ok:
            return await response.text()
    except Exception:
        pass
    return None
