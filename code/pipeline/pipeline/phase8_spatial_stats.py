"""Phase 8 — Spatial statistics.

  8.1 Generalized Linear Regression (Gaussian OLS) on listings
  8.2 Exploratory Regression (all-subsets diagnostics)
  8.3 Geographically Weighted Regression
  8.4 Optimized Hot Spot Analysis on configured fields
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _listings_aug(cfg) -> str | None:
    for v in cfg.vectors:
        if v.role == "listings":
            p = os.path.join(cfg.paths.geodatabase, v.gdb_target) + "_aug"
            return p if arc_utils.exists(p) else None
    return None


def _existing_fields(fc: str) -> set[str]:
    return {f.name for f in arcpy.ListFields(fc)}


def glr(cfg, aug_fc: str) -> None:
    log.info("[8.1] Generalized Linear Regression (Gaussian)")
    fields = _existing_fields(aug_fc)
    dep = cfg.spatial_stats.dependent_variable
    explan = [v for v in cfg.spatial_stats.explanatory_variables if v in fields]
    missing = [v for v in cfg.spatial_stats.explanatory_variables if v not in fields]
    if missing:
        log.warning("  missing explanatory fields (dropped): %s", missing)
    if dep not in fields:
        log.error("  dependent %s not in %s; aborting GLR", dep, aug_fc); return
    if not explan:
        log.error("  no explanatory variables present; aborting GLR"); return

    out = arc_utils.in_gdb(cfg, "GLR_Listings")
    log.info("  dep=%s explan=%s -> %s", dep, explan, Path(out).name)
    try:
        arcpy.stats.GeneralizedLinearRegression(
            in_features=aug_fc,
            dependent_variable=dep,
            model_type="CONTINUOUS",
            out_features=out,
            explanatory_variables=explan,
        )
    except arcpy.ExecuteError as exc:
        log.error("  GLR failed: %s", exc)


def exploratory(cfg, aug_fc: str) -> None:
    log.info("[8.2] Exploratory Regression")
    fields = _existing_fields(aug_fc)
    dep = cfg.spatial_stats.dependent_variable
    explan = [v for v in cfg.spatial_stats.explanatory_variables if v in fields]
    if dep not in fields or not explan:
        log.warning("  fields missing, skipping"); return

    report = os.path.join(cfg.paths.outputs, "exploratory_regression.txt")
    out_tbl = arc_utils.in_gdb(cfg, "ExplReg_Results")
    try:
        arcpy.stats.ExploratoryRegression(
            Input_Features=aug_fc,
            Dependent_Variable=dep,
            Candidate_Explanatory_Variables=explan,
            Output_Report_File=report,
            Output_Results_Table=out_tbl,
        )
        log.info("  wrote %s", report)
    except arcpy.ExecuteError as exc:
        log.error("  ExploratoryRegression failed: %s", exc)


def gwr(cfg, aug_fc: str) -> None:
    log.info("[8.3] Geographically Weighted Regression")
    fields = _existing_fields(aug_fc)
    dep = cfg.spatial_stats.dependent_variable
    explan = [v for v in cfg.spatial_stats.explanatory_variables if v in fields]
    if dep not in fields or not explan:
        log.warning("  fields missing, skipping"); return

    out = arc_utils.in_gdb(cfg, "GWR_Listings")
    try:
        arcpy.stats.GWR(
            in_features=aug_fc,
            dependent_variable=dep,
            model_type="CONTINUOUS",
            explanatory_variables=explan,
            output_features=out,
            neighborhood_type="NUMBER_OF_NEIGHBORS",
            neighborhood_selection_method=cfg.spatial_stats.gwr.bandwidth_method,
            local_weighting_scheme="BISQUARE",
        )
        log.info("  wrote %s", out)
    except arcpy.ExecuteError as exc:
        log.error("  GWR failed: %s", exc)


def hot_spots(cfg) -> None:
    log.info("[8.4] Optimized Hot Spot Analysis")
    targets = cfg._raw["spatial_stats"].get("hotspot_fields", [])
    for spec in targets:
        feat_role = spec.get("feature")
        field = spec.get("field")
        # Resolve a path: either the literal gdb_target name, or Listings_..._aug
        if feat_role.endswith("_aug"):
            base_role = "listings"
            path = _listings_aug(cfg)
        else:
            path = None
            for v in cfg.vectors:
                if v.name == feat_role or v.gdb_target.endswith("/" + feat_role):
                    path = os.path.join(cfg.paths.geodatabase, v.gdb_target)
        if not (path and arc_utils.exists(path)):
            log.warning("  hotspot target %s not found, skipping", feat_role); continue
        if field not in _existing_fields(path):
            log.warning("  field %s not in %s, skipping", field, feat_role); continue

        out = arc_utils.in_gdb(cfg, f"HotSpot_{feat_role}_{field}")
        log.info("  Gi* on %s.%s -> %s", feat_role, field, Path(out).name)
        try:
            arcpy.stats.OptimizedHotSpotAnalysis(
                Input_Features=path,
                Output_Features=out,
                Analysis_Field=field,
            )
        except arcpy.ExecuteError as exc:
            log.error("  OHSA failed for %s.%s: %s", feat_role, field, exc)


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 8 — Spatial statistics")
    log.info("=" * 60)
    if not getattr(cfg.spatial_stats, "enabled", False):
        log.info("  spatial_stats.enabled=False; skipping"); return

    arc_utils.configure_env(cfg)
    aug = _listings_aug(cfg)
    if not aug:
        log.warning("  augmented listings not found; run Phase 7 first")
    else:
        glr(cfg, aug)
        exploratory(cfg, aug)
        gwr(cfg, aug)

    hot_spots(cfg)
    log.info("  Phase 8 complete.")
