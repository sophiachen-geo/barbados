# Selling Paradise, Spending Health

**Real estate tourism, land-use change, loss of public space, and health outcomes on the West Coast of Barbados.**

An interactive, map-driven scrollytelling publication by **Sophia Chen** and **Anastasia Ejov**.
It integrates four data streams to trace one thread — *how the supply side of real estate tourism
reaches from a property listing into public space and public health.*

- **Field observation** — a March 1–7 field log and stakeholder interviews, geocoded to the map.
- **Real-estate listings** — 135 listings scraped from 7thHeaven, analysed with multiple regression.
- **Health outcomes** — Barbados National Registry CVD time series (2013–2022), NCD risk-factor
  prevalence, and the 2010 census enumeration-district disease columns.
- **GIS + remote sensing** — open parish boundaries and Esri satellite imagery now; your parcels,
  enumeration districts, and classified land-cover-change layers slot in via `data/`.

## View it

It's a static site — no build step. View locally with any static server:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

## Publish on GitHub Pages

Two supported paths:

1. **GitHub Actions (included).** `.github/workflows/pages.yml` deploys on every push to `main`
   or `claude/happy-brown-XkrIs`. In the repo: **Settings → Pages → Build and deployment →
   Source: GitHub Actions**.
2. **Deploy from a branch.** **Settings → Pages → Source: Deploy from a branch**, choose the
   branch and `/ (root)`. The `.nojekyll` file keeps Pages from reprocessing the static assets.

## Structure

```
index.html              # the whole narrative + scrollytelling layout
css/style.css           # styles
js/main.js              # Leaflet map + scroll-step orchestration
js/charts.js            # Chart.js charts built from the health CSVs + regression JSON
data/
  field/                # geocoded field observations (GeoJSON) + regression findings (JSON)
  health/               # CVD time series, NCD risk factors, 2010 census ED guide + synthesis
  gis/                  # parish boundaries (live) — drop your vector layers here
  remote_sensing/       # add classified land-cover-change layers / tiles here
```

Each data folder has a `README.md` describing the expected schema and how to swap real layers in
without touching the code.

## Adding your own data

- **GIS / enumeration districts** — see [`data/gis/README.md`](data/gis/README.md).
- **Remote sensing / land-cover change** — see [`data/remote_sensing/README.md`](data/remote_sensing/README.md).
- **Health (parish/ED CVD)** — request sub-national incidence from the Barbados National Registry
  (UWI Cave Hill); see [`data/health/HEALTH_DATA_SYNTHESIS.md`](data/health/HEALTH_DATA_SYNTHESIS.md).

## A note on causation

The site presents an **association and a plausible mechanism**, not a proven cause. National CVD
trends are temporal, the census disease data are a 2010 cross-section, and parish/ED-level incidence
still has to be obtained. The analysis is deliberately structured to accept those data when they
arrive — see the *Data & methods* section in the site.

## Credits & licensing

- Boundaries: [geoBoundaries](https://www.geoboundaries.org/) (gbOpen, ADM1, Barbados).
- Basemaps: © OpenStreetMap contributors; Imagery © Esri, Maxar, Earthstar Geographics.
- Health data: Barbados National Registry for Chronic NCDs; Ministry of Health & Wellness NCD
  Strategic Plan 2020–2025; Barbados Statistical Service 2010 Census; HoTNS / GSHS / GYTS / WHO.
- Libraries: [Leaflet](https://leafletjs.com/), [Chart.js](https://www.chartjs.org/).
