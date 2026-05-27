"""Phase 3 — Ingest the annual Esri/IO Sentinel-2 LC stack.

Project each annual raster, build a Mosaic Dataset in the gdb, add a
Year field to the footprint table, enable multidimensional info so the
mosaic behaves like a time series.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _projected_path(cfg, year: int) -> str:
    return os.path.join(cfg.paths.derivatives, f"LC_{year}_UTM.tif")


def _project_annuals(cfg) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for year in cfg.esri_s2.years:
        fname = cfg.esri_s2.filename_pattern.format(year=year)
        src = os.path.join(cfg.paths.inputs_esri_s2, fname)
        if not arc_utils.exists(src):
            log.warning("  %s not found, skipping year %s", src, year)
            continue
        dst = _projected_path(cfg, year)
        arc_utils.project_raster(src, dst, cfg, resampling="NEAREST")
        out.append((year, dst))
    return out


def _build_mosaic(cfg, annual_rasters: list[tuple[int, str]]) -> str:
    mosaic = arc_utils.in_gdb(cfg, cfg.esri_s2.mosaic_name)
    if not arcpy.Exists(mosaic):
        log.info("  creating mosaic dataset %s", mosaic)
        arcpy.management.CreateMosaicDataset(
            in_workspace=cfg.paths.geodatabase,
            in_mosaicdataset_name=cfg.esri_s2.mosaic_name,
            coordinate_system=arc_utils.target_sr(cfg),
            num_bands=1,
            pixel_type="8_BIT_UNSIGNED",
        )
    else:
        log.info("  mosaic %s already exists", cfg.esri_s2.mosaic_name)

    # Add rasters
    paths = ";".join(p for _, p in annual_rasters)
    if paths:
        log.info("  adding %d rasters to mosaic", len(annual_rasters))
        try:
            arcpy.management.AddRastersToMosaicDataset(
                in_mosaic_dataset=mosaic,
                raster_type="Raster Dataset",
                input_path=paths,
                update_overviews="NO_OVERVIEWS",
                duplicate_items_action="EXCLUDE_DUPLICATES",
            )
        except arcpy.ExecuteError as exc:
            log.warning("  AddRastersToMosaicDataset: %s", exc)

    # Add Year field to footprint, populate from filename
    fields = {f.name for f in arcpy.ListFields(mosaic)}
    if "Year" not in fields:
        log.info("  adding Year field to footprint")
        arcpy.management.AddField(mosaic, "Year", "LONG")

    log.info("  populating Year field from raster name")
    name_to_year = {Path(p).stem: y for y, p in annual_rasters}
    with arcpy.da.UpdateCursor(mosaic, ["Name", "Year"]) as cur:
        for row in cur:
            stem = row[0]
            # Robust to either LC_2017_UTM or arbitrary suffixes — extract first 4-digit year
            m = re.search(r"(19|20)\d{2}", stem or "")
            if m:
                row[1] = int(m.group(0))
            elif stem in name_to_year:
                row[1] = name_to_year[stem]
            cur.updateRow(row)

    # Build attribute table-level multidim info: variable_name + dimension Year
    log.info("  configuring multidimensional info")
    try:
        arcpy.management.BuildMultidimensionalInfo(
            in_mosaic_dataset=mosaic,
            variable_field="Variable",
            dimension_fields=f"Year # # #",
            variable_desc_field=None,
        )
    except arcpy.ExecuteError:
        # Variable field may not exist; add a fixed Variable column.
        if "Variable" not in {f.name for f in arcpy.ListFields(mosaic)}:
            arcpy.management.AddField(mosaic, "Variable", "TEXT", field_length=64)
            arcpy.management.CalculateField(
                mosaic, "Variable", f"'{cfg.esri_s2.variable_name}'", "PYTHON3"
            )
        arcpy.management.BuildMultidimensionalInfo(
            in_mosaic_dataset=mosaic,
            variable_field="Variable",
            dimension_fields=f"Year # # #",
        )

    return mosaic


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 3 — Ingest Esri/IO Sentinel-2 stack")
    log.info("=" * 60)
    arc_utils.configure_env(cfg)

    annuals = _project_annuals(cfg)
    if not annuals:
        log.warning("  no annual rasters projected; skipping mosaic build")
        return

    _build_mosaic(cfg, annuals)
    log.info("  Phase 3 complete.")
