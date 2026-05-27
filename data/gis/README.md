# GIS layers

Drop your vector layers here as **GeoJSON (WGS84 / EPSG:4326)** so the map can read them
without a build step. The site already loads:

- `barbados_parishes.geojson` — 11 parish polygons (geoBoundaries gbOpen ADM1, public open data).
  Each feature has `properties.shapeName` (e.g. `"Saint James"`), which the map keys on.

## Layers the story is wired to accept

| File (suggested) | Geometry | Key properties the code expects | Used by view |
|---|---|---|---|
| `barbados_parishes.geojson` | Polygon | `shapeName` | `overview`, `westcoast`, `edjoin` |
| `enumeration_districts.geojson` | Polygon | `ED_ID`, joined disease + dwelling columns | (future) finer `edjoin` |
| `public_spaces.geojson` | Polygon/Point | `name`, `type` | extend `publicspace` |
| `parcels.geojson` / `listings.geojson` | Point | `price_usd`, `gated`, `type`, `parish` | extend `regression`/map |

## Enumeration districts (highest-value add)

The 2010 census disease data are at ED resolution (~600 districts). To map them you need the
matching ED shapefile from the **Barbados Statistical Service** (`stats.gov.bb`) or **Lands &
Surveys Department**. Once obtained:

1. Reproject to EPSG:4326 and export to `enumeration_districts.geojson`.
2. Join the census CSV on the `ID` column (see `../health/census2010_ED_health_columns_guide.md`).
3. In `js/main.js`, replace the illustrative `TOURISM_PRESSURE` choropleth in the `edjoin` view
   with a real per-ED value (e.g. `heart_disease_per1000` or the tourism-pressure composite).

## Converting other formats

```bash
# Shapefile / GeoPackage / File-GDB -> GeoJSON in WGS84
ogr2ogr -f GeoJSON -t_srs EPSG:4326 enumeration_districts.geojson source.shp
```

Keep files reasonably small for the browser (simplify geometry; aim for < a few MB each).
