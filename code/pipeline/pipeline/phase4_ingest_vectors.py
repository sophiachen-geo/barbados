"""Phase 4 — Ingest vector inputs.

Each vector entry in config is handled by file type:
  - is_csv_xy=True   -> CSV with lon/lat columns -> XYTableToPoint -> Project
  - is_raster=True   -> raster (e.g. WorldPop population) -> Project Raster
  - otherwise        -> shapefile/geojson/etc. -> Project -> Feature Class
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _gdb_target_path(cfg, gdb_target: str) -> str:
    """Resolve `Vector/Parishes` (or bare `Parishes`) inside the gdb."""
    return os.path.join(cfg.paths.geodatabase, gdb_target)


def _ingest_vector_file(cfg, v) -> None:
    src = os.path.join(cfg.paths.project_root, v.source_file)
    dst = _gdb_target_path(cfg, v.gdb_target)
    if not arc_utils.exists(src):
        if getattr(v, "optional", False):
            log.warning("  optional %s missing, skipping", v.name)
        else:
            log.error("  required %s missing: %s", v.name, src)
        return
    arc_utils.project_feature(src, dst, cfg)


def _ingest_raster(cfg, v) -> None:
    src = os.path.join(cfg.paths.project_root, v.source_file)
    dst = os.path.join(cfg.paths.derivatives, f"{v.name}_UTM.tif")
    if not arc_utils.exists(src):
        log.warning("  raster %s missing, skipping", src)
        return
    arc_utils.project_raster(src, dst, cfg, resampling="BILINEAR")


def _ingest_csv_xy(cfg, v) -> None:
    src = os.path.join(cfg.paths.project_root, v.source_file)
    if not arc_utils.exists(src):
        log.warning("  CSV %s missing, skipping", src)
        return

    # Stage as a point feature class in WGS84 lat/lon
    staged = os.path.join(cfg.paths.geodatabase, f"{v.name}_wgs84")
    final = _gdb_target_path(cfg, v.gdb_target)

    if arc_utils.exists(staged):
        log.info("  [skip] %s already staged", staged)
    else:
        log.info("  XYTableToPoint %s", v.name)
        arcpy.management.XYTableToPoint(
            in_table=src,
            out_feature_class=staged,
            x_field=v.x_field,
            y_field=v.y_field,
            coordinate_system=arc_utils.geographic_sr(cfg),
        )

    if arc_utils.exists(final):
        log.info("  [skip] %s already projected", final)
        return
    arc_utils.project_feature(staged, final, cfg)


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 4 — Ingest vector inputs")
    log.info("=" * 60)
    arc_utils.configure_env(cfg)

    for v in cfg.vectors:
        log.info("[vector] %s (role=%s)", v.name, v.role)
        if getattr(v, "is_csv_xy", False):
            _ingest_csv_xy(cfg, v)
        elif getattr(v, "is_raster", False):
            _ingest_raster(cfg, v)
        else:
            _ingest_vector_file(cfg, v)

    log.info("  Phase 4 complete.")
