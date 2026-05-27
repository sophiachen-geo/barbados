"""Render the v8 GEE TIFFs into colormapped PNG overlays for the web map.

Reads each raster from the H: drive (paths configured below), renders to PNG
with an appropriate colormap, writes a manifest JSON the browser can consume,
and copies everything into data/remote_sensing/overlays/.

Run from the project root:
    python Pipeline/render_overlays.py

Idempotent — skips PNGs that already exist unless --force is passed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import rasterio
from matplotlib import cm, colors
from PIL import Image

SRC_DIR = Path(r"H:/My Drive/Barbados")
OUT_DIR = Path(__file__).resolve().parent.parent / "Site_Overlays"  # local staging
SITE_OVERLAYS_DIR = Path(__file__).resolve().parent.parent / "Pipeline" / "site_overlays_published"

# We'll write to a tmp folder first, then copy to the site
TARGET_DIR = Path(__file__).resolve().parent / "site_render_out"


# ----- colormap definitions -----
COPERNICUS_8CLASS = {
    1: ("#f096ff", "Agriculture"),
    2: ("#b4b4b4", "Bare"),
    3: ("#ffff4c", "Herbaceous"),
    4: ("#007800", "Forest"),
    5: ("#ffbb22", "Shrub"),
    6: ("#fa0000", "Urban"),
    7: ("#0032c8", "Water"),
    8: ("#0096a0", "Wetland"),
}

# v8 5-class scheme — likely Built / Veg / Sugarcane / Manicured / Water
V8_5CLASS = {
    0: ("#1f3b6b", "Water / background"),
    1: ("#1f7a35", "Natural vegetation"),
    2: ("#e9c83a", "Sugarcane / cropland"),
    3: ("#a8d97c", "Manicured / pasture"),
    4: ("#d2342f", "Built / urban"),
}

# Binary change: 0 stable, 1 changed
BINARY_CHANGE = {
    0: ("#00000000", "Stable"),
    1: ("#ff2d00", "Changed"),
}

# nBreaks (0-6+)
N_BREAKS_CMAP = "magma_r"

# Years 1985-2025 colormap
YEAR_CMAP = "viridis"

# Disagreement 0-4
DISAGREEMENT_CMAP = "OrRd"


# ----- raster -> PNG renderer -----

def render_categorical(arr: np.ndarray, palette: dict) -> np.ndarray:
    """Map integer-valued array to RGBA using a class -> hex palette."""
    h, w = arr.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for code, (hex_col, _label) in palette.items():
        c = colors.to_rgba(hex_col)
        mask = arr == code
        rgba[mask, 0] = int(c[0] * 255)
        rgba[mask, 1] = int(c[1] * 255)
        rgba[mask, 2] = int(c[2] * 255)
        rgba[mask, 3] = int(c[3] * 255)
    return rgba


def render_continuous(arr: np.ndarray, cmap_name: str,
                       vmin: float, vmax: float,
                       diverging_zero: bool = False) -> np.ndarray:
    """Map a continuous masked array to RGBA via a matplotlib colormap."""
    if diverging_zero:
        # Symmetric range around 0
        lim = max(abs(vmin), abs(vmax))
        vmin, vmax = -lim, lim
    norm = colors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    cmap = cm.get_cmap(cmap_name)
    valid = ~(np.isnan(arr) | (arr == 0))   # treat exact-zero as transparent for change rasters
    rgba = np.zeros((*arr.shape, 4), dtype=np.uint8)
    if not valid.any():
        return rgba
    rgba_f = cmap(norm(arr))                # 0..1 RGBA
    rgba[..., 0] = (rgba_f[..., 0] * 255).astype(np.uint8)
    rgba[..., 1] = (rgba_f[..., 1] * 255).astype(np.uint8)
    rgba[..., 2] = (rgba_f[..., 2] * 255).astype(np.uint8)
    rgba[..., 3] = np.where(valid, 220, 0).astype(np.uint8)
    return rgba


def render_continuous_keep_zero(arr: np.ndarray, cmap_name: str,
                                 vmin: float, vmax: float) -> np.ndarray:
    """Same as render_continuous but allow zero values (for e.g. NDVI trend)."""
    norm = colors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    cmap = cm.get_cmap(cmap_name)
    valid = ~np.isnan(arr)
    rgba = np.zeros((*arr.shape, 4), dtype=np.uint8)
    if not valid.any():
        return rgba
    rgba_f = cmap(norm(arr))
    rgba[..., 0] = (rgba_f[..., 0] * 255).astype(np.uint8)
    rgba[..., 1] = (rgba_f[..., 1] * 255).astype(np.uint8)
    rgba[..., 2] = (rgba_f[..., 2] * 255).astype(np.uint8)
    rgba[..., 3] = np.where(valid, 220, 0).astype(np.uint8)
    return rgba


# ----- per-layer specs -----

LAYERS = [
    # name              file                                    kind                params
    dict(id="class_1984_92",  file="Classified_1984_92_v8c.tif",   kind="categorical", palette=V8_5CLASS,
         title="Land cover 1984-1992",
         desc="Earliest Landsat 5 epoch. Establishes the pre-leisuring baseline.",
         step="01"),
    dict(id="class_1993_01",  file="Classified_1993_01_v8c.tif",   kind="categorical", palette=V8_5CLASS,
         title="Land cover 1993-2001",
         desc="Sugar decline era; emergence of golf and resort fairways.",
         step="02"),
    dict(id="class_2002_10",  file="Classified_2002_10_v8c.tif",   kind="categorical", palette=V8_5CLASS,
         title="Land cover 2002-2010",
         desc="Mid-period: tourism real-estate boom on the West Coast.",
         step="03"),
    dict(id="class_2011_18",  file="Classified_2011_18_v8c.tif",   kind="categorical", palette=V8_5CLASS,
         title="Land cover 2011-2018",
         desc="Densification; villa enclaves multiply.",
         step="04"),
    dict(id="class_2019_25",  file="Classified_2019_25_v8c.tif",   kind="categorical", palette=V8_5CLASS,
         title="Land cover 2019-2025",
         desc="Welcome-Stamp era. 10 m Sentinel-2 cross-check recommended in St James.",
         step="05"),
    dict(id="class_10m_v8f",  file="Classification_10m_v8f.tif",   kind="categorical", palette=V8_5CLASS,
         title="Land cover, 10 m Sentinel-2 (recent)",
         desc="Fine-resolution recent classification. Use this as the St James sanity check.",
         step="06"),
    dict(id="became_urban",   file="BecameUrban_v8c.tif",          kind="categorical", palette=BINARY_CHANGE,
         title="Became urban, 1984-2025",
         desc="Direct binary: red = pixel that was non-urban in 1984-92 and urban by 2019-25.",
         step="07"),
    dict(id="sugarcane_conv", file="SugarcaneConversion_v8c.tif",  kind="categorical",
         palette={0:("#00000000","Not sugarcane"), 1:("#a8d97c","Stayed cropland"),
                  2:("#d2342f","To built"), 3:("#1f7a35","To natural veg"),
                  4:("#e9c83a","Other transition")},
         title="Sugarcane conversion",
         desc="What former sugarcane pixels became.",
         step="08"),
    dict(id="manicuring_10m", file="ManicuringIndex_10m_v8f.tif",  kind="continuous",
         cmap="YlGn", vmin=0.05, vmax=0.4,
         title="Manicuring index (10 m)",
         desc="High = golf-course / resort lawn / heavily managed vegetation.",
         step="09"),
    dict(id="manicuring_30m", file="ManicuringIndex_v8c.tif",      kind="continuous",
         cmap="YlGn", vmin=0.05, vmax=0.5,
         title="Manicuring index (30 m)",
         desc="Coarser-resolution version for comparison.",
         step="10"),
    dict(id="ndvi_trend",     file="NDVI_Trend_10m_v8f.tif",       kind="continuous",
         cmap="RdYlGn", vmin=-0.1, vmax=0.1, diverging=True, keep_zero=True,
         title="NDVI trend per year (10 m)",
         desc="Red = browning (vegetation loss), green = greening, 2017-2024.",
         step="11"),
    dict(id="ccdc_nbreaks",   file="CCDC_nBreaks_v8c.tif",         kind="continuous",
         cmap="magma_r", vmin=0, vmax=4,
         title="CCDC: number of breaks",
         desc="How many times each pixel changed state. High = unstable / repeatedly disturbed.",
         step="12"),
    dict(id="ccdc_firstbreak",file="CCDC_FirstBreakYear_v8c.tif",  kind="continuous",
         cmap="viridis", vmin=1990, vmax=2024, keep_zero=True,
         title="CCDC: year of first detected change",
         desc="Earlier (purple) = changed long ago; later (yellow) = recent change.",
         step="13"),
    dict(id="trajectory_bin", file="Trajectory_5bin_v8c.tif",      kind="categorical_band1",
         palette={0:("#00000000","Stable"), 1:("#1f7a35","Vegetation gain"),
                  2:("#d2342f","Urbanised"), 3:("#e9c83a","To cropland"),
                  4:("#9966cc","Other change")},
         title="Trajectory (5-bin)",
         desc="Pre-classified trajectory type per pixel (first band shown).",
         step="14"),
    dict(id="disagreement",   file="Disagreement_v8c.tif",         kind="continuous",
         cmap="OrRd", vmin=0, vmax=3,
         title="Multi-method disagreement",
         desc="High = classifiers disagree about this pixel. Treat with caution.",
         step="15"),
    dict(id="consensus",      file="Consensus_5way_v8c.tif",       kind="categorical", palette=V8_5CLASS,
         title="5-way classifier consensus",
         desc="Majority-vote class across five classifiers.",
         step="16"),
]


MAX_DIM_PX = 1600  # cap continuous-raster output at 1600 px on the long edge


def render_one(spec: dict, force: bool) -> dict | None:
    src = SRC_DIR / spec["file"]
    if not src.exists():
        print(f"  MISSING: {src}")
        return None
    out_png = TARGET_DIR / f"{spec['id']}.png"
    if out_png.exists() and not force:
        print(f"  [skip] {out_png.name}")
        with rasterio.open(src) as ds:
            b = ds.bounds
        return _manifest_entry(spec, b, out_png)

    with rasterio.open(src) as ds:
        # Decide on an output read shape that respects MAX_DIM_PX for continuous rasters
        h_full, w_full = ds.height, ds.width
        if spec["kind"] == "continuous" and max(h_full, w_full) > MAX_DIM_PX:
            scale = MAX_DIM_PX / max(h_full, w_full)
            out_h = max(1, int(round(h_full * scale)))
            out_w = max(1, int(round(w_full * scale)))
            print(f"    downsample {w_full}x{h_full} -> {out_w}x{out_h}")
        else:
            out_h, out_w = h_full, w_full

        if spec["kind"] == "categorical_band1":
            arr = ds.read(1, out_shape=(out_h, out_w),
                          resampling=rasterio.enums.Resampling.nearest).astype(np.int32)
        elif spec["kind"] == "categorical":
            arr = ds.read(1, out_shape=(out_h, out_w),
                          resampling=rasterio.enums.Resampling.nearest).astype(np.int32)
        else:
            arr = ds.read(1, out_shape=(out_h, out_w),
                          resampling=rasterio.enums.Resampling.average).astype(np.float64)
        b = ds.bounds

    if spec["kind"] in ("categorical", "categorical_band1"):
        rgba = render_categorical(arr, spec["palette"])
    elif spec["kind"] == "continuous":
        if spec.get("keep_zero"):
            rgba = render_continuous_keep_zero(arr, spec["cmap"],
                                                spec["vmin"], spec["vmax"])
        else:
            rgba = render_continuous(arr, spec["cmap"],
                                      spec["vmin"], spec["vmax"],
                                      diverging_zero=spec.get("diverging", False))
    else:
        raise ValueError(f"unknown kind: {spec['kind']}")

    Image.fromarray(rgba, mode="RGBA").save(out_png, optimize=True)
    print(f"  wrote {out_png.name}  ({rgba.shape[1]}x{rgba.shape[0]})")
    return _manifest_entry(spec, b, out_png)


def _manifest_entry(spec, bounds, out_png) -> dict:
    # Leaflet wants [[south, west], [north, east]]
    return dict(
        id=spec["id"],
        title=spec["title"],
        desc=spec["desc"],
        step=spec.get("step"),
        kind=spec["kind"],
        png=f"data/remote_sensing/overlays/{out_png.name}",
        bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
        legend=_legend(spec),
    )


def _legend(spec) -> list:
    if spec["kind"] in ("categorical", "categorical_band1"):
        return [{"label": lab, "hex": hx} for code, (hx, lab) in
                sorted(spec["palette"].items())]
    return [
        {"label": f"{spec['vmin']}", "hex": colors.to_hex(cm.get_cmap(spec["cmap"])(0.0))},
        {"label": f"{(spec['vmin']+spec['vmax'])/2:g}", "hex": colors.to_hex(cm.get_cmap(spec["cmap"])(0.5))},
        {"label": f"{spec['vmax']}", "hex": colors.to_hex(cm.get_cmap(spec["cmap"])(1.0))},
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Re-render existing PNGs")
    args = ap.parse_args()

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for spec in LAYERS:
        print(f"[{spec['id']}] {spec['title']}")
        entry = render_one(spec, force=args.force)
        if entry:
            manifest.append(entry)

    manifest_path = TARGET_DIR / "layers.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nWrote {len(manifest)} layers to {manifest_path}")
    print(f"Render outputs in: {TARGET_DIR}")


if __name__ == "__main__":
    main()
