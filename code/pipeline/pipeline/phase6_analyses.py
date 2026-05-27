"""Phase 6 — Core analyses.

  6.1 From-To transition matrix by admin unit (Tabulate Area + pivot CSV)
  6.2 Per-admin-unit "leisuring rate" from binary change raster
  6.3 Coastline change (Quick: Erase polygons + areas; rigorous DSAS deferred)
  6.4 Urban-class expansion 1985 -> 2020
  6.5 Recent change from Esri/IO (early_year vs recent_year)
  6.6 (Agreement raster already produced in Phase 5)
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


# ---------- helpers ----------

def _admin_layer(cfg):
    """Return (path, name_field) for whichever vector role=admin is configured."""
    for v in cfg.vectors:
        if v.role == "admin":
            path = os.path.join(cfg.paths.geodatabase, v.gdb_target)
            name_field = getattr(v, "name_field", "name")
            if arc_utils.exists(path):
                return path, name_field
    raise FileNotFoundError("No admin-role vector found or not yet projected.")


def _coastline_layer(cfg) -> str | None:
    for v in cfg.vectors:
        if v.role == "coastline":
            p = os.path.join(cfg.paths.geodatabase, v.gdb_target)
            return p if arc_utils.exists(p) else None
    return None


def _write_table_to_csv(in_table: str, out_csv: str) -> None:
    fields = [f.name for f in arcpy.ListFields(in_table)
              if f.type not in ("Geometry", "OID")]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        with arcpy.da.SearchCursor(in_table, fields) as cur:
            for row in cur:
                w.writerow(row)


# ---------- 6.1 ----------

def transition_matrix(cfg) -> None:
    log.info("[6.1] Transition matrix by admin unit")
    fromto = os.path.join(cfg.paths.derivatives, "FromTo_1984_to_2020_UTM.tif")
    if not arc_utils.exists(fromto):
        log.warning("  %s missing, skipping", fromto); return

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "Transitions_by_Admin")
    if not arc_utils.exists(out_table):
        log.info("  TabulateArea")
        arcpy.sa.TabulateArea(
            in_zone_data=admin,
            zone_field=name_field,
            in_class_data=fromto,
            class_field="Value",
            out_table=out_table,
            processing_cell_size=30,
        )
    out_csv = os.path.join(cfg.paths.outputs, "transitions_by_admin.csv")
    _write_table_to_csv(out_table, out_csv)
    log.info("  wrote %s", out_csv)

    # Focus-codes summary
    focus = cfg._raw.get("fromto_focus_codes", {})
    if focus:
        out_focus_csv = os.path.join(cfg.paths.outputs,
                                     "transitions_focus_by_admin.csv")
        log.info("  building focus summary -> %s", out_focus_csv)
        # Pull fields that match focus codes (TabulateArea names columns VALUE_<n>)
        fields = [f.name for f in arcpy.ListFields(out_table)]
        focus_fields = []
        for code in focus.keys():
            for f in fields:
                if f.upper() == f"VALUE_{code}":
                    focus_fields.append((code, f))
                    break

        with open(out_focus_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            header = [name_field] + [f"{code}_{focus[code]['label']}_m2"
                                     for code, _ in focus_fields]
            w.writerow(header)
            cursor_fields = [name_field] + [f for _, f in focus_fields]
            with arcpy.da.SearchCursor(out_table, cursor_fields) as cur:
                for row in cur:
                    w.writerow(row)


# ---------- 6.2 ----------

def leisuring_rate(cfg) -> None:
    log.info("[6.2] Per-admin leisuring rate from binary change")
    change = os.path.join(cfg.paths.derivatives, "Change_1984_to_2020_UTM.tif")
    if not arc_utils.exists(change):
        log.warning("  %s missing, skipping", change); return

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "Change_Stats_by_Admin")
    if not arc_utils.exists(out_table):
        log.info("  ZonalStatisticsAsTable (SUM + COUNT via ALL)")
        arcpy.sa.ZonalStatisticsAsTable(
            in_zone_data=admin,
            zone_field=name_field,
            in_value_raster=change,
            out_table=out_table,
            statistics_type="ALL",
        )
    # Compute pct_changed = SUM / COUNT * 100 (Change raster is selfMasked => SUM is changed-cell count)
    if "pct_changed" not in [f.name for f in arcpy.ListFields(out_table)]:
        arcpy.management.AddField(out_table, "pct_changed", "DOUBLE")
    arcpy.management.CalculateField(
        out_table, "pct_changed",
        "(!SUM! / !COUNT!) * 100 if !COUNT! else None",
        "PYTHON3",
    )

    # Join pct_changed back to the admin feature class as a permanent field
    log.info("  joining pct_changed back to %s", Path(admin).name)
    if "pct_changed" not in [f.name for f in arcpy.ListFields(admin)]:
        arcpy.management.AddField(admin, "pct_changed", "DOUBLE")
    arcpy.management.JoinField(
        in_data=admin,
        in_field=name_field,
        join_table=out_table,
        join_field=name_field,
        fields="pct_changed",
    )

    out_csv = os.path.join(cfg.paths.outputs, "leisuring_rate_by_admin.csv")
    _write_table_to_csv(out_table, out_csv)
    log.info("  wrote %s", out_csv)


# ---------- 6.3 ----------

def coastline_change(cfg) -> None:
    log.info("[6.3] Coastline change (quick method)")
    early_idx = next((e for e in cfg.gee_inputs.composites
                      if e.epoch_label == "1984_86"), None)
    recent_idx = next((e for e in cfg.gee_inputs.composites
                       if e.epoch_label == "2020"), None)
    if not (early_idx and recent_idx):
        log.warning("  composites missing, skipping"); return

    mndwi_early = os.path.join(cfg.paths.derivatives,
                               f"MNDWI_{early_idx.epoch_label}.tif")
    mndwi_recent = os.path.join(cfg.paths.derivatives,
                                f"MNDWI_{recent_idx.epoch_label}.tif")
    if not (arc_utils.exists(mndwi_early) and arc_utils.exists(mndwi_recent)):
        log.warning("  MNDWI extracts missing, skipping"); return

    thr = cfg.analyses.coastline_retreat.mndwi_water_threshold

    from arcpy.sa import Con
    for src, tag in ((mndwi_early, early_idx.epoch_label),
                     (mndwi_recent, recent_idx.epoch_label)):
        water_path = os.path.join(cfg.paths.derivatives, f"Water_{tag}.tif")
        if arc_utils.exists(water_path):
            log.info("  [skip] %s", water_path); continue
        log.info("  threshold MNDWI > %s -> %s", thr, Path(water_path).name)
        result = Con(arcpy.sa.Raster(src) > thr, 1, 0)
        result.save(water_path)

    # Polygonize each water mask, dissolve to one feature per side
    water_polys = {}
    for tag in (early_idx.epoch_label, recent_idx.epoch_label):
        in_r = os.path.join(cfg.paths.derivatives, f"Water_{tag}.tif")
        out_p = arc_utils.in_gdb(cfg, f"Water_Poly_{tag}")
        if arc_utils.exists(out_p):
            log.info("  [skip] %s", out_p)
        else:
            arcpy.conversion.RasterToPolygon(in_r, out_p,
                                              "NO_SIMPLIFY", "Value")
        water_polys[tag] = out_p

    # Land = inverse of water. Easiest: select polygons where gridcode = 0
    land_polys = {}
    for tag, wp in water_polys.items():
        out_land = arc_utils.in_gdb(cfg, f"Land_Poly_{tag}")
        if arc_utils.exists(out_land):
            log.info("  [skip] %s", out_land)
        else:
            arcpy.analysis.Select(wp, out_land, '"gridcode" = 0')
        land_polys[tag] = out_land

    # Erase: land lost between epochs (early land - recent land)
    early_tag = early_idx.epoch_label
    recent_tag = recent_idx.epoch_label
    loss_fc = arc_utils.in_gdb(cfg, f"CoastLoss_{early_tag}_to_{recent_tag}")
    if not arc_utils.exists(loss_fc):
        log.info("  Erase early-land - recent-land -> %s", Path(loss_fc).name)
        arcpy.analysis.Erase(land_polys[early_tag], land_polys[recent_tag], loss_fc)
        # Add area_m2
        arcpy.management.CalculateGeometryAttributes(
            loss_fc, [["area_m2", "AREA"]], area_unit="SQUARE_METERS",
        )
    else:
        log.info("  [skip] %s", loss_fc)

    out_csv = os.path.join(cfg.paths.outputs, "coastline_loss_polygons.csv")
    _write_table_to_csv(loss_fc, out_csv)
    log.info("  wrote %s", out_csv)


# ---------- 6.4 ----------

def urban_expansion(cfg) -> None:
    log.info("[6.4] Urban expansion 1985 -> 2020")
    from arcpy.sa import Con, Raster

    urban_val = cfg.analyses.urban_expansion.urban_class_value
    early = os.path.join(cfg.paths.derivatives, "Classified_1984_1986_UTM.tif")
    recent = os.path.join(cfg.paths.derivatives, "Classified_2020_UTM.tif")
    if not (arc_utils.exists(early) and arc_utils.exists(recent)):
        log.warning("  classified rasters missing, skipping"); return

    urban_early = os.path.join(cfg.paths.derivatives, "Urban_1985.tif")
    urban_recent = os.path.join(cfg.paths.derivatives, "Urban_2020.tif")
    expansion = os.path.join(cfg.paths.derivatives, "Urban_Expansion.tif")

    if not arc_utils.exists(urban_early):
        log.info("  binary Urban_1985")
        Con(Raster(early) == urban_val, 1, 0).save(urban_early)
    if not arc_utils.exists(urban_recent):
        log.info("  binary Urban_2020")
        Con(Raster(recent) == urban_val, 1, 0).save(urban_recent)
    if not arc_utils.exists(expansion):
        log.info("  Urban_Expansion = Urban_2020 - Urban_1985")
        (Raster(urban_recent) - Raster(urban_early)).save(expansion)
    else:
        log.info("  [skip] %s", expansion)

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, "UrbanExpansion_by_Admin")
    if not arc_utils.exists(out_table):
        arcpy.sa.TabulateArea(admin, name_field, expansion, "Value", out_table,
                              processing_cell_size=30)
    _write_table_to_csv(out_table,
        os.path.join(cfg.paths.outputs, "urban_expansion_by_admin.csv"))


# ---------- 6.5 ----------

def esri_recent_change(cfg) -> None:
    log.info("[6.5] Esri/IO recent change")
    from arcpy.sa import Combine

    early_y = cfg.analyses.esri_recent_change.early_year
    recent_y = cfg.analyses.esri_recent_change.recent_year
    early = os.path.join(cfg.paths.derivatives, f"LC_{early_y}_C8.tif")
    recent = os.path.join(cfg.paths.derivatives, f"LC_{recent_y}_C8.tif")
    if not (arc_utils.exists(early) and arc_utils.exists(recent)):
        log.warning("  C8 reclassified annuals missing, skipping"); return

    out_combo = os.path.join(cfg.paths.derivatives,
                              f"FromTo_S2_{early_y}_to_{recent_y}.tif")
    if not arc_utils.exists(out_combo):
        log.info("  Combine %d + %d", early_y, recent_y)
        Combine([early, recent]).save(out_combo)
    else:
        log.info("  [skip] %s", out_combo)

    admin, name_field = _admin_layer(cfg)
    out_table = arc_utils.in_gdb(cfg, f"Transitions_S2_by_Admin_{early_y}_{recent_y}")
    if not arc_utils.exists(out_table):
        arcpy.sa.TabulateArea(admin, name_field, out_combo, "Value", out_table,
                              processing_cell_size=10)
    _write_table_to_csv(out_table,
        os.path.join(cfg.paths.outputs,
                     f"transitions_s2_{early_y}_to_{recent_y}.csv"))


# ---------- entry point ----------

def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 6 — Core analyses")
    log.info("=" * 60)
    arc_utils.configure_env(cfg)

    with arc_utils.extension("Spatial"):
        for label, fn in (
            ("transition_matrix", transition_matrix),
            ("leisuring_rate",    leisuring_rate),
            ("coastline_change",  coastline_change),
            ("urban_expansion",   urban_expansion),
            ("esri_recent_change", esri_recent_change),
        ):
            try:
                fn(cfg)
            except FileNotFoundError as exc:
                log.warning("  [%s] %s", label, exc)
            except arcpy.ExecuteError as exc:
                log.error("  [%s] arcpy: %s", label, exc)
            except Exception:  # noqa: BLE001
                log.exception("  [%s] unexpected error", label)

    log.info("  Phase 6 complete.")
