# Regional Tourism / Land-Cover Pipeline

Config-driven arcpy automation of the ArcGIS Pro protocol from your roadmap. The same code runs Barbados today and Newfoundland tomorrow — only the YAML config swaps.

```
Pipeline/
├── README.md
├── V8_INTEGRATION_NOTES.md     <- v8 series specifics (READ THIS for the H: drive rasters)
├── requirements.txt
├── run_pipeline.py             <- CLI entry point
├── config/
│   ├── barbados.yaml           <- ready to run
│   └── newfoundland.yaml       <- skeleton with TODOs for your NL inputs
└── pipeline/
    ├── arc_utils.py            <- shared arcpy helpers
    ├── config.py               <- YAML loader
    ├── logging_utils.py
    ├── phase0_inventory.py     <- file-presence check (incl. H: drive v8 files)
    ├── phase1_setup.py         <- folders + gdb + feature dataset
    ├── phase2_ingest_gee.py    <- project script-04 GEE rasters, extract NDVI/MNDWI/temp
    ├── phase2b_ingest_gee_v8.py<- v8 series from H:/My Drive/Barbados (NEW)
    ├── phase3_ingest_esri_s2.py<- annual S2 LC -> Mosaic Dataset (multidim)
    ├── phase4_ingest_vectors.py<- shapefiles + CSV listings -> gdb
    ├── phase5_harmonize.py     <- reclassify Esri->Copernicus + 2020 agreement
    ├── phase6_analyses.py      <- transition matrix, leisuring rate, coast, urban, S2 recent
    ├── phase6b_v8_analyses.py  <- 5-epoch transitions, CCDC, sugarcane, manicuring, NDVI trend (NEW)
    ├── phase7_integration.py   <- extract raster values onto listings (incl. v8 covariates)
    ├── phase8_spatial_stats.py <- GLR, Exploratory, GWR, Hot Spots
    └── phase9_layouts.py       <- preloaded map + best-effort layout PNGs
```

## One-time setup

1. Open the **Python Command Prompt** that ships with ArcGIS Pro (Start menu → ArcGIS → Python Command Prompt). This activates the `arcgispro-py3` conda env where arcpy lives.
2. `cd C:\Users\sochen\Documents\ArcGIS\Projects\Barbados\Pipeline`
3. `pip install -r requirements.txt`  (just PyYAML — arcpy is already there)
4. Make sure your inputs are in place. Required for Barbados:
   - `Inputs_GEE/` — six TIFs from GEE script 04's Drive export
   - `Inputs_Esri_S2/` — `Barbados_LC_2017.tif` … `Barbados_LC_2024.tif`
   - `Inputs_Vector/` — Parishes, Roads, Coastline, Buildings, WorldPop, Listings CSV (see `config/barbados.yaml` for exact filenames)

   The pipeline tells you what's missing in Phase 0.

## Running

```powershell
# Whole pipeline, Barbados
python run_pipeline.py --config config/barbados.yaml

# Just one phase
python run_pipeline.py --config config/barbados.yaml --phase 6

# A range or list
python run_pipeline.py --config config/barbados.yaml --phases 5-8
python run_pipeline.py --config config/barbados.yaml --phases 2,5,7
```

Every run writes a timestamped log to `Pipeline/logs/`. Each phase is **idempotent** — outputs that already exist are skipped, so you can rerun freely.

## Phase-by-phase outputs

| Phase | What it writes | Where |
|---|---|---|
| 0 | Inventory report | console + log |
| 1 | `Barbados.gdb`, feature dataset `Vector`, scratch.gdb, folder tree | project root |
| 2 | `Derivatives/*_UTM.tif` (every GEE raster, projected) + per-band extracts `NDVI_2020.tif`, `MNDWI_1984_86.tif`, etc. | Derivatives |
| 3 | `Barbados.gdb/S2_LC_Mosaic` with Year + multidim info | gdb |
| 4 | Vectors imported under `Barbados.gdb/Vector/*` | gdb |
| 5 | `Derivatives/LC_<year>_C8.tif` (reclassified), `Agreement_2020.tif`, `outputs/agreement_2020.csv` | both |
| 6 | `outputs/transitions_by_admin.csv`, `outputs/leisuring_rate_by_admin.csv`, `outputs/coastline_loss_polygons.csv`, `outputs/urban_expansion_by_admin.csv`, `outputs/transitions_s2_2017_to_2024.csv`; matching `Derivatives/*` and gdb tables | both |
| 7 | `Barbados.gdb/Vector/Listings_7thHeaven_aug` + `outputs/listings_augmented.csv` | both |
| 8 | `Barbados.gdb/GLR_Listings`, `GWR_Listings`, `HotSpot_*`, `outputs/exploratory_regression.txt` | both |
| 9 | `Barbados_pipeline.aprx` with all derived layers loaded; PNGs of existing layouts | project root + outputs |

## Swapping to Newfoundland

1. Set up `C:\Users\sochen\Documents\ArcGIS\Projects\Newfoundland\` mirroring the Barbados structure (`Inputs_GEE/`, `Inputs_Esri_S2/`, `Inputs_Vector/`).
2. Re-run the GEE scripts (01-04) over a Newfoundland AOI and copy the outputs into `Inputs_GEE/`. (Note: NL is too large for `FAO/GAUL/2015/level0` — upload a custom AOI as a GEE asset and replace the AOI lines in the JS.)
3. Download Esri/IO annual LC for NL with the naming `NL_LC_2017.tif` … `NL_LC_2024.tif`.
4. Drop in NL vector layers (Census Subdivisions, roads, coastline, etc.) — update `config/newfoundland.yaml` paths and `name_field` to match your StatCan attribute table.
5. Run:
   ```powershell
   python run_pipeline.py --config config/newfoundland.yaml
   ```

The class-color palette, the Copernicus 8-class target schema, the GEE band-name list, and every analysis parameter are all in the YAML — no code edits.

## Things the pipeline doesn't try to do

| Excluded | Why | Workaround |
|---|---|---|
| DSAS (rigorous coastline transects) | Not arcpy — separate Esri-released add-in | Phase 6.3 produces the *quick* loss polygons; install DSAS for transect-level rates |
| Geocoding from address strings | Needs an ArcGIS Online locator and credentials | Geocode before ingest (Nominatim / Google) and ship a CSV with lon/lat columns |
| Aesthetic layout polish | Cartography is human work | Phase 9 stages every layer in a map; you tweak label placement, legends, north arrow in Pro |
| Esri/IO download | Requires AGOL login | Manual download into `Inputs_Esri_S2/` (see climat.esri.ca) |
| LandTrendr | Different module (`GEE_Scripts/LandTrendr_Walkthrough.md`) | Run the GUI walkthrough separately; ingest its asset exports as additional categorical rasters |

## Re-running individual analyses

Phase 6 is internally split into five independent functions. If you only want to refresh the urban-expansion analysis after changing the `urban_class_value` in YAML:

```powershell
# Delete the stale outputs so the idempotency check rebuilds them
del Derivatives\Urban_*.tif
python run_pipeline.py --config config/barbados.yaml --phase 6
```

Every analysis function is wrapped in a `try/except` so one failure doesn't abort the rest of Phase 6.

## Troubleshooting

- **`PyYAML is required`** — open the *Python Command Prompt* from ArcGIS Pro, not your normal terminal. The system Python won't have arcpy.
- **`Could not check out Spatial extension`** — your ArcGIS Pro license doesn't include Spatial Analyst. Most analyses are SA-dependent; the pipeline can't proceed without it.
- **`schema lock` errors** — close ArcGIS Pro before rerunning (the gdb is locked when the app is open and a layer references the same FC).
- **TabulateArea writes zeros** — check that the admin polygons and the input raster actually overlap. Run `arcpy.Describe(<path>).extent` on both in Pro's Python window.
- **GLR/GWR fail with "perfect multicollinearity"** — Phase 8.2 (Exploratory Regression) reports VIFs; drop the highest-VIF explanatory variable in YAML and rerun Phase 8.
