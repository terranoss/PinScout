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


def export(
    listings: list[Listing],
    destination: Path | str | None = None,
    fmt: str = "xlsx",
) -> tuple[Path, Path]:
    if destination is not None:
        out_path = Path(destination)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = "csv" if out_path.suffix.lower() == ".csv" else "xlsx"
        photos_dir = out_path.parent / f"{out_path.stem}_photos"
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gmaps_results_{timestamp}.{fmt}"
        out_path = OUTPUT_DIR / filename
        photos_dir = OUTPUT_DIR / f"{out_path.stem}_photos"

    # Download cover photos for saved listings only at export time
    download_photos_sync(listings, photos_dir=photos_dir)

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

    if fmt == "xlsx":
        df.to_excel(out_path, index=False)
    else:
        df.to_csv(out_path, index=False)

    return out_path, photos_dir


