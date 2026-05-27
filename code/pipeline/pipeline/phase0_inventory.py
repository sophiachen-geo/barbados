"""Phase 0 — Inventory check.

Confirm every input file referenced by config is on disk. Report what's
missing and exit non-zero if anything required is absent; warn-only for
items flagged optional.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def run(cfg) -> bool:
    log.info("=" * 60)
    log.info("Phase 0 — Inventory")
    log.info("=" * 60)

    missing_required: list[str] = []
    missing_optional: list[str] = []

    # GEE outputs (script-04 outputs in Inputs_GEE/)
    for entry in cfg.gee_inputs.composites + cfg.gee_inputs.categorical:
        p = os.path.join(cfg.paths.inputs_gee, entry.file)
        if not Path(p).exists():
            missing_required.append(f"GEE: {p}")

    # GEE v8 series (Google Drive)
    if hasattr(cfg, "gee_v8"):
        v8_base = cfg.paths.inputs_gee_v8
        if not Path(v8_base).exists():
            missing_optional.append(f"v8 base dir not mounted: {v8_base}")
        else:
            buckets = (
                list(cfg.gee_v8.epoch_classifications)
                + list(cfg.gee_v8.continuous_30m)
                + list(cfg.gee_v8.categorical_30m)
                + list(cfg.gee_v8.fine_10m)
            )
            for entry in buckets:
                p = os.path.join(v8_base, entry.file)
                if not Path(p).exists():
                    missing_optional.append(f"v8: {p}")
            cv_csv = os.path.join(v8_base, cfg.gee_v8.spatial_cv_csv)
            if not Path(cv_csv).exists():
                missing_optional.append(f"v8 spatial-CV csv: {cv_csv}")

    # Esri/IO annual rasters
    for year in cfg.esri_s2.years:
        fname = cfg.esri_s2.filename_pattern.format(year=year)
        p = os.path.join(cfg.paths.inputs_esri_s2, fname)
        if not Path(p).exists():
            missing_optional.append(f"Esri S2 {year}: {p}")

    # Vector inputs
    for v in cfg.vectors:
        src = os.path.join(cfg.paths.project_root, v.source_file)
        optional = getattr(v, "optional", False)
        if not Path(src).exists():
            (missing_optional if optional else missing_required).append(
                f"Vector {v.name}: {src}"
            )

    if missing_required:
        log.error("Missing %d REQUIRED inputs:", len(missing_required))
        for m in missing_required:
            log.error("  - %s", m)
    else:
        log.info("All required inputs present.")

    if missing_optional:
        log.warning("Missing %d optional inputs (phase will skip them):",
                    len(missing_optional))
        for m in missing_optional:
            log.warning("  - %s", m)

    return not missing_required
