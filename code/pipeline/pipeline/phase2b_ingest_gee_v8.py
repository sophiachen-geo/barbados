"""Phase 2b — Ingest the GEE v8 series (richer, multi-method outputs).

Reads from Google Drive sync path (configurable via paths.inputs_gee_v8) and
projects every raster to the target CS. Logs the per-parish spatial-CV table
prominently so the user is aware of any parishes where the classifier failed.

c-suffix = Landsat 30m, f-suffix = Sentinel-2 10m. We keep them in the same
Derivatives folder but preserve the suffix so downstream tools can route
correctly by resolution.
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _src(cfg, file_name: str) -> str:
    base = cfg.paths.inputs_gee_v8
    return os.path.join(base, file_name)


def _dst(cfg, name: str) -> str:
    return os.path.join(cfg.paths.derivatives, f"{name}_UTM.tif")


def _project_entry(cfg, entry, resampling: str) -> None:
    src = _src(cfg, entry.file)
    if not arc_utils.exists(src):
        log.warning("  v8 input missing, skipping: %s", src)
        return
    dst = _dst(cfg, entry.name)
    arc_utils.project_raster(src, dst, cfg, resampling=resampling)


def _ingest_epoch_classifications(cfg) -> None:
    log.info("[v8c] Epoch classifications (5 epochs, NEAREST)")
    for entry in cfg.gee_v8.epoch_classifications:
        _project_entry(cfg, entry, resampling="NEAREST")


def _ingest_continuous_30m(cfg) -> None:
    log.info("[v8c] Continuous diagnostics (BILINEAR)")
    for entry in cfg.gee_v8.continuous_30m:
        _project_entry(cfg, entry, resampling="BILINEAR")


def _ingest_categorical_30m(cfg) -> None:
    log.info("[v8c] Categorical change rasters (NEAREST)")
    for entry in cfg.gee_v8.categorical_30m:
        _project_entry(cfg, entry, resampling="NEAREST")


def _ingest_fine_10m(cfg) -> None:
    log.info("[v8f] Sentinel-2/S1 10m rasters")
    for entry in cfg.gee_v8.fine_10m:
        resampling = getattr(entry, "resampling", "BILINEAR")
        _project_entry(cfg, entry, resampling=resampling)


def _log_spatial_cv(cfg) -> None:
    """Read the per-parish spatial CV CSV and call out unreliable parishes."""
    csv_path = _src(cfg, cfg.gee_v8.spatial_cv_csv)
    if not arc_utils.exists(csv_path):
        log.warning("  spatial CV csv not found: %s", csv_path); return

    log.info("=" * 60)
    log.info("Spatial cross-validation by parish (v8c classifier)")
    log.info("=" * 60)
    acc_thr = float(cfg.gee_v8.spatial_cv_unreliable_threshold.accuracy_below)
    kap_thr = float(cfg.gee_v8.spatial_cv_unreliable_threshold.kappa_below)

    unreliable: list[str] = []
    with open(csv_path, "r", encoding="utf-8") as fh:
        rdr = csv.DictReader(fh)
        for row in rdr:
            parish = row.get("parish", "?").strip()
            try:
                acc = float(row.get("accuracy", "nan"))
                kap = float(row.get("kappa", "nan"))
                n   = int(row.get("n_test", "0"))
            except ValueError:
                continue
            flag = " <-- UNRELIABLE" if (acc < acc_thr or kap < kap_thr) else ""
            log.info("  %-15s  acc=%.3f  kappa=%.3f  n=%4d%s",
                     parish, acc, kap, n, flag)
            if flag:
                unreliable.append(parish)

    if unreliable:
        log.warning("Parishes with unreliable v8c classification: %s", unreliable)
        log.warning("Recommendation: cross-check these against Classification_10m_v8f "
                    "(Sentinel-2 fine-resolution) and/or treat their leisuring/transition "
                    "stats as lower-bound estimates only.")

    # Copy the CV table into Outputs/ for the paper
    out_csv = os.path.join(cfg.paths.outputs, "spatial_cv_by_parish_v8c.csv")
    try:
        import shutil
        shutil.copy2(csv_path, out_csv)
        log.info("  CV table copied to %s", out_csv)
    except Exception as exc:  # noqa: BLE001
        log.warning("  could not copy CV table: %s", exc)


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 2b — Ingest GEE v8 series from %s", cfg.paths.inputs_gee_v8)
    log.info("=" * 60)

    if not arc_utils.exists(cfg.paths.inputs_gee_v8):
        log.error("  v8 source directory not reachable: %s", cfg.paths.inputs_gee_v8)
        log.error("  Make sure Google Drive File Stream is mounted as H:")
        return

    arc_utils.configure_env(cfg)

    _ingest_epoch_classifications(cfg)
    _ingest_continuous_30m(cfg)
    _ingest_categorical_30m(cfg)
    _ingest_fine_10m(cfg)
    _log_spatial_cv(cfg)

    log.info("  Phase 2b complete.")
