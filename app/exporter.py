"""Converts collected Listing objects into a CSV/XLSX export.

Uses EXPORT_COLUMN_ORDER and FIELD_TO_EXPORT_HEADER from models.py for
consistent column names and order.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

import pandas as pd

from app.models import Listing, EXPORT_COLUMN_ORDER, FIELD_TO_EXPORT_HEADER
from app.enrichment.image_downloader import download_photos_sync

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def export(listings: list[Listing], fmt: str = "xlsx") -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Download cover photos for saved listings only at export time
    download_photos_sync(listings)

    rows = [listing.model_dump() for listing in listings]

    df = pd.DataFrame(rows)

    # Dedup: prefer place URL as the uniqueness key when present.
    if "maps_url" in df.columns:
        df = df.drop_duplicates(subset=["maps_url"], keep="first")

    # Assign sequential ids, then rename/reorder columns for export.
    df["id"] = range(1, len(df) + 1)
    df = df.rename(columns=FIELD_TO_EXPORT_HEADER)
    ordered_cols = [c for c in EXPORT_COLUMN_ORDER if c in df.columns]
    df = df[ordered_cols]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gmaps_results_{timestamp}.{fmt}"
    out_path = OUTPUT_DIR / filename

    if fmt == "xlsx":
        df.to_excel(out_path, index=False)
    else:
        df.to_csv(out_path, index=False)

    return out_path
