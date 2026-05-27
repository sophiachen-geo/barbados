"""Thin arcpy helpers shared across phases.

Keeping these here avoids each phase re-implementing the same boilerplate
(spatial reference lookup, idempotent overwrite, extension checkout, etc.)
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

import arcpy

log = logging.getLogger(__name__)


def configure_env(cfg) -> None:
    """Set arcpy.env to sane region-aware defaults."""
    arcpy.env.overwriteOutput = True
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(
        int(cfg.region.target_epsg)
    )
    arcpy.env.workspace = cfg.paths.geodatabase
    scratch = os.path.join(cfg.paths.project_root, "scratch.gdb")
    if not arcpy.Exists(scratch):
        arcpy.management.CreateFileGDB(cfg.paths.project_root, "scratch.gdb")
    arcpy.env.scratchWorkspace = scratch


def target_sr(cfg) -> arcpy.SpatialReference:
    return arcpy.SpatialReference(int(cfg.region.target_epsg))


def geographic_sr(cfg) -> arcpy.SpatialReference:
    return arcpy.SpatialReference(int(cfg.region.geographic_epsg))


@contextmanager
def extension(name: str):
    """`with extension('Spatial'): ...` — checks out and checks back in."""
    status = arcpy.CheckOutExtension(name)
    if status != "CheckedOut":
        raise RuntimeError(f"Could not check out {name} extension: {status}")
    try:
        yield
    finally:
        arcpy.CheckInExtension(name)


def exists(path: str) -> bool:
    """Wrapper for arcpy.Exists that also handles plain filesystem paths."""
    if not path:
        return False
    if arcpy.Exists(path):
        return True
    return Path(path).exists()


def project_raster(
    in_raster: str,
    out_raster: str,
    cfg,
    resampling: str = "BILINEAR",
    cell_size: str | None = None,
) -> str:
    """Project a raster to the region's target CS. Idempotent."""
    if exists(out_raster):
        log.info("    [skip] %s already exists", out_raster)
        return out_raster
    log.info("    project %s -> %s (%s)", Path(in_raster).name, Path(out_raster).name, resampling)
    arcpy.management.ProjectRaster(
        in_raster=in_raster,
        out_raster=out_raster,
        out_coor_system=target_sr(cfg),
        resampling_type=resampling,
        cell_size=cell_size,
    )
    try:
        arcpy.management.CalculateStatistics(out_raster)
        arcpy.management.BuildPyramids(out_raster, skip_existing="SKIP_EXISTING")
    except arcpy.ExecuteError as exc:
        log.warning("    pyramids/stats failed: %s", exc)
    return out_raster


def project_feature(
    in_feature: str,
    out_feature: str,
    cfg,
) -> str:
    """Project a feature class to the region's target CS. Idempotent."""
    if exists(out_feature):
        log.info("    [skip] %s already exists", out_feature)
        return out_feature
    in_sr = arcpy.Describe(in_feature).spatialReference
    if in_sr is None or in_sr.factoryCode == 0:
        log.warning("    %s has no/undefined SR; assuming geographic",
                    Path(in_feature).name)
        in_sr = geographic_sr(cfg)
    log.info("    project %s -> %s", Path(in_feature).name, Path(out_feature).name)
    arcpy.management.Project(
        in_dataset=in_feature,
        out_dataset=out_feature,
        out_coor_system=target_sr(cfg),
    )
    return out_feature


def safe_run(label: str, fn, *args, **kwargs):
    """Run an arcpy operation, log failures without aborting the whole phase."""
    try:
        log.info("  %s", label)
        return fn(*args, **kwargs)
    except arcpy.ExecuteError as exc:
        log.error("  [FAIL] %s: %s", label, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        log.exception("  [FAIL] %s: %s", label, exc)
        return None


def in_gdb(cfg, name: str) -> str:
    """Build a path inside the region's gdb."""
    return os.path.join(cfg.paths.geodatabase, name)


def in_dir(cfg, key: str, name: str) -> str:
    """Build a path inside one of the configured directories."""
    return os.path.join(getattr(cfg.paths, key), name)


def list_missing(paths: Iterable[str]) -> list[str]:
    return [p for p in paths if not exists(p)]
