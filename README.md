# Barbados Dual Map Viewer (embed branch)

This branch carries only what's needed to ship the dual side-by-side map comparator as an embeddable widget. The full project lives on the `main` branch.

## What's here

```
index.html      # the standalone embed (was embed.html on main)
data/           # raster overlays, planning maps, legend strips, manifests
```

Nothing else. No scrollytelling, no charts, no narrative text.

## Three ways to use it

### 1. Iframe the hosted version (easiest)

The same file is also available on the main branch at `embed.html`, served from GitHub Pages:

```html
<iframe
  src="https://sophiachen-geo.github.io/barbados/embed.html"
  width="100%"
  height="800"
  style="border: 0; border-radius: 12px;"
  loading="lazy"
  title="Barbados dual map viewer">
</iframe>
```

### 2. Copy `index.html` into your own site

Drop `index.html` anywhere on your server. It loads Leaflet from a CDN and pulls its raster manifests + image overlays from `https://sophiachen-geo.github.io/barbados/` by default. No build step required.

To point at a different data host, set a global before the inline script runs. Easiest is to add it as the first line of the inline `<script>` block:

```javascript
window.BARBADOS_DATA_BASE = "https://your-cdn.example.com/barbados/";
```

The fetch URLs become `{BASE}data/remote_sensing/layers.json`, `{BASE}data/planning_maps.json`, and each image overlay path resolves under that base.

### 3. Clone this branch

```bash
git clone --branch dual-maps-only --single-branch https://github.com/sophiachen-geo/barbados.git barbados-embed
```

You get `index.html` plus the `data/` directory, ready to deploy as a static site.

## What's inside the viewer

- **Left map**: Satellite Analysis basemap (Esri World Imagery)
  - Top-right dropdown picks one of the 16 GEE-derived raster overlays
  - Bottom-left scrubber walks five Landsat epochs from 1984 through 2025, with a play button to cycle through automatically
- **Right map**: Government Planning Maps basemap (Carto Voyager)
  - Top-left multi-select panel toggles any of the 17 Barbados Physical Development Plan maps, each with its own opacity slider and inline legend
- **Linked View**: panning or zooming either map drives the other in lockstep
- **Lightbox**: clicking "View at Full Size" or "view" on any planning map opens the source page in a fullscreen modal

## Dependencies

| What | Where from |
|---|---|
| Leaflet 1.9.4 | jsDelivr CDN |
| Raster manifests + images | GitHub Pages (or your configured `BARBADOS_DATA_BASE`) |
| Basemap tiles | Esri World Imagery and Carto Voyager |

No build step, no bundler, no framework. Single HTML file with inline CSS and JavaScript.
