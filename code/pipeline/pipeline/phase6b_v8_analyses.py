"""Phase 6b — Analyses unlocked by the v8 series.

  6b.1  Consecutive-epoch transition matrices (1984-92 -> 1993-01 -> ... -> 2019-25)
  6b.2  BecameUrban tabulated by parish (direct urbanisation, no derivation needed)
  6b.3  SugarcaneConversion tabulated by parish (plantation displacement)
  6b.4  CCDC FirstBreakYear histogram by parish (when did each parish change?)
  6b.5  ManicuringIndex hotspots (golf-course / resort lawn detection)
  6b.6  NDVI 10m trend slope by parish (greening / browning per year)
  6b.7  Disagreement / Consensus_5way mapped to flag uncertain pixels
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


# ---------- helpers shared with phase 6 ----------

def _admin_layer(cfg):
    for v in cfg.vectors:
        if v.role == "admin":
            path = os.path.join(cfg.paths.geodatabase, v.gdb_target)
            name_field = getattr(v, "name_field", "name")
            if arc_utils.exists(path):
                return path, name_field
    raise FileNotFoundError("No admin-role vector found.")


def _deriv(cfg, name: str) -> str:
    return os.path.join(cfg.paths.derivatives, f"{name}_UTM.tif")


def _write_table_to_csv(in_table: str, out_csv: str) -> None:
    fields = [f.name for f in arcpy.ListFields(in_table)
              if f.type not in ("Geometry", "OID")]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        with arcpy.da.SearchCursor(in_table, fields) as cur:
            for row in cur:
                w.writerow(row)


# ---------- 6b.1 Consecutive-epoch transitions ----------

def consecutive_epoch_transitions(cfg) -> None:
    log.info("[6b.1] Consecutive-epoch transitions (4 pairs)")
    from arcpy.sa import Combine, Raster

    epochs = list(cfg.gee_v8.epoch_classifications)
    if len(epochs) < 2:
        log.warning("  need 2+ epoch classifications, found %d", len(epochs)); return

    admin, name_field = _admin_layer(cfg)

    for early, recent in zip(epochs, epochs[1:]):
        early_path = _deriv(cfg, early.name)
        recent_path = _deriv(cfg, recent.name)
        if not (arc_utils.exists(early_path) and arc_utils.exists(recent_path)):
            log.warning("  missing pair: %s / %s", early.name, recent.name); continue

        tag = f"{early.epoch_start}_to_{recent.epoch_end}"
        combo_path = os.path.join(cfg.paths.derivatives,
                                   f"FromTo_v8c_{tag}.tif")
        if not arc_utils.exists(combo_path):
            log.info("  Combine %s + %s -> %s",
                     early.name, recent.name, Path(combo_path).name)
            Combine([early_path, recent_path]).save(combo_path)

        out_table = arc_utils.in_gdb(cfg, f"Transitions_v8c_{tag}_by_Admin")
        if not arc_utils.exists(out_table):
            arcpy.sa.TabulateArea(admin, name_field, combo_path, "Value",
                                  out_table, processing_cell_size=30)
        out_csv = os.path.join(cfg.paths.outputs,
                                f"transitions_v8c_{tag}_by_admin.csv")
        _write_table_to_csv(out_table, out_csv)
        log.info("  wrote %s", out_csv)


# ---------- 6b.2 BecameUrban ----------

def became_urban(cfg) -> None:
    log.info("[6b.2] BecameUrban_v8c by parish")
    src = _deriv(cfg, "BecameUrban_v8c")
    if not arc_utils.exists(src):
        log.warning("  %s missing, skipping", src); return

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "BecameUrban_by_Admin")
    if not arc_utils.exists(out_table):
        arcpy.sa.ZonalStatisticsAsTable(
            in_zone_data=admin, zone_field=name_field,
            in_value_raster=src, out_table=out_table,
            statistics_type="ALL",
        )

    # Add a became_urban_pct field: SUM / COUNT * 100 (assumes selfMasked binary)
    fields = {f.name for f in arcpy.ListFields(out_table)}
    if "became_urban_pct" not in fields:
        arcpy.management.AddField(out_table, "became_urban_pct", "DOUBLE")
        arcpy.management.CalculateField(
            out_table, "became_urban_pct",
            "(!SUM! / !COUNT!) * 100 if !COUNT! else None",
            "PYTHON3",
        )

    _write_table_to_csv(out_table,
        os.path.join(cfg.paths.outputs, "became_urban_by_admin.csv"))


# ---------- 6b.3 Sugarcane conversion ----------

def sugarcane_conversion(cfg) -> None:
    log.info("[6b.3] SugarcaneConversion_v8c by parish")
    src = _deriv(cfg, "SugarcaneConversion_v8c")
    if not arc_utils.exists(src):
        log.warning("  %s missing, skipping", src); return

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "SugarcaneConversion_by_Admin")
    if not arc_utils.exists(out_table):
        arcpy.sa.TabulateArea(admin, name_field, src, "Value",
                              out_table, processing_cell_size=30)
    _write_table_to_csv(out_table,
        os.path.join(cfg.paths.outputs, "sugarcane_conversion_by_admin.csv"))


# ---------- 6b.4 CCDC break-year histogram ----------

def ccdc_break_year_histogram(cfg) -> None:
    log.info("[6b.4] CCDC FirstBreakYear histogram by parish")
    src = _deriv(cfg, "CCDC_FirstBreakYear_v8c")
    if not arc_utils.exists(src):
        log.warning("  %s missing, skipping", src); return

    # Reclassify into year-bins from config
    from arcpy.sa import Reclassify, RemapRange

    bins = list(cfg.gee_v8.epoch_classifications)  # not used here, just sanity
    edges = list(cfg.v8_analyses.ccdc_break_year_bins)
    if len(edges) < 2:
        log.warning("  need 2+ break-year bin edges; skipping"); return

    # Build a [lo, hi, bin_code] remap. Bin code = index from 1.
    remap = []
    for i, (lo, hi) in enumerate(zip(edges, edges[1:]), start=1):
        remap.append([float(lo), float(hi), i])

    binned = os.path.join(cfg.paths.derivatives, "CCDC_FirstBreakYear_binned.tif")
    if not arc_utils.exists(binned):
        log.info("  reclassify into %d bins", len(remap))
        Reclassify(src, "Value", RemapRange(remap), "NODATA").save(binned)

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "CCDC_BreakYear_by_Admin")
    if not arc_utils.exists(out_table):
        arcpy.sa.TabulateArea(admin, name_field, binned, "Value",
                              out_table, processing_cell_size=30)
    out_csv = os.path.join(cfg.paths.outputs,
                            "ccdc_first_break_year_by_admin.csv")
    _write_table_to_csv(out_table, out_csv)
    log.info("  wrote %s (bin codes = consecutive year ranges from %s)",
             out_csv, edges)


# ---------- 6b.5 Manicuring index hotspots ----------

def manicuring_hotspots(cfg) -> None:
    log.info("[6b.5] ManicuringIndex hotspots (golf / resort lawn detection)")
    from arcpy.sa import Con, Raster

    # Prefer the 10m v8f version if available; fall back to 30m v8c
    src_10m = _deriv(cfg, "ManicuringIndex_10m_v8f")
    src_30m = _deriv(cfg, "ManicuringIndex_v8c")
    src = src_10m if arc_utils.exists(src_10m) else src_30m
    if not arc_utils.exists(src):
        log.warning("  no manicuring raster, skipping"); return

    thr = float(cfg.v8_analyses.manicuring_threshold)
    out_mask = os.path.join(cfg.paths.derivatives, "Manicured_Mask.tif")
    if not arc_utils.exists(out_mask):
        log.info("  threshold manicuring > %s -> %s", thr, Path(out_mask).name)
        Con(Raster(src) > thr, 1, 0).save(out_mask)

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "Manicured_by_Admin")
    if not arc_utils.exists(out_table):
        arcpy.sa.ZonalStatisticsAsTable(
            in_zone_data=admin, zone_field=name_field,
            in_value_raster=out_mask, out_table=out_table,
            statistics_type="SUM",
        )
    _write_table_to_csv(out_table,
        os.path.join(cfg.paths.outputs, "manicuring_hotspots_by_admin.csv"))


# ---------- 6b.6 NDVI trend by parish ----------

def ndvi_trend_by_parish(cfg) -> None:
    log.info("[6b.6] NDVI trend (10m) per parish")
    src = _deriv(cfg, "NDVI_Trend_10m_v8f")
    if not arc_utils.exists(src):
        log.warning("  %s missing, skipping", src); return

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "NDVI_Trend_by_Admin")
    if not arc_utils.exists(out_table):
        arcpy.sa.ZonalStatisticsAsTable(
            in_zone_data=admin, zone_field=name_field,
            in_value_raster=src, out_table=out_table,
            statistics_type="ALL",
        )

    # Add a "greening_down_share" field — fraction of pixels with slope < threshold
    from arcpy.sa import Con, Raster
    thr = float(cfg.v8_analyses.ndvi_trend_significant_slope)
    browning_mask = os.path.join(cfg.paths.derivatives, "NDVI_Browning_Mask.tif")
    if not arc_utils.exists(browning_mask):
        log.info("  threshold slope < %s -> browning mask", thr)
        Con(Raster(src) < thr, 1, 0).save(browning_mask)

    out_brown = arc_utils.in_gdb(cfg, "NDVI_Browning_by_Admin")
    if not arc_utils.exists(out_brown):
        arcpy.sa.ZonalStatisticsAsTable(
            in_zone_data=admin, zone_field=name_field,
            in_value_raster=browning_mask, out_table=out_brown,
            statistics_type="ALL",
        )
    _write_table_to_csv(out_table,
        os.path.join(cfg.paths.outputs, "ndvi_trend_by_admin.csv"))
    _write_table_to_csv(out_brown,
        os.path.join(cfg.paths.outputs, "ndvi_browning_share_by_admin.csv"))


# ---------- 6b.7 Disagreement masking ----------

def write_uncertainty_mask(cfg) -> None:
    """Combine Disagreement_v8c and Certainty_2019_2021_v8c into an uncertainty
    flag that downstream regressions can use to weight or drop pixels."""
    log.info("[6b.7] Uncertainty mask from Disagreement + Certainty")
    from arcpy.sa import Raster, Con

    dis = _deriv(cfg, "Disagreement_v8c")
    cer = _deriv(cfg, "Certainty_2019_2021_v8c")
    if not (arc_utils.exists(dis) and arc_utils.exists(cer)):
        log.warning("  Disagreement and/or Certainty missing"); return

    out = os.path.join(cfg.paths.derivatives, "Uncertainty_Flag.tif")
    if arc_utils.exists(out):
        log.info("  [skip] %s exists", out); return

    # Flag = 1 where (disagreement >= 2) OR (certainty < 0.5)
    flag = Con((Raster(dis) >= 2) | (Raster(cer) < 0.5), 1, 0)
    flag.save(out)
    log.info("  wrote %s (1 = treat with caution)", out)


# ---------- entry point ----------

def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 6b — v8 analyses")
    log.info("=" * 60)
    arc_utils.configure_env(cfg)

    with arc_utils.extension("Spatial"):
        for label, fn in (
            ("consecutive_epoch_transitions", consecutive_epoch_transitions),
            ("became_urban",                  became_urban),
            ("sugarcane_conversion",          sugarcane_conversion),
            ("ccdc_break_year_histogram",     ccdc_break_year_histogram),
            ("manicuring_hotspots",           manicuring_hotspots),
            ("ndvi_trend_by_parish",          ndvi_trend_by_parish),
            ("write_uncertainty_mask",        write_uncertainty_mask),
        ):
            try:
                fn(cfg)
            except FileNotFoundError as exc:
                log.warning("  [%s] %s", label, exc)
            except arcpy.ExecuteError as exc:
                log.error("  [%s] arcpy: %s", label, exc)
            except Exception:  # noqa: BLE001
                log.exception("  [%s] unexpected error", label)

    log.info("  Phase 6b complete.")
