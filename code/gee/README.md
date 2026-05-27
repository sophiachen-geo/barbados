# Barbados Land Cover — GEE Step-Through Part 1

Two scripts that build Landsat median composites for change analysis, following the SERVIR-Amazonia tutorial:
https://servir-amazonia.github.io/barbados-training/landcover-mapping-gee/step-through-1.html

| File | Purpose | Tutorial source |
|---|---|---|
| `01_composite_1984_1986.js` | Baseline composite, 1984-86 (Landsat 5) | step-through-1 |
| `02_composite_2020.js`      | Current composite, 2020 (Landsat 7 + 8)  | step-through-1 |
| `03_classify_and_change.js` | Both composites + RF classify + change map | step-through-1, step-through-2 |
| `04_classify_with_challenge_improvements.js` | Same workflow with 500 trees and 300 samples/class | challenge.html |
| `LandTrendr_Walkthrough.md` | GUI walkthrough — open shared `kwoodward` scripts and run LandTrendr on Barbados | time-series-change1 module |

Both scripts merge all four mission collections (L5, L7, L8, L9) before filtering by date, exactly as written in the tutorial — only the date filter decides which mission's imagery ends up in the composite.

## How to run

1. Open https://code.earthengine.google.com/ (signed in with a registered Earth Engine account).
2. Click **New > File** in the left Scripts panel; paste the contents of `01_composite_1984_1986.js`.
3. Click **Run**. The Map panel will show the AOI, the Copernicus 8-class reference layer, and the median composite. The Console will print the filtered ImageCollection and the final band names.
4. Open the **Tasks** tab and click **Run** next to `ToDrive_LandsatComposite_1984_1986` to export the GeoTIFF to your Google Drive (~30 m, clipped to Barbados).
5. Repeat steps 2-4 with `02_composite_2020.js`.

## What you'll have when both finish

- `LandsatComposite_1984_1986.tif` and `LandsatComposite_2020.tif` in your Google Drive.
- Each composite has bands: `blue, green, red, nir, swir1, temp, swir2, ndvi, lswi, ndmi, mndwi` — the exact feature set the tutorial passes to the Random Forest classifier in Part 2.

## Part 2 + change analysis (`03_classify_and_change.js`)

This is the script that actually produces the change map. It is self-contained — paste the whole file into a new GEE script and Run.

What it does:
1. Builds the 2020 composite and the 1984-86 composite (Part 1).
2. Generates 100 stratified samples per Copernicus class from the 2020 composite (Part 2).
3. Splits 80/20 train/test, trains a 100-tree Random Forest, prints training + testing confusion matrices and overall/producer/user accuracies (Part 2).
4. Applies the **same** trained classifier to both composites.
5. Computes two change products and queues four Drive exports:
   - `Classified_2020.tif` — 8-class map for 2020
   - `Classified_1984_1986.tif` — 8-class map for 1984-86
   - `Change_1984_to_2020.tif` — binary (1 = changed, 0 = stable)
   - `FromTo_1984_to_2020.tif` — `early_class * 10 + recent_class`, so e.g. code 46 means forest → urban

Why train only on 2020: the Copernicus 8-class reference layer is dated ~2019. Using it to label 1984-86 spectra would force the model to learn "what was here in 2019" from 1984 pixels — exactly the opposite of what change detection needs. Training once on the era the labels correspond to, then applying the same classifier to the historical composite, is the standard workaround when no historical ground-truth exists.

Caveat: Landsat 5 TM and Landsat 8 OLI have different spectral response functions, so the 1984-86 map will be noisier than the 2020 map even after band-name harmonization. Treat the historical map and the change product as indicative, not authoritative.

## Notes specific to the 1984-86 baseline

- Landsat 5 launched March 1984, so January-February 1984 will have no imagery. This is expected.
- Barbados is small (~430 km²) and falls inside a single Landsat path/row (path 1, row 50). With a 25% cloud-cover threshold, a 3-year window typically yields 8-15 usable scenes — enough for a stable median composite.
- The Copernicus 8-class reference layer is from ~2019, so it's only a legitimate training source for the 2020 composite. For the 1984-86 period you'll need a different label source in Part 2 (or you can train on 2020 and apply the same classifier to the 1984-86 composite, accepting the spectral-drift caveat).
