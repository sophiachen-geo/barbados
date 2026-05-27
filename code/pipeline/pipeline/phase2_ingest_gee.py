"""Phase 2 — Ingest GEE outputs.

Project every GEE raster to the target CS, write to Derivatives/ with
`_UTM` suffix, build pyramids/stats. For multiband composites, also
extract the requested index bands (NDVI/MNDWI/temp by default) as
standalone rasters so downstream tools don't have to know band order.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _derivative_path(cfg, name: str) -> str:
    return os.path.join(cfg.paths.derivatives, f"{name}_UTM.tif")


def _extract_band(in_raster: str, band_index_1based: int, out_path: str) -> None:
    """Copy a single band out of a multiband raster to a standalone TIF."""
    if arc_utils.exists(out_path):
        log.info("    [skip] %s", out_path)
        return
    log.info("    extract band %d -> %s", band_index_1based, Path(out_path).name)
    # arcpy.management.CompositeBands or just use Make Raster Layer + Copy
    band_path = f"{in_raster}/Band_{band_index_1based}"
    arcpy.management.CopyRaster(band_path, out_path, pixel_type="32_BIT_FLOAT")


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 2 — Ingest GEE outputs")
    log.info("=" * 60)
    arc_utils.configure_env(cfg)

    band_names = list(cfg.gee_inputs.composite_band_names)
    extract_names = list(cfg.gee_inputs.extract_index_bands)

    # --- Composites (Bilinear) ---
    for entry in cfg.gee_inputs.composites:
        src = os.path.join(cfg.paths.inputs_gee, entry.file)
        if not arc_utils.exists(src):
            log.warning("  composite missing, skipping: %s", src)
            continue
        out = _derivative_path(cfg, entry.name)
        arc_utils.project_raster(src, out, cfg, resampling="BILINEAR")

        # Extract requested index bands as standalone rasters
        for band_name in extract_names:
            if band_name not in band_names:
                log.warning("    band %s not in composite_band_names list",
                            band_name)
                continue
            idx_1based = band_names.index(band_name) + 1
            tag = entry.epoch_label
            out_band = os.path.join(
                cfg.paths.derivatives, f"{band_name.upper()}_{tag}.tif"
            )
            try:
                _extract_band(out, idx_1based, out_band)
            except arcpy.ExecuteError as exc:
                log.error("    extract %s band failed: %s", band_name, exc)

    # --- Categorical rasters (Nearest) ---
    for entry in cfg.gee_inputs.categorical:
        src = os.path.join(cfg.paths.inputs_gee, entry.file)
        if not arc_utils.exists(src):
            log.warning("  categorical missing, skipping: %s", src)
            continue
        out = _derivative_path(cfg, entry.name)
        arc_utils.project_raster(src, out, cfg, resampling="NEAREST")

    log.info("  Phase 2 complete.")
