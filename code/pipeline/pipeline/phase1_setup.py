"""Phase 1 — Project setup: folders + geodatabase + feature dataset."""
from __future__ import annotations

import logging
import os

import arcpy

from . import arc_utils
from . import config as cfg_mod

log = logging.getLogger(__name__)


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 1 — Project setup")
    log.info("=" * 60)

    cfg_mod.ensure_dirs(cfg)
    log.info("  on-disk folders ensured under %s", cfg.paths.project_root)

    # Geodatabase
    gdb_path = cfg.paths.geodatabase
    gdb_parent, gdb_name = os.path.split(gdb_path)
    if not arcpy.Exists(gdb_path):
        log.info("  creating %s", gdb_path)
        arcpy.management.CreateFileGDB(gdb_parent, gdb_name)
    else:
        log.info("  %s already exists", gdb_path)

    arc_utils.configure_env(cfg)

    # Feature dataset "Vector" in the target CS, for organizing vectors
    vector_fds = os.path.join(gdb_path, "Vector")
    if not arcpy.Exists(vector_fds):
        log.info("  creating feature dataset Vector (EPSG:%s)",
                 cfg.region.target_epsg)
        arcpy.management.CreateFeatureDataset(
            gdb_path, "Vector", arc_utils.target_sr(cfg)
        )
    else:
        log.info("  feature dataset Vector already exists")

    log.info("  Phase 1 complete.")
