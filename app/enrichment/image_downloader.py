"""Asynchronously downloads the main cover photo (top_image_url) for each listing

Saves images locally into the `output/photos/` directory with clean filenames.
Populates listing.sstatus with the download outcome for export observability.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from playwright.async_api import APIRequestContext, Error as PlaywrightError, async_playwright

from app.models import Listing

PHOTOS_DIR = Path(__file__).parent.parent.parent / "output" / "photos"
CONCURRENCY_LIMIT = 8
REQUEST_TIMEOUT_MS = 8000
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
MAPS_REFERER = "https://www.google.com/maps"

logger = logging.getLogger(__name__)


async def download_photos(listings: list[Listing]) -> None:
    """Download main cover photos for listings; set sstatus for every listing."""
    for listing in listings:
        if not listing.top_image_url:
            listing.sstatus = "no_img"

    targets = [l for l in listings if l.top_image_url]
    if not targets:
        return

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async with async_playwright() as p:
        request_context = await p.request.new_context(
            extra_http_headers={
                "Referer": MAPS_REFERER,
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            }
        )
        try:
            tasks = [_download_one(listing, request_context, semaphore) for listing in targets]
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await request_context.dispose()


async def _download_one(
    listing: Listing,
    request_context: APIRequestContext,
    semaphore: asyncio.Semaphore,
) -> None:
    if not listing.top_image_url:
        listing.sstatus = "no_img"
        return

    async with semaphore:
        last_status = "error"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await request_context.get(
                    listing.top_image_url,
                    timeout=REQUEST_TIMEOUT_MS,
                    headers={"Referer": MAPS_REFERER},
                )
                if response.ok:
                    body = await response.body()
                    if not body:
                        last_status = "empty_body"
                        logger.warning(
                            "Empty image body for listing id=%s attempt=%s",
                            listing.id,
                            attempt,
                        )
                    else:
                        safe_name = _sanitize_filename(listing.name or "listing")
                        rec_id = listing.id or "0"
                        filename = f"{rec_id}_{safe_name}.jpg"
                        filepath = PHOTOS_DIR / filename
                        with open(filepath, "wb") as f:
                            f.write(body)
                        listing.saved_image_name = filename
                        listing.sstatus = "ok"
                        return
                else:
                    last_status = f"http_{response.status}"
                    logger.warning(
                        "Image download HTTP %s for listing id=%s attempt=%s url=%s",
                        response.status,
                        listing.id,
                        attempt,
                        listing.top_image_url[:120],
                    )
            except PlaywrightError as exc:
                msg = str(exc).lower()
                if "timeout" in msg:
                    last_status = "timeout"
                else:
                    last_status = "error"
                logger.warning(
                    "Image download Playwright error for listing id=%s attempt=%s: %s",
                    listing.id,
                    attempt,
                    exc,
                )
            except Exception as exc:
                last_status = "error"
                logger.warning(
                    "Image download failed for listing id=%s attempt=%s: %s",
                    listing.id,
                    attempt,
                    exc,
                )
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_BASE_SECONDS * attempt)

        listing.sstatus = last_status
        logger.error(
            "Image download exhausted retries for listing id=%s status=%s",
            listing.id,
            last_status,
        )


def download_photos_sync(listings: list[Listing]) -> None:
    """Synchronous wrapper to download cover photos at export time."""
    try:
        asyncio.run(download_photos(listings))
    except Exception as exc:
        logger.exception("download_photos_sync failed: %s", exc)
        for listing in listings:
            if listing.sstatus is None:
                listing.sstatus = "batch_error"


def _sanitize_filename(name: str) -> str:
    """Remove filesystem-unsafe characters from a business name."""
    s = re.sub(r'[\\/*?:"<>|]', "", name)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:40] if s else "listing"
