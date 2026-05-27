"""Phase 7 — Augment listings with raster-derived attributes.

For every listing point: pull NDVI/MNDWI/Temp/Urban_Expansion/distance-to-
coast and the C8 class at that location, plus the parish-level pct_changed
joined from the admin layer. Output: Listings_<name>_aug feature class
and a paired CSV ready for regression in Phase 8.
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _listings_layer(cfg):
    for v in cfg.vectors:
        if v.role == "listings":
            p = os.path.join(cfg.paths.geodatabase, v.gdb_target)
            if arc_utils.exists(p):
                return v, p
    return None, None


def _admin_layer(cfg):
    for v in cfg.vectors:
        if v.role == "admin":
            p = os.path.join(cfg.paths.geodatabase, v.gdb_target)
            name_field = getattr(v, "name_field", "name")
            return v, p, name_field
    return None, None, None


def _coastline_layer(cfg):
    for v in cfg.vectors:
        if v.role == "coastline":
            p = os.path.join(cfg.paths.geodatabase, v.gdb_target)
            return p if arc_utils.exists(p) else None
    return None


def _ensure_distance_to_coast(cfg) -> str | None:
    coast = _coastline_layer(cfg)
    if not coast:
        log.warning("  no coastline available; skipping distance-to-coast")
        return None
    out = os.path.join(cfg.paths.derivatives, "DistToCoast.tif")
    if arc_utils.exists(out):
        log.info("  [skip] %s exists", out); return out
    log.info("  Euclidean Distance from coastline -> %s", Path(out).name)
    arcpy.sa.EucDistance(coast).save(out)
    return out


def _build_extract_list(cfg, dist_to_coast: str | None) -> list[tuple[str, str]]:
    """Return list of (raster_path, output_field_name)."""
    items: list[tuple[str, str]] = []
    der = cfg.paths.derivatives

    # Indices for 2020 (the era of listings)
    for band in ("NDVI", "MNDWI", "TEMP"):
        p = os.path.join(der, f"{band}_2020.tif")
        if arc_utils.exists(p):
            items.append((p, f"{band}_2020"))

    # Urban expansion + classes
    for r, fname in (
        ("Urban_Expansion.tif", "Urban_Expansion"),
        ("Classified_2020_UTM.tif", "class_2020"),
        ("FromTo_1984_to_2020_UTM.tif", "fromto_code"),
    ):
        p = os.path.join(der, r)
        if arc_utils.exists(p):
            items.append((p, fname))

    if dist_to_coast and arc_utils.exists(dist_to_coast):
        items.append((dist_to_coast, "dist_to_coast_m"))

    # Esri C8 most recent year
    recent_year = cfg.analyses.esri_recent_change.recent_year
    p = os.path.join(der, f"LC_{recent_year}_C8.tif")
    if arc_utils.exists(p):
        items.append((p, f"esri_class_{recent_year}"))

    # v8 series — if Phase 2b has run, pick up the most useful derivatives
    v8_extras = [
        ("BecameUrban_v8c_UTM.tif",            "became_urban_v8"),
        ("SugarcaneConversion_v8c_UTM.tif",    "sugarcane_conv_v8"),
        ("CCDC_FirstBreakYear_v8c_UTM.tif",    "ccdc_first_break_yr"),
        ("CCDC_nBreaks_v8c_UTM.tif",           "ccdc_n_breaks"),
        ("ManicuringIndex_10m_v8f_UTM.tif",    "manicuring_10m"),
        ("ManicuringIndex_v8c_UTM.tif",        "manicuring_30m"),
        ("NDVI_Trend_10m_v8f_UTM.tif",         "ndvi_trend_10m"),
        ("Classification_10m_v8f_UTM.tif",     "class_10m_v8f"),
        ("Classified_2019_25_v8c_UTM.tif",     "class_2019_25_v8c"),
        ("Uncertainty_Flag.tif",               "uncertainty_flag"),
    ]
    for fname, alias in v8_extras:
        p = os.path.join(der, fname)
        if arc_utils.exists(p):
            items.append((p, alias))

    return items


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 7 — Listings integration")
    log.info("=" * 60)
    arc_utils.configure_env(cfg)

    listings_cfg, listings_fc = _listings_layer(cfg)
    if not listings_fc:
        log.warning("  no listings feature class; phase skipped"); return

    aug_fc = listings_fc + "_aug"
    if not arc_utils.exists(aug_fc):
        log.info("  copying %s -> _aug", Path(listings_fc).name)
        arcpy.management.CopyFeatures(listings_fc, aug_fc)
    else:
        log.info("  [skip] %s already exists", aug_fc)

    with arc_utils.extension("Spatial"):
        dist_to_coast = _ensure_distance_to_coast(cfg)
        extract_list = _build_extract_list(cfg, dist_to_coast)

        if extract_list:
            log.info("  ExtractMultiValuesToPoints (%d rasters)", len(extract_list))
            try:
                arcpy.sa.ExtractMultiValuesToPoints(
                    in_point_features=aug_fc,
                    in_rasters=extract_list,
                    bilinear_interpolate_values="NONE",
                )
            except arcpy.ExecuteError as exc:
                log.error("  ExtractMultiValuesToPoints: %s", exc)

    # Spatial join with admin to pull pct_changed + admin name
    _, admin_fc, name_field = _admin_layer(cfg)
    if admin_fc and arc_utils.exists(admin_fc):
        joined = aug_fc + "_admin"
        if not arc_utils.exists(joined):
            log.info("  SpatialJoin with admin -> %s", Path(joined).name)
            arcpy.analysis.SpatialJoin(
                target_features=aug_fc,
                join_features=admin_fc,
                out_feature_class=joined,
                join_operation="JOIN_ONE_TO_ONE",
                join_type="KEEP_ALL",
                match_option="INTERSECT",
            )
            # Promote the joined version as the canonical augmented FC
            arcpy.management.Delete(aug_fc)
            arcpy.management.Rename(joined, aug_fc)

    # Optional log-price column
    if getattr(cfg.spatial_stats, "log_transform_dependent", False):
        existing_fields = {f.name for f in arcpy.ListFields(aug_fc)}
        if "price" in existing_fields and "price_log" not in existing_fields:
            log.info("  adding price_log column")
            arcpy.management.AddField(aug_fc, "price_log", "DOUBLE")
            arcpy.management.CalculateField(
                aug_fc, "price_log",
                "math.log(!price!) if !price! and !price! > 0 else None",
                "PYTHON3",
            )

    # Encode listing_type as integer code if present
    if "listing_type" in {f.name for f in arcpy.ListFields(aug_fc)} \
            and "listing_type_code" not in {f.name for f in arcpy.ListFields(aug_fc)}:
        log.info("  encoding listing_type -> listing_type_code")
        types: dict[str, int] = {}
        with arcpy.da.SearchCursor(aug_fc, ["listing_type"]) as cur:
            for (t,) in cur:
                if t is None: continue
                types.setdefault(str(t), len(types) + 1)
        arcpy.management.AddField(aug_fc, "listing_type_code", "LONG")
        with arcpy.da.UpdateCursor(aug_fc, ["listing_type", "listing_type_code"]) as cur:
            for row in cur:
                row[1] = types.get(str(row[0])) if row[0] is not None else None
                cur.updateRow(row)
        log.info("  listing_type encoding: %s", types)

    # Dump to CSV
    out_csv = os.path.join(cfg.paths.outputs, "listings_augmented.csv")
    fields = [f.name for f in arcpy.ListFields(aug_fc)
              if f.type not in ("Geometry",) and f.name.lower() != "shape"]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        with arcpy.da.SearchCursor(aug_fc, fields) as cur:
            for row in cur:
                w.writerow(row)
    log.info("  wrote %s", out_csv)
    log.info("  Phase 7 complete.")
