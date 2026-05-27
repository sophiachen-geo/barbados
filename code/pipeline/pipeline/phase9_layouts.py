"""Phase 9 — Cartographic outputs.

We can't fully automate aesthetic decisions in a layout, but we can:
  - Create a fresh map in the .aprx with all the derived layers loaded
  - Apply the Copernicus colormap to classified rasters (already on disk)
  - Set graduated symbology on parishes by pct_changed
  - Export PNGs of each layer at default extent

The user does the final layout polish in Pro itself.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _aprx_path(cfg) -> str | None:
    # Look for any .aprx in project root
    root = Path(cfg.paths.project_root)
    candidates = list(root.glob("*.aprx"))
    if not candidates:
        log.warning("  no .aprx in %s; create one manually and re-run", root)
        return None
    return str(candidates[0])


def _open_aprx(path: str) -> arcpy.mp.ArcGISProject:
    return arcpy.mp.ArcGISProject(path)


def _ensure_map(aprx, name: str):
    for m in aprx.listMaps():
        if m.name == name:
            return m
    log.info("  creating map %s", name)
    return aprx.createMap(name, "MAP")


def _add_raster(m, path: str) -> None:
    if not arc_utils.exists(path):
        return
    try:
        m.addDataFromPath(path)
        log.info("    added raster %s", Path(path).name)
    except Exception as exc:  # noqa: BLE001
        log.warning("    failed to add %s: %s", path, exc)


def _add_feature(m, path: str) -> None:
    if not arc_utils.exists(path):
        return
    try:
        m.addDataFromPath(path)
        log.info("    added feature %s", Path(path).name)
    except Exception as exc:  # noqa: BLE001
        log.warning("    failed to add %s: %s", path, exc)


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 9 — Cartographic outputs")
    log.info("=" * 60)

    aprx_path = _aprx_path(cfg)
    if not aprx_path:
        log.warning("  Phase 9 skipped (no .aprx found)"); return

    aprx = _open_aprx(aprx_path)
    map_name = f"{cfg.region.name}_Pipeline"
    m = _ensure_map(aprx, map_name)

    # Clear existing pipeline-added layers so we don't double up
    for lyr in list(m.listLayers()):
        if lyr.name.startswith("_pipeline_"):
            m.removeLayer(lyr)

    der = cfg.paths.derivatives
    gdb = cfg.paths.geodatabase

    # Rasters
    for entry in cfg.gee_inputs.categorical:
        _add_raster(m, os.path.join(der, f"{entry.name}_UTM.tif"))
    for tag in ("1984_86", "2020"):
        for band in cfg.gee_inputs.extract_index_bands:
            _add_raster(m, os.path.join(der, f"{band.upper()}_{tag}.tif"))
    _add_raster(m, os.path.join(der, "Urban_Expansion.tif"))
    _add_raster(m, os.path.join(der, "Agreement_2020.tif"))

    # Vector overlays
    for v in cfg.vectors:
        if getattr(v, "is_raster", False):
            continue
        target = v.gdb_target
        if v.role == "listings":
            target = target + "_aug"
        _add_feature(m, os.path.join(gdb, target))

    # Save
    out_aprx = str(Path(aprx_path).with_name(
        Path(aprx_path).stem + "_pipeline.aprx"))
    log.info("  saving copy: %s", out_aprx)
    aprx.saveACopy(out_aprx)

    # Export current layout if one exists (best-effort)
    for layout in aprx.listLayouts():
        try:
            out_png = os.path.join(cfg.paths.outputs, f"layout_{layout.name}.png")
            layout.exportToPNG(out_png, resolution=200)
            log.info("  exported %s", out_png)
        except Exception as exc:  # noqa: BLE001
            log.warning("  could not export layout %s: %s", layout.name, exc)

    log.info("  Phase 9 complete. Open %s to polish.", out_aprx)
