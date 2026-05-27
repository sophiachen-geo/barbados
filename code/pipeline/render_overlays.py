"""Render the GEE TIFFs into colormapped PNG overlays for the web map.

For each raster:
  1. Reads at native (categorical) or downsampled (continuous) resolution.
  2. Applies a colormap (categorical palette or continuous matplotlib cmap).
  3. Masks every pixel outside the Barbados outline to transparent, so the
     overlay never bleeds into the surrounding ocean as a rectangle.
  4. Writes a PNG and a manifest entry the browser consumes.

Run from the project root:
    python Pipeline/render_overlays.py            (only renders missing PNGs)
    python Pipeline/render_overlays.py --force    (re-render everything)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import rasterio
from matplotlib import cm, colors
from PIL import Image
from rasterio.features import geometry_mask
from shapely.geometry import shape
from shapely.ops import unary_union
from rasterio.transform import Affine
from rasterio.enums import Resampling

SRC_DIR = Path(r"H:/My Drive/Barbados")
TARGET_DIR = Path(__file__).resolve().parent / "site_render_out"
PARISH_GEOJSON = Path(__file__).resolve().parent.parent / "Pipeline" / "..\\..\\Pipeline" / ".." / "barbados_parishes.geojson"
# Fallback that always works regardless of where this is invoked from:
PARISH_GEOJSON = Path(r"C:/Users/sochen/AppData/Local/Temp/barbados-site/data/gis/barbados_parishes.geojson")

MAX_DIM_PX = 1600  # cap continuous-raster output at 1600 px on the long edge


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

CLASS_5 = {
    0: ("#00000000", "Water or background"),
    1: ("#1f7a35", "Natural Vegetation"),
    2: ("#e9c83a", "Sugarcane and Cropland"),
    3: ("#a8d97c", "Manicured Grass and Pasture"),
    4: ("#d2342f", "Built Area"),
}

BINARY_CHANGE = {
    0: ("#00000000", "Stable"),
    1: ("#ff2d00", "Changed to Built"),
}

SUGARCANE_TRANSITIONS = {
    0: ("#00000000", "Never Sugarcane"),
    1: ("#a8d97c", "Stayed Cropland"),
    2: ("#d2342f", "Sugarcane to Built"),
    3: ("#1f7a35", "Sugarcane to Natural Vegetation"),
    4: ("#e9c83a", "Other Transition"),
}

TRAJECTORY_5BIN = {
    0: ("#00000000", "Stable"),
    1: ("#1f7a35", "Vegetation Gain"),
    2: ("#d2342f", "Urbanised"),
    3: ("#e9c83a", "Converted to Cropland"),
    4: ("#9966cc", "Other Change"),
}


# ----- island outline (Barbados parishes dissolved into a single mask) -----

_island_geom = None
def island_outline():
    global _island_geom
    if _island_geom is not None:
        return _island_geom
    with open(PARISH_GEOJSON, "r", encoding="utf-8") as fh:
        gj = json.load(fh)
    polys = [shape(f["geometry"]) for f in gj["features"]]
    _island_geom = unary_union(polys).buffer(0)  # buffer(0) cleans any self-intersections
    return _island_geom


def island_mask(transform, shape_hw):
    """True inside the island, False outside."""
    geom = island_outline()
    return geometry_mask([geom.__geo_interface__],
                         out_shape=shape_hw,
                         transform=transform,
                         invert=True)


# ----- per-array renderers -----

def render_categorical(arr: np.ndarray, palette: dict) -> np.ndarray:
    h, w = arr.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for code, (hex_col, _label) in palette.items():
        c = colors.to_rgba(hex_col)
        m = arr == code
        rgba[m, 0] = int(c[0] * 255)
        rgba[m, 1] = int(c[1] * 255)
        rgba[m, 2] = int(c[2] * 255)
        rgba[m, 3] = int(c[3] * 255)
    return rgba


def render_continuous(arr: np.ndarray, cmap_name: str,
                       vmin: float, vmax: float,
                       diverging_zero: bool = False,
                       transparent_zero: bool = True) -> np.ndarray:
    if diverging_zero:
        lim = max(abs(vmin), abs(vmax))
        vmin, vmax = -lim, lim
    norm = colors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    cmap_obj = cm.get_cmap(cmap_name)
    valid = ~np.isnan(arr)
    if transparent_zero:
        valid = valid & (arr != 0)
    rgba = np.zeros((*arr.shape, 4), dtype=np.uint8)
    if not valid.any():
        return rgba
    rgba_f = cmap_obj(norm(arr))
    rgba[..., 0] = (rgba_f[..., 0] * 255).astype(np.uint8)
    rgba[..., 1] = (rgba_f[..., 1] * 255).astype(np.uint8)
    rgba[..., 2] = (rgba_f[..., 2] * 255).astype(np.uint8)
    rgba[..., 3] = np.where(valid, 235, 0).astype(np.uint8)
    return rgba


# ----- per-layer specs (publishable titles, no dashes, title case) -----

LAYERS = [
    dict(id="class_1984_92",  file="Classified_1984_92_v8c.tif",   kind="categorical", palette=CLASS_5,
         title="Land Cover, 1984 to 1992",
         desc="The earliest Landsat 5 epoch. Sugarcane dominates the central plain and built area is largely confined to Bridgetown and a handful of coastal villages."),
    dict(id="class_1993_01",  file="Classified_1993_01_v8c.tif",   kind="categorical", palette=CLASS_5,
         title="Land Cover, 1993 to 2001",
         desc="Sugar enters terminal decline. Early golf and resort fairways begin to register as manicured pixels along the western littoral."),
    dict(id="class_2002_10",  file="Classified_2002_10_v8c.tif",   kind="categorical", palette=CLASS_5,
         title="Land Cover, 2002 to 2010",
         desc="The tourism real estate boom registers in pixels. Gated villa enclaves and resort lawns replace cropland on the western coast."),
    dict(id="class_2011_18",  file="Classified_2011_18_v8c.tif",   kind="categorical", palette=CLASS_5,
         title="Land Cover, 2011 to 2018",
         desc="Densification. Villa enclaves multiply and the manicured signature spreads inland from the original coastal strip."),
    dict(id="class_2019_25",  file="Classified_2019_25_v8c.tif",   kind="categorical", palette=CLASS_5,
         title="Land Cover, 2019 to 2025",
         desc="The most recent classification. Note that the 30 metre Landsat classifier performs poorly in Saint James, so the next layer offers a finer resolution sanity check."),
    dict(id="class_10m_v8f",  file="Classification_10m_v8f.tif",   kind="categorical", palette=CLASS_5,
         title="Land Cover, 10 Metre Sentinel 2",
         desc="The same classification scheme built from 10 metre Sentinel 2 imagery. The increased resolution resolves individual hotel footprints and villa lots, which is particularly useful on the West Coast."),
    dict(id="became_urban",   file="BecameUrban_v8c.tif",          kind="categorical", palette=BINARY_CHANGE,
         title="Land That Became Urban",
         desc="Red pixels were any class other than built in the 1984 epoch and became built by the 2019 epoch. This is the most direct evidence of real estate driven urbanisation in the entire stack."),
    dict(id="sugarcane_conv", file="SugarcaneConversion_v8c.tif",  kind="categorical", palette=SUGARCANE_TRANSITIONS,
         title="Where the Sugarcane Went",
         desc="What former sugarcane pixels became. The red Sugarcane to Built class concentrated along the West Coast is the spatial signature of plantation land sold for tourism real estate."),
    dict(id="manicuring_10m", file="ManicuringIndex_10m_v8f.tif",  kind="continuous",
         cmap="YlGn", vmin=0.05, vmax=0.4,
         title="Manicured Vegetation Index, 10 Metre",
         desc="High values pick out heavily managed turf: golf course fairways, resort lawns, hotel grounds. Sandy Lane, Apes Hill, Royal Westmoreland and the Sandals fairways all light up clearly."),
    dict(id="manicuring_30m", file="ManicuringIndex_v8c.tif",      kind="continuous",
         cmap="YlGn", vmin=0.05, vmax=0.5,
         title="Manicured Vegetation Index, 30 Metre",
         desc="The same index built from coarser Landsat imagery for direct comparison with the Landsat era classifications."),
    dict(id="ndvi_trend",     file="NDVI_Trend_10m_v8f.tif",       kind="continuous",
         cmap="RdYlGn", vmin=-0.1, vmax=0.1, diverging=True, transparent_zero=False,
         title="NDVI Trend Per Year, 2017 to 2024",
         desc="Red indicates a decline in vegetation cover, green indicates an increase. The West Coast and the densifying suburban ring around Bridgetown show consistent browning."),
    dict(id="ccdc_nbreaks",   file="CCDC_nBreaks_v8c.tif",         kind="continuous",
         cmap="magma_r", vmin=0, vmax=4,
         title="Number of Detected Changes",
         desc="How many times each pixel changed state across the full record. High values mark unstable or repeatedly disturbed land such as construction sites and abandonment cycles."),
    dict(id="ccdc_firstbreak",file="CCDC_FirstBreakYear_v8c.tif",  kind="continuous",
         cmap="viridis", vmin=1990, vmax=2024, transparent_zero=False,
         title="Year of First Detected Change",
         desc="Each pixel is coloured by the year a continuous change detection algorithm first registered a real disturbance. Purple is long ago, yellow is recent."),
    dict(id="trajectory_bin", file="Trajectory_5bin_v8c.tif",      kind="categorical_band1",
         palette=TRAJECTORY_5BIN,
         title="Trajectory Type, Five Classes",
         desc="A pre classified trajectory type per pixel showing the dominant kind of change that occurred from the 1980s baseline to the present."),
    dict(id="disagreement",   file="Disagreement_v8c.tif",         kind="continuous",
         cmap="OrRd", vmin=0, vmax=3,
         title="Classifier Disagreement",
         desc="Five separate classifiers vote on each pixel. High values mark pixels where the methods disagree, and any per pixel statistic should be treated with care there."),
    dict(id="consensus",      file="Consensus_5way_v8c.tif",       kind="categorical", palette=CLASS_5,
         title="Five Way Classifier Consensus",
         desc="The majority vote class across five separate classifiers."),
]


# ----- main render loop -----

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
        h_full, w_full = ds.height, ds.width
        if spec["kind"] == "continuous" and max(h_full, w_full) > MAX_DIM_PX:
            scale = MAX_DIM_PX / max(h_full, w_full)
            out_h = max(1, int(round(h_full * scale)))
            out_w = max(1, int(round(w_full * scale)))
            print(f"    downsample {w_full}x{h_full} -> {out_w}x{out_h}")
        else:
            out_h, out_w = h_full, w_full

        if spec["kind"] in ("categorical", "categorical_band1"):
            arr = ds.read(1, out_shape=(out_h, out_w),
                          resampling=Resampling.nearest).astype(np.int32)
        else:
            arr = ds.read(1, out_shape=(out_h, out_w),
                          resampling=Resampling.average).astype(np.float64)

        # Effective transform for the read shape
        sx = ds.width / out_w
        sy = ds.height / out_h
        effective_transform = ds.transform * Affine.scale(sx, sy)
        b = ds.bounds

    # Render to RGBA
    if spec["kind"] in ("categorical", "categorical_band1"):
        rgba = render_categorical(arr, spec["palette"])
    else:
        rgba = render_continuous(
            arr,
            spec["cmap"],
            spec["vmin"],
            spec["vmax"],
            diverging_zero=spec.get("diverging", False),
            transparent_zero=spec.get("transparent_zero", True),
        )

    # Apply island mask: pixels outside Barbados become fully transparent
    inside = island_mask(effective_transform, (out_h, out_w))
    rgba[..., 3] = np.where(inside, rgba[..., 3], 0)

    Image.fromarray(rgba, mode="RGBA").save(out_png, optimize=True)
    print(f"  wrote {out_png.name}  ({rgba.shape[1]}x{rgba.shape[0]})")
    return _manifest_entry(spec, b, out_png)


def _manifest_entry(spec, bounds, out_png) -> dict:
    return dict(
        id=spec["id"],
        title=spec["title"],
        desc=spec["desc"],
        kind=spec["kind"],
        png=f"data/remote_sensing/overlays/{out_png.name}",
        bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
        legend=_legend(spec),
    )


def _legend(spec) -> list:
    if spec["kind"] in ("categorical", "categorical_band1"):
        return [{"label": lab, "hex": hx}
                for code, (hx, lab) in sorted(spec["palette"].items())
                if hx != "#00000000"]
    cmap = cm.get_cmap(spec["cmap"])
    return [
        {"label": f"{spec['vmin']:g}", "hex": colors.to_hex(cmap(0.0))},
        {"label": f"{(spec['vmin'] + spec['vmax']) / 2:g}", "hex": colors.to_hex(cmap(0.5))},
        {"label": f"{spec['vmax']:g}", "hex": colors.to_hex(cmap(1.0))},
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
