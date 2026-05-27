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

  // ---------- Map setup (two viewers, linked pan/zoom) ----------
  var map = L.map("map", { zoomControl: true, scrollWheelZoom: true, attributionControl: true })
    .fitBounds(ISLAND_BOUNDS);
  var mapPlan = L.map("map-plan", { zoomControl: true, scrollWheelZoom: true, attributionControl: true })
    .fitBounds(ISLAND_BOUNDS);

  // Left-side basemaps
  var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);
  var imagery = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics" }
  );

  // Right-side basemap (light grey, so planning maps read clearly above it)
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png",
    { maxZoom: 19, attribution: "&copy; OpenStreetMap, &copy; CARTO" }
  ).addTo(mapPlan);

  // Sync pan and zoom between the two maps so panning one moves the other
  var syncing = false;
  function bindSync(a, b) {
    a.on("move zoomanim", function () {
      if (syncing) return;
      syncing = true;
      b.setView(a.getCenter(), a.getZoom(), { animate: false });
      syncing = false;
    });
  }
  bindSync(map, mapPlan);
  bindSync(mapPlan, map);

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
      // Load both the GEE-derived raster manifest and the planning-maps manifest,
      // tag each entry with its category, and merge into a single list.
      var loadGee = fetch("data/remote_sensing/layers.json").then(function (r) {
        if (!r.ok) throw new Error("Could not load layers.json (" + r.status + ")");
        return r.json();
      }).then(function (m) {
        m.forEach(function (e) { e.category = "Satellite Analysis Layers"; });
        return m;
      }).catch(function (e) { console.warn("GEE manifest unavailable:", e.message); return []; });

      var loadPlan = fetch("data/planning_maps.json").then(function (r) {
        if (!r.ok) throw new Error("Could not load planning_maps.json (" + r.status + ")");
        return r.json();
      }).then(function (m) {
        m.forEach(function (e) { e.category = "Government Planning Maps"; });
        return m;
      }).catch(function (e) { console.warn("Planning maps unavailable:", e.message); return []; });

      return Promise.all([loadGee, loadPlan]).then(function (parts) {
        rasterManager.manifest = parts[0].concat(parts[1]);
        return rasterManager.manifest;
      });
    },
    entry: function (id) {
      for (var i = 0; i < this.manifest.length; i++) {
        if (this.manifest[i].id === id) return this.manifest[i];
      }
      return null;
    },
    _targetMapFor: function (entry) {
      // Planning maps go on the dedicated right map. Everything else stays
      // on the main scrollytelling map on the left.
      return entry.category === "Government Planning Maps" ? mapPlan : map;
    },
    _ensure: function (id) {
      if (this.layers[id]) return this.layers[id];
      var e = this.entry(id);
      if (!e) return null;
      var isPlan = e.category === "Government Planning Maps";
      this.layers[id] = L.imageOverlay(e.png, e.bounds, {
        opacity: isPlan ? 0.92 : 0.88,
        interactive: false,
        className: isPlan ? "plan-map-overlay" : "v8-raster"
      });
      return this.layers[id];
    },
    show: function (id) {
      var lyr = this._ensure(id);
      if (!lyr) return;
      var e = this.entry(id);
      var tgt = this._targetMapFor(e);
      if (!tgt.hasLayer(lyr)) lyr.addTo(tgt);
      if (parishLayer && map.hasLayer(parishLayer)) parishLayer.bringToFront();
      if (corridorLayer && map.hasLayer(corridorLayer)) corridorLayer.bringToFront();
      this.activeId = id;
    },
    hide: function (id) {
      var lyr = this.layers[id];
      if (!lyr) return;
      if (map.hasLayer(lyr)) map.removeLayer(lyr);
      if (mapPlan.hasLayer(lyr)) mapPlan.removeLayer(lyr);
      if (this.activeId === id) this.activeId = null;
    },
    solo: function (id) {
      // Solo only inside the same category so that picking a satellite layer
      // does not hide the planning maps the user has checked on the other map.
      var self = this;
      var e = self.entry(id);
      var cat = e ? e.category : null;
      Object.keys(this.layers).forEach(function (other) {
        if (other === id) return;
        var oe = self.entry(other);
        if (oe && oe.category === cat) self.hide(other);
      });
      this.show(id);
    },
    hideAll: function () {
      var self = this;
      Object.keys(this.layers).forEach(function (id) { self.hide(id); });
    },
    hideCategory: function (category) {
      var self = this;
      Object.keys(this.layers).forEach(function (id) {
        var e = self.entry(id);
        if (e && e.category === category) self.hide(id);
      });
    },
    setOpacity: function (id, value) {
      var lyr = this.layers[id];
      if (lyr && lyr.setOpacity) lyr.setOpacity(value);
    },
    isActive: function (id) {
      var lyr = this.layers[id];
      if (!lyr) return false;
      return map.hasLayer(lyr) || mapPlan.hasLayer(lyr);
    }
  };

  function rasterLegendHTML(entry) {
    if (!entry) return null;
    var rows = (entry.legend || []).map(function (L) {
      return '<i style="background:' + L.hex + '"></i>' + L.label;
    }).join("<br>");
    var viewLink = "";
    if (entry.category === "Government Planning Maps") {
      // Planning maps carry their own internal legend, so we link the user
      // to the full size version in the gallery lightbox.
      viewLink = '<p style="margin-top:.45rem;font-size:.78rem;">' +
        '<a href="#" data-lightbox="' + entry.id + '" class="legend-lightbox-link">View at Full Size &rarr;</a></p>';
    }
    return '<h4>' + entry.title + '</h4>' +
      '<p style="margin:0 0 .35rem;font-size:.75rem;opacity:.8">' + entry.desc + '</p>' +
      rows + viewLink;
  }

  // ---------- Lightbox for full size planning maps ----------
  function openLightbox(id) {
    var entry = rasterManager.entry(id);
    if (!entry) return;
    var box = document.getElementById("lightbox");
    if (!box) {
      box = document.createElement("div");
      box.id = "lightbox";
      box.className = "lightbox";
      box.innerHTML =
        '<button class="lightbox__close" type="button" aria-label="Close">&times;</button>' +
        '<figure class="lightbox__figure">' +
          '<img class="lightbox__img" alt="" />' +
          '<figcaption class="lightbox__cap"></figcaption>' +
        '</figure>';
      document.body.appendChild(box);
      box.addEventListener("click", function (e) {
        if (e.target === box || e.target.classList.contains("lightbox__close")) {
          box.classList.remove("is-open");
        }
      });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") box.classList.remove("is-open");
      });
    }
    box.querySelector(".lightbox__img").src = entry.png;
    box.querySelector(".lightbox__img").alt = entry.title;
    box.querySelector(".lightbox__cap").textContent = entry.title + ". " + entry.desc;
    box.classList.add("is-open");
  }

  // Delegate clicks from legend links + the gallery thumbnails
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (t && t.dataset && t.dataset.lightbox) {
      e.preventDefault();
      openLightbox(t.dataset.lightbox);
    }
  });

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

  // ---------- Satellite raster picker (top-right): single select, GEE only ----------
  function buildSatellitePicker() {
    var ctrl = L.control({ position: "topright" });
    ctrl.onAdd = function () {
      var div = L.DomUtil.create("div", "raster-picker");
      var entries = rasterManager.manifest.filter(function (e) {
        return e.category === "Satellite Analysis Layers";
      });
      var options = '<option value="">Pick a Raster Dataset</option>';
      entries.forEach(function (e) {
        options += '<option value="' + e.id + '">' + e.title + '</option>';
      });
      div.innerHTML =
        '<button class="raster-picker__clear" type="button" title="Clear overlay" aria-label="Clear">&times;</button>' +
        '<label class="raster-picker__label">Satellite Analysis Layers</label>' +
        '<select class="raster-picker__select">' + options + '</select>';
      var sel = div.querySelector(".raster-picker__select");
      var clr = div.querySelector(".raster-picker__clear");
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);
      L.DomEvent.on(sel, "change", function () {
        if (sel.value) showRasterView(sel.value);
      });
      L.DomEvent.on(clr, "click", function () {
        sel.value = "";
        rasterManager.hideCategory("Satellite Analysis Layers");
        setLegend(null);
      });
      // Expose so the time scrubber can sync the dropdown
      window.__satPicker = { select: sel };
      return div;
    };
    ctrl.addTo(map);
  }

  // ---------- Planning maps panel (top-left): multi-select + opacity sliders ----------
  function buildPlanningPanel() {
    var ctrl = L.control({ position: "topleft" });
    var planEntries = rasterManager.manifest.filter(function (e) {
      return e.category === "Government Planning Maps";
    });
    if (!planEntries.length) return;

    ctrl.onAdd = function () {
      var div = L.DomUtil.create("div", "plan-panel");
      var rows = planEntries.map(function (e) {
        return (
          '<div class="plan-panel__row" data-id="' + e.id + '">' +
            '<label class="plan-panel__check">' +
              '<input type="checkbox" data-plan-toggle="' + e.id + '" />' +
              '<span>' + e.title + '</span>' +
            '</label>' +
            '<div class="plan-panel__controls" hidden>' +
              '<input type="range" min="0" max="100" value="78" data-plan-opacity="' + e.id + '" />' +
              '<span class="plan-panel__opacity-val">78%</span>' +
              ' &middot; <a href="#" data-lightbox="' + e.id + '" class="plan-panel__view">view</a>' +
              ' &middot; <a href="#" data-plan-legend="' + e.id + '" class="plan-panel__legend-btn">legend</a>' +
            '</div>' +
            '<figure class="plan-panel__legend" hidden>' +
              '<img loading="lazy" src="' + e.legend_png + '" alt="Legend for ' + e.title + '" />' +
            '</figure>' +
          '</div>'
        );
      }).join("");
      div.innerHTML =
        '<div class="plan-panel__head">' +
          '<strong>Government Planning Maps</strong>' +
          '<button class="plan-panel__collapse" type="button" aria-label="Collapse">&minus;</button>' +
        '</div>' +
        '<p class="plan-panel__hint">Pick one or more layers to overlay. Each has its own opacity slider and legend.</p>' +
        '<div class="plan-panel__body">' + rows + '</div>';

      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);

      // Checkbox toggles overlay
      div.querySelectorAll("[data-plan-toggle]").forEach(function (cb) {
        L.DomEvent.on(cb, "change", function () {
          var id = cb.dataset.planToggle;
          var row = cb.closest(".plan-panel__row");
          var controls = row.querySelector(".plan-panel__controls");
          if (cb.checked) {
            rasterManager.show(id);
            // Set initial opacity to 0.78
            rasterManager.setOpacity(id, 0.78);
            controls.hidden = false;
          } else {
            rasterManager.hide(id);
            controls.hidden = true;
            // Also hide expanded legend if open
            var legendFig = row.querySelector(".plan-panel__legend");
            if (legendFig) legendFig.hidden = true;
          }
        });
      });

      // Opacity slider updates layer opacity in real time
      div.querySelectorAll("[data-plan-opacity]").forEach(function (slider) {
        L.DomEvent.on(slider, "input", function () {
          var id = slider.dataset.planOpacity;
          var pct = parseFloat(slider.value);
          rasterManager.setOpacity(id, pct / 100);
          var label = slider.parentNode.querySelector(".plan-panel__opacity-val");
          if (label) label.textContent = Math.round(pct) + "%";
        });
      });

      // Legend toggle
      div.querySelectorAll("[data-plan-legend]").forEach(function (a) {
        L.DomEvent.on(a, "click", function (e) {
          e.preventDefault();
          var id = a.dataset.planLegend;
          var row = div.querySelector('.plan-panel__row[data-id="' + id + '"]');
          var fig = row.querySelector(".plan-panel__legend");
          if (fig) fig.hidden = !fig.hidden;
        });
      });

      // Header collapse
      var collapseBtn = div.querySelector(".plan-panel__collapse");
      var body = div.querySelector(".plan-panel__body");
      var hint = div.querySelector(".plan-panel__hint");
      L.DomEvent.on(collapseBtn, "click", function () {
        var collapsed = body.hidden;
        body.hidden = !collapsed;
        hint.hidden = !collapsed;
        collapseBtn.textContent = collapsed ? "−" : "+";
      });

      return div;
    };
    ctrl.addTo(mapPlan);   // <-- attaches to the dedicated right-side map
  }

  // ---------- Time scrubber (bottom-left): drag through 1984 to 2025 ----------
  function buildTimeScrubber() {
    var EPOCHS = [
      { id: "class_1984_92", label: "1984 to 1992" },
      { id: "class_1993_01", label: "1993 to 2001" },
      { id: "class_2002_10", label: "2002 to 2010" },
      { id: "class_2011_18", label: "2011 to 2018" },
      { id: "class_2019_25", label: "2019 to 2025" }
    ];
    // Only build if at least the first epoch exists in the manifest
    if (!rasterManager.entry(EPOCHS[0].id)) return;

    var ctrl = L.control({ position: "bottomleft" });
    ctrl.onAdd = function () {
      var div = L.DomUtil.create("div", "time-scrubber");
      var tickHtml = EPOCHS.map(function (e, i) {
        return '<span class="time-scrubber__tick" data-i="' + i + '">' + e.label + '</span>';
      }).join("");
      div.innerHTML =
        '<div class="time-scrubber__head">' +
          '<button class="time-scrubber__play" type="button" aria-label="Play">&#9654;</button>' +
          '<strong>Land Cover Time Series, 1984 to 2025</strong>' +
        '</div>' +
        '<div class="time-scrubber__ticks">' + tickHtml + '</div>' +
        '<input type="range" min="0" max="4" step="1" value="0" class="time-scrubber__slider" />';

      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);

      var slider = div.querySelector(".time-scrubber__slider");
      var ticks = Array.prototype.slice.call(div.querySelectorAll(".time-scrubber__tick"));
      var playBtn = div.querySelector(".time-scrubber__play");

      function setEpoch(idx) {
        var spec = EPOCHS[idx];
        if (!spec) return;
        ticks.forEach(function (t, i) {
          t.classList.toggle("is-active", i === idx);
        });
        slider.value = String(idx);
        // Drive the same showRasterView so legend updates and parishes overlay
        showRasterView(spec.id);
        // Sync the right-side picker dropdown if present
        if (window.__satPicker && window.__satPicker.select) {
          window.__satPicker.select.value = spec.id;
        }
      }

      L.DomEvent.on(slider, "input", function () {
        setEpoch(parseInt(slider.value, 10));
      });
      ticks.forEach(function (t) {
        L.DomEvent.on(t, "click", function () {
          setEpoch(parseInt(t.dataset.i, 10));
        });
      });

      var playInterval = null;
      L.DomEvent.on(playBtn, "click", function () {
        if (playInterval) {
          clearInterval(playInterval);
          playInterval = null;
          playBtn.innerHTML = "&#9654;";
          return;
        }
        playBtn.innerHTML = "&#10073;&#10073;"; // pause symbol
        var i = parseInt(slider.value, 10);
        playInterval = setInterval(function () {
          i = (i + 1) % EPOCHS.length;
          setEpoch(i);
        }, 1500);
      });

      // Don't auto-activate; user starts when ready
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
    // Top-right of the left map so it stacks below the picker and cannot
    // collide with the time scrubber that lives in the bottom-left.
    legend = L.control({ position: "topright" });
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
    // When switching to a non-raster view, hide the satellite overlays
    // but keep any planning maps the user has explicitly checked on.
    if (!(view && view.indexOf("raster_") === 0)) {
      rasterManager.hideCategory("Satellite Analysis Layers");
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

    if (rasterManager.manifest.length) {
      buildSatellitePicker();
      buildPlanningPanel();
      buildTimeScrubber();
    }

    // Populate the planning map gallery (thumbnails click through to lightbox)
    var galleryEl = document.getElementById("plan-map-gallery");
    if (galleryEl) {
      var planEntries = rasterManager.manifest.filter(function (e) {
        return e.category === "Government Planning Maps";
      });
      if (planEntries.length) {
        galleryEl.innerHTML = planEntries.map(function (e) {
          return '<figure class="plan-thumb">' +
            '<a href="#" data-lightbox="' + e.id + '" title="' + e.title + '">' +
              '<img loading="lazy" src="' + e.png + '" alt="' + e.title + '" />' +
            '</a>' +
            '<figcaption>' + e.title + '</figcaption>' +
          '</figure>';
        }).join("");
      } else {
        galleryEl.innerHTML = '<p style="color:#8a8170;font-style:italic;">No planning maps found in data/planning_maps.json.</p>';
      }
    }

    views.overview();
    initScroller();
    window.setTimeout(function () {
      map.invalidateSize();
      mapPlan.invalidateSize();
    }, 300);
  }).catch(function (e) {
    console.error(e);
    document.getElementById("map").innerHTML =
      '<div style="padding:2rem;font-family:sans-serif;color:#095159">Could not load map data: ' + e.message + "</div>";
  });

  // Keep both maps sized correctly on resize.
  window.addEventListener("resize", function () {
    map.invalidateSize();
    if (typeof mapPlan !== "undefined") mapPlan.invalidateSize();
  });
})();
