"""CLI orchestrator for the regional pipeline.

Usage examples (from inside the ArcGIS Pro Python environment, with the
Pipeline/ folder as CWD):

    # Run everything (phases 0-9) on Barbados
    python run_pipeline.py --config config/barbados.yaml

    # Run a single phase
    python run_pipeline.py --config config/barbados.yaml --phase 6

    # Run a contiguous range
    python run_pipeline.py --config config/barbados.yaml --phases 1-4

    # Run for a different region — just swap the config
    python run_pipeline.py --config config/newfoundland.yaml
"""
from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path

# Make `pipeline` importable when run from this directory
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import config as cfg_mod  # noqa: E402
from pipeline.logging_utils import setup_logging  # noqa: E402


# Phase keys are strings so we can insert "2b", "6b" without breaking ordering.
PHASES = {
    "0":  ("pipeline.phase0_inventory",      "Inventory"),
    "1":  ("pipeline.phase1_setup",          "Project setup"),
    "2":  ("pipeline.phase2_ingest_gee",     "Ingest GEE (script-04 outputs)"),
    "2b": ("pipeline.phase2b_ingest_gee_v8", "Ingest GEE v8 series (H: drive)"),
    "3":  ("pipeline.phase3_ingest_esri_s2", "Ingest Esri S2"),
    "4":  ("pipeline.phase4_ingest_vectors", "Ingest vectors"),
    "5":  ("pipeline.phase5_harmonize",      "Harmonize + cross-compare"),
    "6":  ("pipeline.phase6_analyses",       "Core analyses"),
    "6b": ("pipeline.phase6b_v8_analyses",   "v8 series analyses"),
    "7":  ("pipeline.phase7_integration",    "Listings integration"),
    "8":  ("pipeline.phase8_spatial_stats",  "Spatial statistics"),
    "9":  ("pipeline.phase9_layouts",        "Layouts"),
}

# Canonical run order — used when expanding a range like "1-4" or running all.
PHASE_ORDER = ["0", "1", "2", "2b", "3", "4", "5", "6", "6b", "7", "8", "9"]


def _parse_phase_arg(args) -> list[str]:
    """Return a list of phase keys (strings) to run, in canonical order."""
    if args.phase is not None:
        return [str(args.phase).strip()]
    if args.phases:
        token = args.phases.strip()
        if "-" in token:
            lo, hi = (t.strip() for t in token.split("-", 1))
            if lo not in PHASE_ORDER or hi not in PHASE_ORDER:
                raise SystemExit(f"Unknown phase in range '{token}'. "
                                 f"Valid: {PHASE_ORDER}")
            i, j = PHASE_ORDER.index(lo), PHASE_ORDER.index(hi)
            return PHASE_ORDER[i : j + 1]
        return [t.strip() for t in token.split(",") if t.strip()]
    return list(PHASE_ORDER)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to region YAML")
    ap.add_argument("--phase",
                    help="Run a single phase. Valid: 0,1,2,2b,3,4,5,6,6b,7,8,9")
    ap.add_argument("--phases",
                    help="Range (e.g. 1-4, 2-6b) or list (e.g. 2,2b,5,6b)")
    args = ap.parse_args()

    cfg = cfg_mod.load(args.config)
    cfg_mod.ensure_dirs(cfg)

    phases_to_run = _parse_phase_arg(args)
    label = "_".join(phases_to_run) if len(phases_to_run) > 1 \
            else phases_to_run[0]
    setup_logging(cfg.paths.logs, f"{cfg.region.name}_phases{label}")

    import logging
    log = logging.getLogger("run_pipeline")
    log.info("Region: %s", cfg.region.name)
    log.info("Config: %s", cfg.config_path)
    log.info("Phases: %s", phases_to_run)

    overall_start = time.time()
    for p in phases_to_run:
        if p not in PHASES:
            log.error("Unknown phase: %s", p); continue
        mod_name, phase_label = PHASES[p]
        log.info("\n>>> Phase %s (%s) <<<", p, phase_label)
        t0 = time.time()
        try:
            mod = importlib.import_module(mod_name)
            result = mod.run(cfg)
            if p == "0" and result is False:
                log.error("Inventory failed — fix missing inputs and rerun.")
                return 2
        except Exception:  # noqa: BLE001
            log.exception("Phase %s crashed", p)
            return 1
        log.info("Phase %s done in %.1fs", p, time.time() - t0)

    log.info("\nAll requested phases done in %.1fs", time.time() - overall_start)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
