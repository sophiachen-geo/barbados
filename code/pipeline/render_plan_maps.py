"""Render the planning maps from the Barbados Physical Development Plan PDF.

For each MAP page in the PDF:
  1. Render the page at high DPI to a PNG.
  2. Auto-crop white margins.
  3. Write a manifest entry with approximate WGS84 bounds so the browser can
     overlay the map on the Leaflet map. The bounds are island-scale defaults;
     manual fine tuning per map is possible once each map's true frame is
     measured.

Source PDF must already be downloaded to PDF_PATH.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

PDF_PATH = Path(r"C:/Users/sochen/AppData/Local/Temp/barbados_parliament.pdf")
TARGET_DIR = Path(__file__).resolve().parent / "plan_maps_out"
TARGET_DIR.mkdir(parents=True, exist_ok=True)

DPI = 180

# Approximate Barbados extent (WGS84). The planning maps are portrait pages
# with the map image inset; we place each rendered page at this island scale,
# which gives an "almost right" overlay. True geo-correction requires manual
# ground control points and is left as a follow on step.
ISLAND_BOUNDS = {
    "south": 13.04, "west": -59.71,
    "north": 13.345, "east": -59.40,
}

# Sometimes the rendered page has a header + legend column. We auto-trim the
# white margins, which gets us a reasonable bounding box even when the page
# is wider than the map.
WHITE_THRESHOLD = 245   # pixel mean above this is "white"


def render_page(doc: fitz.Document, page_index: int) -> Image.Image:
    page = doc[page_index]
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def auto_trim_white(img: Image.Image) -> Image.Image:
    arr = np.asarray(img)
    # rows / cols that are mostly white
    row_mean = arr.mean(axis=(1, 2))
    col_mean = arr.mean(axis=(0, 2))
    rows = np.where(row_mean < WHITE_THRESHOLD)[0]
    cols = np.where(col_mean < WHITE_THRESHOLD)[0]
    if len(rows) == 0 or len(cols) == 0:
        return img
    top, bottom = rows.min(), rows.max() + 1
    left, right = cols.min(), cols.max() + 1
    return img.crop((left, top, right, bottom))


def find_map_pages(doc: fitz.Document) -> list[tuple[int, str, str]]:
    """Return [(page_index_0based, map_number_str, map_title), ...]."""
    results = []
    for i, page in enumerate(doc):
        txt = page.get_text()
        m = re.search(r"MAP\s+(\d+):?\s*([^\n]+)", txt, flags=re.IGNORECASE)
        if not m:
            continue
        results.append((i, m.group(1).strip(), m.group(2).strip()))
    return results


def main():
    doc = fitz.open(PDF_PATH)
    all_matches = find_map_pages(doc)
    print(f"Found {len(all_matches)} MAP mentions in text")

    # Render every candidate; keep only the LARGEST render per MAP number,
    # which is the dedicated map page rather than an inline reference.
    rendered_by_num: dict[int, tuple[int, str, Image.Image]] = {}
    for page_idx, mnum, title in all_matches:
        try:
            mnum_int = int(mnum)
        except ValueError:
            continue
        img = render_page(doc, page_idx)
        img = auto_trim_white(img)
        # Total pixel count is a good proxy for "this is the real map page"
        pixels = img.width * img.height
        existing = rendered_by_num.get(mnum_int)
        if existing is None or pixels > existing[2].width * existing[2].height:
            rendered_by_num[mnum_int] = (page_idx, title, img)

    print(f"Deduped to {len(rendered_by_num)} unique maps")

    manifest = []
    for mnum_int in sorted(rendered_by_num):
        page_idx, title, img = rendered_by_num[mnum_int]
        slug = f"plan_map_{mnum_int:02d}"
        out_path = TARGET_DIR / f"{slug}.png"
        img.save(out_path, optimize=True)
        print(f"[{slug}] page {page_idx + 1}: {title}")
        print(f"   wrote {out_path.name}  ({img.width}x{img.height})  "
              f"{out_path.stat().st_size / 1024:.0f} KB")

        manifest.append(dict(
            id=slug,
            title=f"Plan Map {mnum_int}. {title}",
            desc="Source: Barbados Physical Development Plan Amendment, 2023",
            png=f"data/planning_maps/{out_path.name}",
            bounds=[
                [ISLAND_BOUNDS["south"], ISLAND_BOUNDS["west"]],
                [ISLAND_BOUNDS["north"], ISLAND_BOUNDS["east"]],
            ],
            source_page=page_idx + 1,
        ))

    manifest_path = TARGET_DIR / "plan_maps.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nWrote {len(manifest)} maps to {manifest_path}")


if __name__ == "__main__":
    main()
