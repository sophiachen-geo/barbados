# GEE v8 Series — Integration Notes

The Google Drive folder `H:/My Drive/Barbados/` contains a much richer GEE deliverable than what we built earlier. It's now wired into the pipeline as **Phase 2b (ingest)** and **Phase 6b (analyses)**, alongside everything that was already there. The original `Inputs_GEE/` pipeline (scripts 01-04 outputs) still runs in Phase 2 / Phase 6 — the v8 series is purely additive.

## What's new

| Raster | What it is | Why it matters |
|---|---|---|
| `Classified_1984_92_v8c` … `Classified_2019_25_v8c` | **Five** epoch classifications, ~9-year windows | Gives us 4 consecutive transition matrices instead of one 1984→2020 jump. Lets you separate the 1980s sugarcane decline, the 1990s suburbanisation, the 2000s tourism boom, the 2010s densification |
| `BecameUrban_v8c` | Direct binary mask of pixels that became urban | Saves us from deriving urban-expansion in Phase 6.4; cleaner |
| `SugarcaneConversion_v8c` | Pixels that switched from sugarcane to something else | **Barbados-specific** — direct plantation-decline metric. Maps the 1990s-2010s collapse of sugar |
| `CCDC_FirstBreakYear_v8c` | Year of first detected change per pixel | Lets you say *when* each pixel changed, not just *whether*. Histogram by parish answers "did St. James change later/earlier than St. Joseph?" |
| `CCDC_nBreaks_v8c` | Number of CCDC breaks per pixel | High n = unstable / repeatedly changing land use (construction sites, abandonment cycles) |
| `ManicuringIndex_v8c` / `_10m_v8f` | Continuous index of "manicured" vegetation | **Golf courses, resort lawns, hotel grounds** — the exact tourism-infrastructure signal your project hypothesis predicts |
| `SeasonalAmplitude_v8c` / `_10m_v8f` | Phenology amplitude | Separates cropping cycles (high amplitude) from natural / built (low amplitude) |
| `SeasonalPhase_v8c` / `_10m_v8f` | Phenology phase | Distinguishes sugarcane (specific phenology peak) from other vegetation |
| `Disagreement_v8c`, `Consensus_5way_v8c` | Multi-method classifier (dis)agreement | Quantifies pixel-level classification uncertainty rigorously |
| `Trajectory_5bin_v8c` | 5-class temporal trajectory categorisation | Pre-classified trajectory types (e.g. "stable forest", "ag→urban", "natural→manicured") |
| `Classification_10m_v8f` | 10 m Sentinel-2 classification | **Finer resolution** than 30 m Landsat — captures hotel footprints, road widths, individual properties |
| `Certainty_10m_v8f`, `Certainty_2019_2021_v8c` | Pixel certainty rasters | Use as weights in regression, or as masks |
| `NDVI_Trend_10m_v8f` | NDVI slope per year (10 m) | **Direct loss-of-green-space signal**. Negative slope = browning / vegetation loss |
| `S1_SAR_Stack_10m_v8f` | Sentinel-1 SAR backscatter stack | Cloud-independent built-up detection; useful for QA in cloudy West Coast scenes |
| `RF_2019_2021_v8c` | Single-model RF classification | Comparison to Consensus_5way |
| `SpatialCV_byParish_v8c.csv` | Per-parish accuracy + kappa | **Critical QA — see below** |

## CRITICAL: parish-level classifier quality

The `SpatialCV_byParish_v8c.csv` shows the classifier's per-parish hold-out accuracy. Several parishes are **unreliable**:

| Parish | Accuracy | Kappa | n_test | Verdict |
|---|---:|---:|---:|---|
| St. Michael | 0.915 | 0.414 | 540 | Good |
| St. Andrew | 0.887 | 0.201 | 257 | Accuracy inflated by class imbalance |
| Christ Church | 0.841 | 0.691 | 176 | **Excellent** (highest kappa) |
| St. Phillip | 0.845 | 0.517 | 769 | Good |
| St. Joseph | 0.791 | 0.142 | 761 | Imbalanced |
| St. Peter | 0.682 | 0.379 | 428 | Acceptable |
| St. Tomas | 0.604 | 0.411 | 96 | Small n |
| St. George | 0.539 | 0.086 | 762 | **Poor** |
| St. Lucy | 0.487 | 0.107 | 528 | **Poor** |
| **St. James** | **0.186** | **0.030** | 566 | **Classifier fails** — this is the Platinum Coast |
| **St. John** | **0.065** | **0.030** | 1558 | **Classifier fails** |

**Implications for your project**

1. **St. James is THE tourism parish** and the classifier essentially doesn't work there at 30 m. Any parish-level finding for St. James from the v8c rasters needs to:
   - Be cross-checked against `Classification_10m_v8f` (Sentinel-2 fine-resolution), which uses different inputs and may not share the same failure mode, OR
   - Be reported with an explicit uncertainty caveat citing the 0.186 / 0.03 CV result.

2. The `Uncertainty_Flag` raster Phase 6b.7 produces combines `Disagreement_v8c ≥ 2` and `Certainty_2019_2021_v8c < 0.5`. Phase 7 extracts it as `uncertainty_flag` onto every listing. Drop or down-weight listings with `uncertainty_flag = 1` in your Phase 8 regressions.

3. Report the spatial-CV table as a methods-section table in any publication. Reviewers will ask.

## How the pipeline now runs

```powershell
cd C:\Users\sochen\Documents\ArcGIS\Projects\Barbados\Pipeline

# Full run (now 12 phases instead of 10)
python run_pipeline.py --config config/barbados.yaml

# Just the new v8 ingest + analyses
python run_pipeline.py --config config/barbados.yaml --phases 2b,6b

# Inventory check — will report what's missing from H: drive
python run_pipeline.py --config config/barbados.yaml --phase 0

# Re-run a range that includes the v8 phases
python run_pipeline.py --config config/barbados.yaml --phases 2-6b
```

## New outputs (under `Outputs/`)

| File | From | What it is |
|---|---|---|
| `spatial_cv_by_parish_v8c.csv` | Phase 2b | Copy of the H: drive CV table |
| `transitions_v8c_1984_to_2001_by_admin.csv` | Phase 6b.1 | 1984-92 → 1993-01 per parish |
| `transitions_v8c_1993_to_2010_by_admin.csv` | Phase 6b.1 | 1993-01 → 2002-10 per parish |
| `transitions_v8c_2002_to_2018_by_admin.csv` | Phase 6b.1 | 2002-10 → 2011-18 per parish |
| `transitions_v8c_2011_to_2025_by_admin.csv` | Phase 6b.1 | 2011-18 → 2019-25 per parish |
| `became_urban_by_admin.csv` | Phase 6b.2 | Direct urban-conversion % per parish |
| `sugarcane_conversion_by_admin.csv` | Phase 6b.3 | Sugarcane → other m² per parish |
| `ccdc_first_break_year_by_admin.csv` | Phase 6b.4 | Histogram of change-detection year per parish |
| `manicuring_hotspots_by_admin.csv` | Phase 6b.5 | Manicured-pixel count per parish (golf/resort) |
| `ndvi_trend_by_admin.csv` | Phase 6b.6 | Mean NDVI slope per parish (10 m) |
| `ndvi_browning_share_by_admin.csv` | Phase 6b.6 | Fraction of pixels with significant negative NDVI trend |

And under `Derivatives/`:

| File | Use |
|---|---|
| `<everything>_UTM.tif` for each v8c/v8f raster | Projected versions for ArcGIS Pro layer-loading |
| `FromTo_v8c_<early>_to_<recent>.tif` (×4) | Source rasters for 6b.1 tables |
| `Manicured_Mask.tif` | Binary mask of manicured-vegetation pixels |
| `CCDC_FirstBreakYear_binned.tif` | Year-bins of first CCDC break (codes 1-N from config) |
| `NDVI_Browning_Mask.tif` | Pixels with NDVI slope below the significance threshold |
| `Uncertainty_Flag.tif` | 1 = treat with caution (used by Phase 7) |

## New columns auto-joined onto listings in Phase 7

When Phase 7 runs after 2b/6b, the augmented `Listings_7thHeaven_aug` feature class gains these fields automatically:

- `became_urban_v8`, `sugarcane_conv_v8`
- `ccdc_first_break_yr`, `ccdc_n_breaks`
- `manicuring_30m`, `manicuring_10m`
- `ndvi_trend_10m`
- `class_10m_v8f`, `class_2019_25_v8c`
- `uncertainty_flag`

So Phase 8's GLR/GWR can now use vastly richer explanatory variables. Suggested additions to `spatial_stats.explanatory_variables` in `barbados.yaml` after Phase 7 has populated them:

```yaml
spatial_stats:
  explanatory_variables:
    - rooms
    - pool
    - gated
    - listing_type_code
    - NDVI_2020
    - dist_to_coast_m
    - pct_changed
    # v8 additions:
    - manicuring_10m        # tourism-infrastructure intensity at the listing
    - ndvi_trend_10m        # local greening/browning trend
    - ccdc_n_breaks         # land-use instability
    - became_urban_v8       # binary: did this pixel urbanise?
```

Drop a row if `uncertainty_flag = 1` in your pre-regression filter:

```python
arcpy.management.MakeFeatureLayer(
    aug_fc, "listings_certain", '"uncertainty_flag" = 0 OR "uncertainty_flag" IS NULL'
)
# Run GLR/GWR on listings_certain instead of aug_fc
```

(I haven't auto-wired that filter into Phase 8 because the threshold is a methodological choice you should make explicitly.)

## What the v8 series doesn't fix

- The unreliable parishes (St. James, St. John, St. George, St. Lucy) are unreliable because of the underlying training data / class definitions, not the algorithm. The 10 m v8f run *may* perform better there (different sensor, different training), but you still need a sanity check pass — visually compare `Classification_10m_v8f` to recent high-res imagery for St. James specifically.
- The `Trajectory_5bin_v8c` raster is pre-classified; we expose it but don't know what the 5 bins mean without your GEE script's `remap` step. **Add a `trajectory_bin_definitions` block to the YAML** once you can confirm what each bin code represents — then the per-parish trajectory composition becomes a one-liner.
- Health outcomes aren't joined yet (no parish-level CVD data exists publicly). When/if you obtain the BNR parish-level CVD breakdown, add it as a vector role and Phase 7 will join it automatically.
