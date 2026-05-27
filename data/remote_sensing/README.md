# Remote-sensing layers

The map already offers an **Esri World Imagery** satellite basemap (used by the *land-use* view).
This folder is where your processed remote-sensing products go.

## What the story is set up to show

The narrative describes a **1984 → 2020 urban-expansion** analysis (Landsat) plus a recent
**2017 → 2024** change layer (Sentinel-2 / Esri Land Cover). To put real pixels on the map, add
one of these:

### Option A — classified change as GeoJSON (simplest)
Vectorise your change raster (e.g. "new built-up 1984→2020") to polygons and export
`urban_expansion_1984_2020.geojson` (EPSG:4326). Then in `js/main.js` swap the illustrative
`CORRIDOR` polygon in the `landuse` view for `L.geoJSON(thatFile, …)`.

### Option B — raster tiles (best fidelity)
Tile a GeoTIFF (NDVI, land-surface temperature, or a classification) into XYZ/`{z}/{x}/{y}.png`:

```bash
gdal2tiles.py -z 9-15 -w none classified_2020.tif tiles_2020/
```

Put the output under `data/remote_sensing/tiles_2020/` and add an
`L.tileLayer("data/remote_sensing/tiles_2020/{z}/{x}/{y}.png", …)` toggle in `main.js`.

### Option C — Google Earth Engine tile URL
If you process in GEE, export the `Map.getMapId` XYZ template and load it as a normal
`L.tileLayer(...)`. (Tokens expire, so prefer A or B for a permanent published site.)

## Suggested products (from the health-data synthesis)

| Product | Why | Source |
|---|---|---|
| Built-up extent 1984 / 2000 / 2020 | Core "leisuring of land" evidence | Landsat 5/8 via GEE |
| Recent change 2017→2024 | Overlaps the rising-AMI window | Esri/IO 10 m Land Cover or Sentinel-2 |
| NDVI loss | Green-space decline near the coast | Landsat/Sentinel-2 |
| Land-surface temperature (LST) | Heat exposure pathway to CVD | Landsat band 6 (already in `Derivatives/TEMP_2020.tif`) |

Keep tiled output and large GeoTIFFs out of git history if they get big — consider Git LFS or a
release asset, and reference them by URL.
