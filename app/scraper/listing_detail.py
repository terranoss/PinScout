"""Navigates to an individual listing's place URL and parses the detail pane
into the full Listing schema.
"""

from __future__ import annotations

import asyncio
import random
import re

from playwright.async_api import Page

from app.config import SEL
from app.models import Listing
from app.scraper.results_panel import CardRef

RATING_RE = re.compile(r"(\d+\.\d+)")
REVIEW_COUNT_RE = re.compile(r"([\d,]+)\s*review", re.IGNORECASE)
PAREN_REVIEW_COUNT_RE = re.compile(r"\(([\d,]+)\)")
ZIP_RE = re.compile(r"\b(\d{4,6})\b")



async def extract_listing(page: Page, card: CardRef, keyword: str | None) -> Listing:
    listing = Listing(
        keyword=keyword,
        name=card.name,
        maps_url=card.maps_url,
        latitude=card.latitude,
        longitude=card.longitude,
    )


    max_attempts = SEL.retry.get("max_attempts", 3)
    backoff = SEL.retry.get("backoff_base_seconds", 1.5)

    loaded = False
    for attempt in range(1, max_attempts + 1):
        try:
            await page.goto(card.maps_url, wait_until="domcontentloaded")
            await _wait_for_detail_pane(page)
            await asyncio.sleep(random.uniform(0.3, 0.8))
            loaded = True
            break
        except Exception:
            if attempt < max_attempts:
                await asyncio.sleep(backoff * attempt)

    title_sel = SEL.detail_pane.get("title", "h1.DUwDvf")
    category_sel = SEL.detail_pane.get("category", "button.DkEaL")
    address_sel = SEL.detail_pane.get("address_button", "button[data-item-id='address']")
    phone_sel = SEL.detail_pane.get("phone_button", "button[data-item-id^='phone:tel:']")
    website_sel = SEL.detail_pane.get("website_link", "a[data-item-id='authority']")
    plus_code_sel = SEL.detail_pane.get("plus_code_button", "button[data-item-id='oloc']")
    rating_sel = SEL.detail_pane.get("rating_text", "div.F7nice")
    claim_hint = SEL.detail_pane.get("claimed_text_hint", "Claim this business")

    sub_title_sel = SEL.detail_pane.get("sub_title", "div.LBgpqf")
    pricing_sel = SEL.detail_pane.get("pricing", "span.mgr77e")
    description_sel = SEL.detail_pane.get("description", "div.PYvSYb")
    hours_status_sel = SEL.detail_pane.get("hours_status", "div.MkV9")
    hours_table_sel = SEL.detail_pane.get("hours_table", "table.eK4R0e")
    top_image_sel = SEL.detail_pane.get("top_image", "button.aoRNLd img")
    top_image_fallbacks = SEL.detail_pane.get("top_image_fallbacks") or []
    photo_tags_sel = SEL.detail_pane.get("photo_tags", "div.Qi3Lb")
    menu_url_sel = SEL.detail_pane.get("menu_url", "a[data-item-id='menu']")
    services_sel = SEL.detail_pane.get("services", "div.LTs0Pb")
    located_in_sel = SEL.detail_pane.get("located_in", "a[data-item-id='located-in']")
    amenities_sel = SEL.detail_pane.get("amenities", "div.e2moi")
    attributes_sel = SEL.detail_pane.get("attributes", "div.M37doe")
    external_urls_sel = SEL.detail_pane.get("external_urls", "a[data-item-id^='url']")

    listing.name = await _safe_text(page, title_sel) or listing.name
    listing.category = await _safe_text(page, category_sel)
    listing.full_address = await _safe_text(page, address_sel)
    listing.phone = await _safe_text(page, phone_sel)
    listing.website = await _safe_attr(page, website_sel, "href")
    listing.plus_code = await _safe_text(page, plus_code_sel)
    listing.sub_title = await _safe_text(page, sub_title_sel)
    listing.pricing = await _safe_text(page, pricing_sel)
    listing.description = await _safe_text(page, description_sel)
    listing.top_image_url = await _extract_top_image_url(page, top_image_sel, top_image_fallbacks)
    listing.menu_url = await _safe_attr(page, menu_url_sel, "href")
    listing.services = await _safe_text(page, services_sel)
    listing.located_in = await _safe_text(page, located_in_sel)
    listing.amenities = await _safe_text(page, amenities_sel)
    listing.attributes = await _safe_text(page, attributes_sel)

    # Photo tags
    try:
        tag_els = await page.locator(photo_tags_sel).all()
        if tag_els:
            tags = [await t.inner_text() for t in tag_els]
            listing.photo_tags = ", ".join([t.strip() for t in tags if t.strip()])
    except Exception:
        pass

    # External URLs
    try:
        ext_els = await page.locator(external_urls_sel).all()
        if ext_els:
            urls = [await e.get_attribute("href") for e in ext_els]
            listing.external_urls = ", ".join([u for u in urls if u])
    except Exception:
        pass

    # Verification text
    try:
        page_text = await page.inner_text("body")
        if claim_hint in page_text:
            listing.verification_text = claim_hint
    except Exception:
        pass

    # Hours Status & Day Hours (extracted while on Overview tab)
    listing.hours = await _safe_text(page, hours_status_sel)
    await _extract_hours(page, hours_table_sel, listing)

    # Rating & Review Count
    await _extract_rating_and_reviews(page, rating_sel, listing)

    # Tab-specific inspection (Reviews & Tickets tabs — runs last so it doesn't disturb Overview tab extraction)
    await _extract_tab_data(page, listing)


    if listing.full_address:
        listing.street_address, listing.city, listing.state, listing.zip = (
            _split_address(listing.full_address)
        )

    return listing


async def _extract_rating_and_reviews(page: Page, rating_sel: str, listing: Listing) -> None:
    # 1. Check primary rating block on Overview tab (e.g. "3.9 (585)" or "3.9 585 reviews")
    rating_block = await _safe_text(page, rating_sel)
    if rating_block:
        r_match = RATING_RE.search(rating_block)
        rev_match = REVIEW_COUNT_RE.search(rating_block) or PAREN_REVIEW_COUNT_RE.search(rating_block)
        if r_match:
            listing.rating = float(r_match.group(1))
        if rev_match:
            listing.review_count = int(rev_match.group(1).replace(",", ""))

    # 2. Check aria-labels on rating buttons/spans on Overview tab if missing
    if not listing.rating or not listing.review_count:
        try:
            aria_els = await page.locator("button[aria-label*='reviews'], span[aria-label*='reviews'], button[aria-label*='stars'], span[aria-label*='stars']").all()
            for el in aria_els:
                label = await el.get_attribute("aria-label") or ""
                if label:
                    r_match = RATING_RE.search(label)
                    rev_match = REVIEW_COUNT_RE.search(label) or PAREN_REVIEW_COUNT_RE.search(label)
                    if not listing.rating and r_match:
                        listing.rating = float(r_match.group(1))
                    if not listing.review_count and rev_match:
                        listing.review_count = int(rev_match.group(1).replace(",", ""))
        except Exception:
            pass


async def _extract_tab_data(page: Page, listing: Listing) -> None:
    # Extract Star Histogram from current view (Overview or Reviews)
    await _extract_stars(page, listing)

    # Check if Reviews tab needs clicking to get missing review count/histogram
    if not listing.review_count or not listing.stars_5:
        try:
            reviews_tab_sel = SEL.tabs.get("reviews_tab", "button[role='tab'][aria-label*='Reviews'], button[role='tab']:has-text('Reviews')")
            tab_btn = page.locator(reviews_tab_sel).first
            if await tab_btn.count() > 0:
                await tab_btn.click(timeout=2000)
                await asyncio.sleep(0.5)

                # Read review count header (e.g. "585 reviews")
                page_text = await page.inner_text("body")
                rev_match = REVIEW_COUNT_RE.search(page_text)
                if rev_match and not listing.review_count:
                    listing.review_count = int(rev_match.group(1).replace(",", ""))

                # Re-check stars on Reviews tab
                await _extract_stars(page, listing)
        except Exception:
            pass

    # Check Tickets tab for official / primary admission price (e.g. "RM 130.00" or "RM 2.00")
    if not listing.pricing:
        try:
            tickets_tab_sel = SEL.tabs.get("tickets_tab", "button[role='tab'][aria-label*='Tickets'], button[role='tab']:has-text('Tickets')")
            ticket_btn = page.locator(tickets_tab_sel).first
            if await ticket_btn.count() > 0:
                await ticket_btn.click(timeout=2000)
                await asyncio.sleep(0.5)

                container_sel = SEL.tickets.get("admission_container", "div[aria-label*='Admission'], div:has-text('Admission')")
                admission_el = page.locator(container_sel).first
                if await admission_el.count() > 0:
                    # 1. Prefer Official Site row price first
                    official_row = admission_el.locator("div:has-text('Official site')").first
                    official_text = await official_row.inner_text(timeout=1500) if await official_row.count() > 0 else ""
                    official_match = re.search(r"((?:RM|\$|€|£|¥)\s*[\d,]+(?:\.\d{2})?|Free)", official_text, re.IGNORECASE)

                    if official_match:
                        listing.pricing = official_match.group(1)
                    else:
                        # 2. Fallback to first price found in tickets list
                        full_text = await admission_el.inner_text(timeout=2000)
                        first_match = re.search(r"((?:RM|\$|€|£|¥)\s*[\d,]+(?:\.\d{2})?|Free)", full_text, re.IGNORECASE)
                        if first_match:
                            listing.pricing = first_match.group(1)
        except Exception:
            pass




async def _extract_hours(page: Page, hours_table_sel: str, listing: Listing) -> None:
    try:
        dropdown_sel = SEL.detail_pane.get(
            "hours_dropdown",
            "button[data-item-id='oh'], button[aria-label*='hours'], button[aria-label*='Hours'], button[aria-label*='Open'], button[aria-label*='Closed'], div.MkV9 button, div.MkV9",
        )
        table = page.locator("table.eK4R0e, table[class*='eK4R0e'], div.t3b7ae").first

        # If 7-day table is not currently visible, try clicking the hours dropdown button
        if await table.count() == 0 or await table.locator("tr").count() == 0:
            btn = page.locator(dropdown_sel).first
            if await btn.count() > 0:
                try:
                    await btn.click(timeout=2000)
                    await asyncio.sleep(0.6)
                except Exception:
                    pass

        # Re-check table or rows after click
        table = page.locator("table.eK4R0e, table[class*='eK4R0e'], div.t3b7ae").first
        rows = await table.locator("tr").all() if await table.count() > 0 else await page.locator("tr.y0skT, tr.WvfeUd").all()

        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        for row in rows:
            raw_text = await row.inner_text()
            clean_text = _clean_text(raw_text) or ""
            if not clean_text:
                continue

            lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
            full_line = " ".join(lines)

            for day in days:
                if day in full_line.lower():
                    if len(lines) >= 2:
                        hours_str = " ".join(lines[1:])
                    else:
                        match = re.search(r"^\s*" + day + r"\s*:?\s*(.*)$", full_line, re.IGNORECASE)
                        hours_str = match.group(1).strip() if match else full_line

                    setattr(listing, day, _clean_text(hours_str) or "Closed")
                    break

        if rows and not listing.hours_info:
            first_row_text = await rows[0].inner_text()
            listing.hours_info = _clean_text(" ".join([l.strip() for l in first_row_text.splitlines() if l.strip()]))

    except Exception:
        pass




async def _extract_stars(page: Page, listing: Listing) -> None:
    try:
        star_rows = await page.locator("tr.GBkF3d, tr[aria-label*='stars'], div[aria-label*='stars']").all()
        for row in star_rows:
            label = await row.get_attribute("aria-label") or await row.inner_text()
            if not label:
                continue
            m_star = re.search(r"([1-5])\s*star", label, re.IGNORECASE)
            m_count = re.search(r"([\d,]+)\s*(?:review)?", label, re.IGNORECASE)
            if m_star:
                star_num = m_star.group(1)
                count_val = int(m_count.group(1).replace(",", "")) if m_count else 0
                setattr(listing, f"stars_{star_num}", count_val)
    except Exception:
        pass



async def _wait_for_detail_pane(page: Page, timeout: int = 10000) -> None:
    title_sel = SEL.detail_pane.get("title", "h1.DUwDvf")
    try:
        await page.locator(title_sel).first.wait_for(state="visible", timeout=timeout)
    except Exception:
        pass


def _is_usable_image_src(src: str | None) -> bool:
    if not src:
        return False
    s = src.strip()
    if not s or s.startswith("data:"):
        return False
    return s.startswith("http://") or s.startswith("https://")


async def _soft_wait_for_selector(page: Page, selector: str, timeout: int = 4000) -> None:
    try:
        await page.locator(selector).first.wait_for(state="attached", timeout=timeout)
    except Exception:
        pass


async def _extract_top_image_url(
    page: Page,
    primary_sel: str,
    fallbacks: list | None = None,
) -> str | None:
    """Soft-wait for the hero image, then try primary + fallback selectors for src."""
    await _soft_wait_for_selector(page, primary_sel, timeout=4000)
    selectors = [primary_sel]
    if fallbacks:
        selectors.extend([s for s in fallbacks if s and s not in selectors])
    for sel in selectors:
        src = await _safe_attr(page, sel, "src")
        if _is_usable_image_src(src):
            return src
        # Some Maps heroes put the URL on a parent style/background instead of img src.
        style_url = await _safe_bg_image_url(page, sel)
        if _is_usable_image_src(style_url):
            return style_url
    return None


async def _safe_bg_image_url(page: Page, selector: str) -> str | None:
    """Best-effort extract of url(...) from an element's style or parent style."""
    try:
        el = page.locator(selector).first
        if await el.count() == 0:
            return None
        style = await el.get_attribute("style", timeout=2000) or ""
        m = re.search(r"url\([\"']?(https?://[^\"')]+)[\"']?\)", style)
        if m:
            return m.group(1)
        parent = el.locator("xpath=..")
        if await parent.count() == 0:
            return None
        pstyle = await parent.first.get_attribute("style", timeout=2000) or ""
        m = re.search(r"url\([\"']?(https?://[^\"')]+)[\"']?\)", pstyle)
        return m.group(1) if m else None
    except Exception:
        return None


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    # Remove Private Use Area Unicode characters (\ue000-\uf8ff), replacement chars (\ufffd),
    # icon glyphs like ✚ (\u2795), non-breaking spaces (\xa0), and control formatting marks
    s = re.sub(r"[\ue000-\uf8ff\ufffd\u2795\u200e\u200f\ufeff]", "", text)
    s = s.replace("\xa0", " ").strip()
    return s or None


async def _safe_text(page: Page, selector: str) -> str | None:
    try:
        el = page.locator(selector).first
        if await el.count() == 0:
            return None
        text = await el.inner_text(timeout=3000)
        return _clean_text(text)
    except Exception:
        return None



async def _safe_attr(page: Page, selector: str, attr: str) -> str | None:
    try:
        el = page.locator(selector).first
        if await el.count() == 0:
            return None
        val = await el.get_attribute(attr, timeout=3000)
        return val
    except Exception:
        return None


def _split_address(full_address: str) -> tuple[str | None, str | None, str | None, str | None]:
    parts = [p.strip() for p in full_address.split(",") if p.strip()]
    street = parts[0] if len(parts) >= 1 else None
    city = parts[1] if len(parts) >= 2 else None

    zip_code = None
    zip_match = ZIP_RE.search(full_address)
    if zip_match:
        zip_code = zip_match.group(1)

    state = parts[-1] if len(parts) >= 3 else None

    return street, city, state, zip_code

