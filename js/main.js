/* Map + scrollytelling orchestration for the Barbados site. */
(function () {
  "use strict";

  // ---------- Constants ----------
  var ISLAND_BOUNDS = L.latLngBounds([12.99, -59.69], [13.345, -59.41]);
  var WESTCOAST_BOUNDS = L.latLngBounds([13.07, -59.66], [13.28, -59.59]);
  var WEST_PARISHES = ["Saint James", "Saint Peter"];

  // Illustrative tourism-pressure index per parish (0–1), derived from the paper's
  // narrative until the 2010 census ED layer is joined. Clearly a placeholder.
  var TOURISM_PRESSURE = {
    "Saint James": 0.95, "Saint Peter": 0.72, "Christ Church": 0.66,
    "Saint Michael": 0.58, "Saint Philip": 0.40, "Saint Lucy": 0.33,
    "Saint Joseph": 0.26, "Saint Thomas": 0.24, "Saint George": 0.20,
    "Saint John": 0.20, "Saint Andrew": 0.18
  };

  // Rough West-Coast tourism-development corridor (illustrative until the
  // classified Landsat/Sentinel-2 change layer is added).
  var CORRIDOR = {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [[
        [-59.654, 13.255], [-59.628, 13.255], [-59.610, 13.205],
        [-59.625, 13.150], [-59.640, 13.100], [-59.648, 13.075],
        [-59.660, 13.085], [-59.652, 13.150], [-59.648, 13.205],
        [-59.654, 13.255]
      ]]
    }
  };

  var CATEGORY_COLORS = {
    "public space / community": "#0e7c86",
    "water / sewage inequity": "#1f6f8b",
    "agriculture vs tourism land": "#6b8e23",
    "real estate market": "#d2603a",
    "public space / access": "#b8492a",
    "gated community": "#7a3b8f",
    "vacancy / speculation": "#c08a2a",
    "heritage / public space": "#0e7c86",
    "land use change / 'green' branding": "#6b8e23",
    "remote-sensing / coastal change": "#1f6f8b",
    "public space / mobility": "#0e7c86"
  };

  // ---------- Map setup ----------
  var map = L.map("map", { zoomControl: true, scrollWheelZoom: true, attributionControl: true })
    .fitBounds(ISLAND_BOUNDS);

  var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  var imagery = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics" }
  );

  var corridorLayer = L.geoJSON(CORRIDOR, {
    style: { color: "#ffd166", weight: 2, fillColor: "#ffd166", fillOpacity: 0.18, dashArray: "6 5" }
  });

  var parishLayer = null;
  var obsLayer = null;
  var legend = null;
  var obsData = null;

  // ---------- Raster overlay manager (v8 GEE PNGs) ----------
  var rasterManager = {
    manifest: [],
    layers: {},        // id -> L.imageOverlay
    activeId: null,

    load: function () {
      return fetch("data/remote_sensing/layers.json").then(function (r) {
        if (!r.ok) throw new Error("Could not load layers.json (" + r.status + ")");
        return r.json();
      }).then(function (m) {
        rasterManager.manifest = m;
        return m;
      });
    },
    entry: function (id) {
      for (var i = 0; i < this.manifest.length; i++) {
        if (this.manifest[i].id === id) return this.manifest[i];
      }
      return null;
    },
    _ensure: function (id) {
      if (this.layers[id]) return this.layers[id];
      var e = this.entry(id);
      if (!e) return null;
      this.layers[id] = L.imageOverlay(e.png, e.bounds, {
        opacity: 0.85, interactive: false, className: "v8-raster"
      });
      return this.layers[id];
    },
    show: function (id) {
      var lyr = this._ensure(id);
      if (!lyr) return;
      if (!map.hasLayer(lyr)) lyr.addTo(map);
      // Keep parishes / corridor on top
      if (parishLayer && map.hasLayer(parishLayer)) parishLayer.bringToFront();
      if (corridorLayer && map.hasLayer(corridorLayer)) corridorLayer.bringToFront();
      this.activeId = id;
    },
    hide: function (id) {
      var lyr = this.layers[id];
      if (lyr && map.hasLayer(lyr)) map.removeLayer(lyr);
      if (this.activeId === id) this.activeId = null;
    },
    solo: function (id) {
      var self = this;
      Object.keys(this.layers).forEach(function (other) {
        if (other !== id) self.hide(other);
      });
      this.show(id);
    },
    hideAll: function () {
      var self = this;
      Object.keys(this.layers).forEach(function (id) { self.hide(id); });
    }
  };

  function rasterLegendHTML(entry) {
    if (!entry) return null;
    var rows = (entry.legend || []).map(function (L) {
      return '<i style="background:' + L.hex + '"></i>' + L.label;
    }).join("<br>");
    return '<h4>' + entry.title + '</h4>' +
      '<p style="margin:0 0 .35rem;font-size:.75rem;opacity:.8">' + entry.desc + '</p>' +
      rows;
  }

  function showRasterView(id) {
    var entry = rasterManager.entry(id);
    if (!entry) return;
    // Use satellite imagery as base so the raster's classes overlay terrain context
    ensureBase(imagery);
    removeIf(corridorLayer);
    removeIf(obsLayer);
    resetParishStyle();
    addIf(parishLayer);
    rasterManager.solo(id);
    setLegend(rasterLegendHTML(entry));
    // Fit to whatever extent: if WestCoast layer (NDVI 10m / manicuring) tight in, else island
    var bounds = L.latLngBounds(entry.bounds);
    map.flyToBounds(bounds, { duration: 1.0, padding: [10, 10] });
  }

  // ---------- Raster picker control (always-visible dropdown) ----------
  function buildRasterPicker() {
    var ctrl = L.control({ position: "topright" });
    ctrl.onAdd = function () {
      var div = L.DomUtil.create("div", "raster-picker");
      var options = '<option value="">Pick a Raster Dataset</option>';
      rasterManager.manifest.forEach(function (e) {
        options += '<option value="' + e.id + '">' + e.title + '</option>';
      });
      div.innerHTML =
        '<button class="raster-picker__clear" type="button" title="Hide overlay" aria-label="Clear overlay">&times;</button>' +
        '<label class="raster-picker__label">Raster Overlay</label>' +
        '<select class="raster-picker__select">' + options + '</select>';
      var sel = div.querySelector(".raster-picker__select");
      var clr = div.querySelector(".raster-picker__clear");
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.on(sel, "change", function () {
        if (sel.value) showRasterView(sel.value);
      });
      L.DomEvent.on(clr, "click", function () {
        sel.value = "";
        rasterManager.hideAll();
        setLegend(null);
      });
      return div;
    };
    ctrl.addTo(map);
  }

  // ---------- Styling helpers ----------
  function parishStyleBase(feature) {
    var west = WEST_PARISHES.indexOf(feature.properties.shapeName) !== -1;
    return {
      color: "#095159",
      weight: 1,
      fillColor: west ? "#0e7c86" : "#9bc4c2",
      fillOpacity: 0.18
    };
  }

  function pressureColor(v) {
    return v > 0.8 ? "#7f0000" :
           v > 0.6 ? "#b30000" :
           v > 0.45 ? "#d7301f" :
           v > 0.3 ? "#ef6548" :
           v > 0.22 ? "#fc8d59" :
                      "#fdbb84";
  }

  function setLegend(html) {
    if (legend) { map.removeControl(legend); legend = null; }
    if (!html) return;
    legend = L.control({ position: "bottomright" });
    legend.onAdd = function () {
      var div = L.DomUtil.create("div", "legend");
      div.innerHTML = html;
      return div;
    };
    legend.addTo(map);
  }

  // ---------- Layer factories ----------
  function buildParishLayer(geojson) {
    parishLayer = L.geoJSON(geojson, {
      style: parishStyleBase,
      onEachFeature: function (f, layer) {
        layer.bindTooltip(f.properties.shapeName, { sticky: true, direction: "top", className: "parish-tip" });
      }
    });
  }

  function obsMarker(feature, latlng) {
    var cat = feature.properties.category;
    return L.circleMarker(latlng, {
      radius: 8,
      color: "#fff",
      weight: 2,
      fillColor: CATEGORY_COLORS[cat] || "#d2603a",
      fillOpacity: 0.95
    });
  }

  function obsPopup(f) {
    var p = f.properties;
    var chips = (p.issues || []).map(function (i) { return '<span class="chip">Issue ' + i + "</span>"; }).join("");
    return '<div class="obs-popup">' +
      '<div class="date">' + p.date + " &middot; " + (p.parish || "") + "</div>" +
      "<h4>" + p.place + "</h4>" +
      "<p>" + p.note + "</p>" +
      '<div class="chips">' + chips + "</div></div>";
  }

  function buildObsLayer(geojson) {
    obsLayer = L.geoJSON(geojson, {
      pointToLayer: obsMarker,
      onEachFeature: function (f, layer) {
        layer.bindPopup(obsPopup(f), { maxWidth: 300 });
        layer.bindTooltip(f.properties.place, { direction: "top" });
      }
    });
  }

  // ---------- View handlers ----------
  function ensureBase(layer) {
    [osm, imagery].forEach(function (l) { if (l !== layer && map.hasLayer(l)) map.removeLayer(l); });
    if (!map.hasLayer(layer)) layer.addTo(map);
  }
  function removeIf(layer) { if (layer && map.hasLayer(layer)) map.removeLayer(layer); }
  function addIf(layer) { if (layer && !map.hasLayer(layer)) layer.addTo(map); }

  function resetParishStyle() {
    if (parishLayer) parishLayer.setStyle(parishStyleBase);
  }

  var views = {
    overview: function () {
      ensureBase(osm); removeIf(corridorLayer); removeIf(obsLayer);
      resetParishStyle(); addIf(parishLayer); setLegend(null);
      map.flyToBounds(ISLAND_BOUNDS, { duration: 1.1 });
    },
    westcoast: function () {
      ensureBase(osm); removeIf(corridorLayer); removeIf(obsLayer);
      resetParishStyle(); addIf(parishLayer); setLegend(
        '<h4>Platinum Coast</h4><i style="background:#0e7c86"></i>West parishes (St James, St Peter)' +
        '<br><i style="background:#9bc4c2"></i>Other parishes'
      );
      map.flyToBounds(WESTCOAST_BOUNDS, { duration: 1.1 });
    },
    landuse: function () {
      ensureBase(imagery); resetParishStyle(); removeIf(parishLayer); removeIf(obsLayer);
      addIf(corridorLayer); setLegend('<h4>Development corridor</h4><i style="background:#ffd166"></i>Illustrative West-Coast<br>expansion zone (placeholder)');
      map.flyToBounds(WESTCOAST_BOUNDS, { duration: 1.1 });
    },
    publicspace: function () {
      ensureBase(osm); removeIf(corridorLayer); resetParishStyle(); removeIf(parishLayer);
      addIf(obsLayer); setLegend('<h4>Field encounters</h4>Tap a marker for the full note.<br>Colour = theme of the observation.');
      map.flyToBounds(WESTCOAST_BOUNDS, { duration: 1.1 });
    },
    edjoin: function () {
      ensureBase(osm); removeIf(corridorLayer); removeIf(obsLayer);
      addIf(parishLayer);
      if (parishLayer) {
        parishLayer.setStyle(function (f) {
          var v = TOURISM_PRESSURE[f.properties.shapeName] || 0.2;
          return { color: "#7a2f1e", weight: 1, fillColor: pressureColor(v), fillOpacity: 0.78 };
        });
      }
      setLegend(
        '<h4>Tourism-pressure index<br><span style="font-weight:400">(illustrative placeholder)</span></h4>' +
        '<i style="background:#7f0000"></i>High &nbsp;<i style="background:#fc8d59"></i>Mid &nbsp;<i style="background:#fdbb84"></i>Low' +
        '<br><span style="font-size:0.7rem;color:#8a8170">Replace with 2010 census ED join.</span>'
      );
      map.flyToBounds(ISLAND_BOUNDS, { duration: 1.1 });
    },
    fieldtimeline: function () {
      ensureBase(osm); removeIf(corridorLayer); resetParishStyle(); removeIf(parishLayer);
      addIf(obsLayer); setLegend('<h4>March 1–7 field log</h4>13 geocoded observations across the West Coast.');
      if (obsLayer) map.flyToBounds(obsLayer.getBounds().pad(0.15), { duration: 1.1 });
    }
  };

  // ---------- Graphic / panel switching ----------
  var chartPanel = document.getElementById("chart-panel");
  var badge = document.getElementById("graphic-badge");
  var titleEl = document.getElementById("chart-title");
  var subEl = document.getElementById("chart-sub");
  var srcEl = document.getElementById("chart-source");

  var BADGES = {
    overview: "Map · Barbados", westcoast: "Map · West Coast", landuse: "Satellite · West Coast",
    publicspace: "Map · Field encounters", edjoin: "Map · Parish choropleth", fieldtimeline: "Map · Field log",
    regression: "Chart · Real estate", cvd: "Chart · Health", riskfactors: "Chart · Health", activity: "Chart · Health"
  };

  function showChart(view) {
    chartPanel.classList.add("is-visible");
    badge.textContent = BADGES[view] || "Chart";
    window.requestAnimationFrame(function () {
      window.BarbadosCharts.render(view).then(function (meta) {
        titleEl.textContent = meta.title;
        subEl.textContent = meta.sub;
        srcEl.textContent = meta.source;
      }).catch(function (e) {
        titleEl.textContent = "Data unavailable";
        subEl.textContent = e.message;
        srcEl.textContent = "";
      });
    });
  }

  function showMap(view) {
    chartPanel.classList.remove("is-visible");
    badge.textContent = BADGES[view] || "Map";
    // Any non-raster view should hide the overlays
    if (!(view && view.indexOf("raster_") === 0)) {
      rasterManager.hideAll();
    }
    if (views[view]) views[view]();
    // Leaflet needs a nudge after the sticky container settles.
    window.setTimeout(function () { map.invalidateSize(); }, 200);
  }

  var lastView = null;
  function activate(stepEl) {
    var graphic = stepEl.getAttribute("data-graphic");
    var view = stepEl.getAttribute("data-view");
    if (view === lastView) return;
    lastView = view;
    if (graphic === "chart") showChart(view);
    else showMap(view);
  }

  // ---------- Scroll stepper (IntersectionObserver) ----------
  function initScroller() {
    var steps = Array.prototype.slice.call(document.querySelectorAll(".step"));
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          steps.forEach(function (s) { s.classList.remove("is-active"); });
          entry.target.classList.add("is-active");
          activate(entry.target);
        }
      });
    }, { root: null, rootMargin: "-45% 0px -45% 0px", threshold: 0 });
    steps.forEach(function (s) { observer.observe(s); });
  }

  // ---------- Boot ----------
  Promise.all([
    fetch("data/gis/barbados_parishes.geojson").then(function (r) { return r.json(); }),
    fetch("data/field/field_observations.geojson").then(function (r) { return r.json(); }),
    rasterManager.load().catch(function (e) {
      console.warn("Raster manifest unavailable:", e.message);
      return [];
    })
  ]).then(function (res) {
    buildParishLayer(res[0]);
    obsData = res[1];
    buildObsLayer(res[1]);

    // Register a raster view per manifest entry so steps can declare
    // data-view="raster_<id>" and the existing scroller picks them up.
    rasterManager.manifest.forEach(function (e) {
      views["raster_" + e.id] = function () { showRasterView(e.id); };
      BADGES["raster_" + e.id] = "Raster · " + e.title;
    });

    if (rasterManager.manifest.length) buildRasterPicker();

    views.overview();
    initScroller();
    window.setTimeout(function () { map.invalidateSize(); }, 300);
  }).catch(function (e) {
    console.error(e);
    document.getElementById("map").innerHTML =
      '<div style="padding:2rem;font-family:sans-serif;color:#095159">Could not load map data: ' + e.message + "</div>";
  });

  // Keep the map sized correctly on resize.
  window.addEventListener("resize", function () { map.invalidateSize(); });
})();
