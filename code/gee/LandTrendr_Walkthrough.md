# LandTrendr GUI Walkthrough — Barbados Time-Series Change

Companion to the SERVIR-Amazonia time-series-change1 module:
- https://servir-amazonia.github.io/barbados-training/time-series-change1/introduction.html
- https://servir-amazonia.github.io/barbados-training/time-series-change1/lt-tutorial-1.html
- https://servir-amazonia.github.io/barbados-training/time-series-change1/lt-tutorial-2.html
- https://servir-amazonia.github.io/barbados-training/time-series-change1/challenge.html

Unlike the land-cover-mapping module (which is hand-written JavaScript), this module drives the pre-built **LandTrendr GUI** scripts in the `kwoodward` shared repository — there is no code for you to write. You open the scripts, configure parameters in the GUI panel, and click Run / Download. The notes below collect the parameter values the tutorial specifies so you can run the workflow end-to-end on Barbados.

## 0. Get access to the shared scripts

In the GEE Code Editor's left panel, under **Scripts → Reader**, you should see `users/kwoodward/caribbean-trainings`. If you don't, open this URL once while signed in to add the repo as a reader:

https://code.earthengine.google.com/?accept_repo=users/kwoodward/caribbean-trainings

The scripts you'll use:

| Script | Purpose |
|---|---|
| `2_LT-Data-Visualization` | Run LandTrendr on a Landsat NBR time series and download loss/gain rasters |
| `3_LTMakeLossGainPostprocessed` | Filter the raw loss/gain by year-of-detection, magnitude, etc. |
| `4_AssembleMap` | Combine post-processed loss + gain with a forest mask into a final categorical map |

## 1. Run `2_LT-Data-Visualization`

Open the script and click **Run**. The LandTrendr panel appears on the right.

**Asset overlay (top panel)** — load your AOI:
- Asset path: `projects/caribbean-trainings/assets/barbados-2022/CliftonHillAOI`
  (or `projects/caribbean-trainings/assets/barbados-2022/CattleWashAOI` for the alternate site)
- Layer name: anything memorable
- Check **"use this layer to constrain later analyses"**
- Click **Add asset to map**

**LandTrendr Options** — the segmentation parameters:
- Max Segments: `8`
- Spike Threshold: `0.9`
- Vertex Count Overshoot: `3`
- Prevent One Year Recovery: unchecked (false)
- Recovery Threshold: `0.5`
- p-value Threshold: `0.05`
- Best Model Proportion: `0.75`
- Min Observations Needed: `6`
- Image IDs to exclude: blank

**RGB Change Options** — for visual triptych:
- Red year: earliest year you want to inspect
- Green year: a middle year
- Blue year: latest year
- Click **Add RGB Imagery**

**Re-add the AOI** if it cleared, then in **Change Filter Options** run two passes and download each:

Loss pass:
- Change Type: `Loss`
- Change Sort: `Greatest`
- Filter by Year: checked, range = your full analysis window
- Click **Download**

Gain pass:
- Change Type: `Gain`
- Change Sort: `Newest`
- Filter by Year: unchecked (or set the same range)
- Click **Download**

**Download options:**
- EPSG: `4326`
- Output file name: your choice (will land in your Drive)

Each Download queues an Export task — go to **Tasks** and click Run on each.

## 2. Run `3_LTMakeLossGainPostprocessed`

Open the script, click **Run** to load its panel.

In the panel:
- Input asset paths: the **Loss** and **Gain** rasters you exported in step 1 (after their tasks finished — they need to exist as GEE assets, so use **Export to Asset** in step 1 if you haven't, or re-import the Drive GeoTIFFs)
- Red Year: first year of interest
- Blue Year: final year of interest
- YOD (Year of Detection) Min: first analysis year + 1
- Abrupt YOD Max: final year of interest
- End Year (Gain): final year of interest
- Export asset filename: your choice
- Tick **Export to Asset** (required for step 3)
- **Export to Drive** is optional

Click **Run**, then run each export task that appears under the **Tasks** tab.

A forest/non-forest mask is also used downstream:
`projects/caribbean-trainings/assets/barbados-2022/images/FNFMask2000_2020`

## 3. Run `4_AssembleMap`

Open the script, click **Run**.

- Post-processed loss asset path: from step 2
- Post-processed gain asset path: from step 2
- AOI: your Barbados AOI from step 1 (replaces the default Kailali area)
- Click **Run**, then export the result (Asset export is required; Drive optional)

Output is a single categorical raster with classes like deforestation, degradation, reforestation, stable forest, stable non-forest.

## 4. Challenge tasks

From the challenge page:
1. Re-run `2_LT-Data-Visualization` focused on the **Greatest Loss** output (steps 1-8 above).
2. Re-run `3_LTMakeLossGainPostprocessed` using only the Loss panel.
3. Explore `4_AssembleMap` to understand how it combines loss + gain + forest mask into Forest Degradation / Deforestation / Reforestation classes — useful for the follow-on time-series module.

## Why two parallel workflows?

The land-cover-mapping module (scripts `01`–`04`) classifies each year independently and differences the maps. The LandTrendr module fits a piecewise-linear model to the NBR (or NDVI) time series at every pixel and reports the year and magnitude of breakpoints. They answer different questions:

| Workflow | Best answers |
|---|---|
| Land-cover classification + difference | "What classes were present in year X vs year Y, and where did classes change?" |
| LandTrendr | "When did each pixel change, and how big was the change?" |

For a Barbados 1984→2020 study, the most defensible deliverable combines both: classification for the categorical change matrix, LandTrendr for dating and quantifying the change events.
