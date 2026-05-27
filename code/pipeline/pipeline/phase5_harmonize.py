"""Phase 5 — Harmonize Esri/IO LC to Copernicus 8-class + cross-comparison.

  5.1 Apply class color symbology to classified rasters (writes .lyrx)
  5.2 Reclassify each Esri/IO annual LC to Copernicus 8-class
  5.3 Combine the 2020 Copernicus-classified raster with the Esri C8
      2020 raster to produce an agreement matrix + overall agreement %.
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

import arcpy

from . import arc_utils

log = logging.getLogger(__name__)


def _build_remap(cfg):
    """Build a RemapValue list usable by sa.Reclassify."""
    remap_pairs = []
    raw_remap = cfg._raw["esri_to_copernicus_remap"]
    for k, v in raw_remap.items():
        if k == "nodata_classes":
            continue
        remap_pairs.append([int(k), int(v)])
    for nd in raw_remap.get("nodata_classes", []):
        remap_pairs.append([int(nd), "NODATA"])
    return remap_pairs


def _reclassify_esri_annual(cfg, remap) -> list[str]:
    from arcpy.sa import Reclassify, RemapValue

    out_paths: list[str] = []
    for year in cfg.esri_s2.years:
        src = os.path.join(cfg.paths.derivatives, f"LC_{year}_UTM.tif")
        if not arc_utils.exists(src):
            log.warning("  %s missing, skipping reclassify", src)
            continue
        dst = os.path.join(cfg.paths.derivatives, f"LC_{year}_C8.tif")
        if arc_utils.exists(dst):
            log.info("  [skip] %s already exists", dst)
            out_paths.append(dst)
            continue
        log.info("  reclassify %s -> Copernicus 8-class", Path(src).name)
        result = Reclassify(src, "Value", RemapValue(remap), "NODATA")
        result.save(dst)
        out_paths.append(dst)
    return out_paths


def _apply_classified_symbology(cfg) -> None:
    """Write a .clr colormap file so Pro picks up the palette automatically."""
    palette = cfg._raw["copernicus_8class"]["palette"]
    clr_path = os.path.join(cfg.paths.derivatives, "copernicus_8class.clr")
    with open(clr_path, "w", encoding="utf-8") as fh:
        for code, info in sorted(palette.items()):
            hex_col = info["hex"].lstrip("#")
            r, g, b = (int(hex_col[i:i+2], 16) for i in (0, 2, 4))
            fh.write(f"{code} {r} {g} {b}\n")
    log.info("  wrote colormap %s", clr_path)

    # Apply to every classified-style raster
    targets = []
    for entry in cfg.gee_inputs.categorical:
        if entry.kind == "classification":
            p = os.path.join(cfg.paths.derivatives, f"{entry.name}_UTM.tif")
            if arc_utils.exists(p):
                targets.append(p)
    for year in cfg.esri_s2.years:
        p = os.path.join(cfg.paths.derivatives, f"LC_{year}_C8.tif")
        if arc_utils.exists(p):
            targets.append(p)

    for p in targets:
        try:
            log.info("  apply colormap to %s", Path(p).name)
            arcpy.management.AddColormap(p, "#", clr_path)
        except arcpy.ExecuteError as exc:
            log.warning("  AddColormap on %s: %s", Path(p).name, exc)


def _cross_compare_2020(cfg) -> None:
    """Combine Copernicus-2020 and Esri-C8-2020; report % agreement."""
    from arcpy.sa import Combine

    cop = os.path.join(cfg.paths.derivatives, "Classified_2020_UTM.tif")
    esri = os.path.join(cfg.paths.derivatives, "LC_2020_C8.tif")
    if not (arc_utils.exists(cop) and arc_utils.exists(esri)):
        log.warning("  cross-comparison skipped (need both 2020 layers)")
        return

    out = os.path.join(cfg.paths.derivatives, "Agreement_2020.tif")
    if not arc_utils.exists(out):
        log.info("  Combine Copernicus + Esri 2020 -> %s", Path(out).name)
        Combine([cop, esri]).save(out)
    else:
        log.info("  [skip] %s already exists", out)

    # Compute overall agreement: rows where the two class fields are equal
    # The two value fields are named after the input raster basenames.
    fields = [f.name for f in arcpy.ListFields(out)]
    val_fields = [f for f in fields if f.upper().startswith("CLASSIFIED_2020")
                  or f.upper().startswith("LC_2020_C8")]
    if len(val_fields) < 2:
        # Fallback: pick the last two numeric fields that aren't OBJECTID / Value / Count
        val_fields = [f.name for f in arcpy.ListFields(out, field_type="Integer")
                      if f.name.lower() not in ("objectid", "value", "count")][-2:]

    if len(val_fields) < 2:
        log.warning("  could not identify agreement fields; skipping summary")
        return

    log.info("  computing agreement on fields %s", val_fields)
    total = 0
    agree = 0
    with arcpy.da.SearchCursor(out, val_fields + ["Count"]) as cur:
        for row in cur:
            a, b, c = row
            total += c
            if a == b:
                agree += c

    pct = 100.0 * agree / total if total else 0.0
    log.info("  Overall 2020 agreement: %.2f%% (%d / %d cells)",
             pct, agree, total)

    summary = os.path.join(cfg.paths.outputs, "agreement_2020.csv")
    with open(summary, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "value"])
        w.writerow(["overall_agreement_pct", f"{pct:.4f}"])
        w.writerow(["agree_cells", agree])
        w.writerow(["total_cells", total])
    log.info("  wrote %s", summary)


def run(cfg) -> None:
    log.info("=" * 60)
    log.info("Phase 5 — Harmonize + cross-comparison")
    log.info("=" * 60)
    arc_utils.configure_env(cfg)

    with arc_utils.extension("Spatial"):
        remap = _build_remap(cfg)
        log.info("  Esri/IO -> Copernicus remap: %s", remap)
        _reclassify_esri_annual(cfg, remap)
        _apply_classified_symbology(cfg)
        _cross_compare_2020(cfg)

    log.info("  Phase 5 complete.")
