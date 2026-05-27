/* Charts for the Barbados scrollytelling site.
   Reads the real health CSVs in data/health/ and the regression findings JSON,
   and renders into a single shared canvas (#chart-canvas). */
(function () {
  "use strict";

  var PALETTE = {
    ink: "#15242b",
    teal: "#0e7c86",
    tealDark: "#095159",
    coral: "#d2603a",
    coralSoft: "#e08a6a",
    sand: "#c9b889",
    grid: "rgba(21,36,43,0.10)",
    muted: "#8a8170"
  };

  var cache = {};       // url -> parsed rows / json
  var currentChart = null;

  function fetchText(url) {
    if (cache[url]) return Promise.resolve(cache[url]);
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("Failed to load " + url + " (" + r.status + ")");
      return r.text();
    }).then(function (t) { cache[url] = t; return t; });
  }

  function fetchJSON(url) {
    if (cache[url]) return Promise.resolve(cache[url]);
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("Failed to load " + url);
      return r.json();
    }).then(function (j) { cache[url] = j; return j; });
  }

  // Minimal CSV parser (these files contain no quoted commas).
  function parseCSV(text) {
    var lines = text.replace(/\r/g, "").split("\n").filter(function (l) { return l.trim() !== ""; });
    var headers = lines[0].split(",");
    return lines.slice(1).map(function (line) {
      var cells = line.split(",");
      var obj = {};
      headers.forEach(function (h, i) { obj[h.trim()] = (cells[i] || "").trim(); });
      return obj;
    });
  }

  function destroy() {
    if (currentChart) { currentChart.destroy(); currentChart = null; }
  }

  function baseOpts(extra) {
    var o = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600 },
      plugins: {
        legend: { labels: { color: PALETTE.ink, font: { size: 12 } } },
        tooltip: { backgroundColor: PALETTE.tealDark }
      },
      scales: {
        x: { ticks: { color: PALETTE.ink }, grid: { color: PALETTE.grid } },
        y: { ticks: { color: PALETTE.ink }, grid: { color: PALETTE.grid } }
      }
    };
    return Object.assign(o, extra || {});
  }

  function ctx() { return document.getElementById("chart-canvas").getContext("2d"); }

  // ---- chart builders, each returns a promise resolving to {title, sub, source} ----
  var builders = {

    regression: function () {
      return fetchJSON("data/field/listings_findings.json").then(function (d) {
        var rows = d.coefficients.slice().sort(function (a, b) { return a.effect_pct - b.effect_pct; });
        destroy();
        currentChart = new Chart(ctx(), {
          type: "bar",
          data: {
            labels: rows.map(function (r) { return r.factor.replace(" (vs other types)", "").replace(" (vs other locations)", ""); }),
            datasets: [{
              label: "% effect on listed price",
              data: rows.map(function (r) { return r.effect_pct; }),
              backgroundColor: rows.map(function (r) { return r.direction === "increase" ? PALETTE.teal : PALETTE.coral; }),
              borderRadius: 4
            }]
          },
          options: baseOpts({
            indexAxis: "y",
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: function (c) { return (c.raw > 0 ? "+" : "") + c.raw + "% vs baseline"; } } }
            },
            scales: {
              x: { ticks: { color: PALETTE.ink, callback: function (v) { return v + "%"; } }, grid: { color: PALETTE.grid }, title: { display: true, text: "Change in listed price, all else equal", color: PALETTE.muted } },
              y: { ticks: { color: PALETTE.ink, font: { size: 11 } }, grid: { display: false } }
            }
          })
        });
        return {
          title: "What drives a luxury listing's price",
          sub: "Multiple regression on 135 listings (7thHeaven, May 2020). Teal = premium, coral = discount.",
          source: "Source: Chen & Ejov web-scrape + MLR (log price, p < 0.05)."
        };
      });
    },

    cvd: function () {
      return fetchText("data/health/barbados_cvd_timeseries_2013_2022.csv").then(function (t) {
        var rows = parseCSV(t);
        var years = rows.map(function (r) { return r.year; });
        destroy();
        currentChart = new Chart(ctx(), {
          type: "line",
          data: {
            labels: years,
            datasets: [
              {
                label: "Heart attack (AMI) incidence /100k",
                data: rows.map(function (r) { return +r.ami_crude_incidence_per100k; }),
                borderColor: PALETTE.coral, backgroundColor: PALETTE.coral,
                tension: 0.3, borderWidth: 3, pointRadius: 3
              },
              {
                label: "Stroke incidence /100k",
                data: rows.map(function (r) { return +r.stroke_crude_incidence_per100k; }),
                borderColor: PALETTE.teal, backgroundColor: PALETTE.teal,
                tension: 0.3, borderWidth: 3, pointRadius: 3, borderDash: [6, 4]
              }
            ]
          },
          options: baseOpts({
            scales: {
              x: { ticks: { color: PALETTE.ink }, grid: { color: PALETTE.grid } },
              y: { beginAtZero: false, ticks: { color: PALETTE.ink }, grid: { color: PALETTE.grid }, title: { display: true, text: "Crude incidence per 100,000", color: PALETTE.muted } }
            }
          })
        });
        return {
          title: "Cardiovascular incidence, 2013–2022",
          sub: "Heart-attack incidence climbs ~55% (2013–2020); stroke stays flat — the divergence is the signal.",
          source: "Source: Barbados National Registry for Chronic NCDs, CVD Annual Report 2024."
        };
      });
    },

    riskfactors: function () {
      return fetchText("data/health/barbados_ncd_risk_factor_prevalence.csv").then(function (t) {
        var rows = parseCSV(t);
        var ami = rows.filter(function (r) { return r.cohort === "hospitalised_ami" && r.year === "2014"; });
        var order = ["hypertension", "obesity", "diabetes", "high_cholesterol"];
        var lookup = {};
        ami.forEach(function (r) { lookup[r.risk_factor] = +r.prevalence_pct; });
        destroy();
        currentChart = new Chart(ctx(), {
          type: "bar",
          data: {
            labels: ["Hypertension", "Obesity", "Diabetes", "High cholesterol"],
            datasets: [{
              label: "% of hospitalised heart-attack patients (2014)",
              data: order.map(function (k) { return lookup[k]; }),
              backgroundColor: [PALETTE.coral, PALETTE.coral, PALETTE.coralSoft, PALETTE.sand],
              borderRadius: 4
            }]
          },
          options: baseOpts({
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return c.raw + "% of patients"; } } } },
            scales: {
              x: { ticks: { color: PALETTE.ink }, grid: { display: false } },
              y: { beginAtZero: true, max: 100, ticks: { color: PALETTE.ink, callback: function (v) { return v + "%"; } }, grid: { color: PALETTE.grid } }
            }
          })
        });
        return {
          title: "The mechanism: risk factors behind heart attacks",
          sub: "Among hospitalised AMI patients, 86% had hypertension and 86% were obese — both shaped by the built environment.",
          source: "Source: National Strategic Plan for NCD Prevention & Control 2020–2025 (QEH 2014 cohort)."
        };
      });
    },

    activity: function () {
      return fetchText("data/health/barbados_ncd_risk_factor_prevalence.csv").then(function (t) {
        var rows = parseCSV(t);
        function val(rf) {
          var m = rows.filter(function (r) { return r.cohort === "students_13_15" && r.sex === "both" && r.risk_factor === rf; });
          return m.length ? +m[0].prevalence_pct : null;
        }
        var data = [
          { label: "Active 60min, 5+ days/wk", v: val("physically_active_60min_5days_per_week"), good: true },
          { label: "Sedentary 3+ hrs/day", v: val("sedentary_3plus_hours_per_day"), good: false },
          { label: "Soft drink daily", v: val("carbonated_soft_drink_daily"), good: false },
          { label: "Overweight", v: val("overweight"), good: false },
          { label: "Obese", v: val("obese"), good: false }
        ];
        destroy();
        currentChart = new Chart(ctx(), {
          type: "bar",
          data: {
            labels: data.map(function (d) { return d.label; }),
            datasets: [{
              label: "% of students aged 13–15",
              data: data.map(function (d) { return d.v; }),
              backgroundColor: data.map(function (d) { return d.good ? PALETTE.teal : PALETTE.coral; }),
              borderRadius: 4
            }]
          },
          options: baseOpts({
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return c.raw + "%"; } } } },
            scales: {
              x: { ticks: { color: PALETTE.ink, font: { size: 10 } }, grid: { display: false } },
              y: { beginAtZero: true, max: 100, ticks: { color: PALETTE.ink, callback: function (v) { return v + "%"; } }, grid: { color: PALETTE.grid } }
            }
          })
        });
        return {
          title: "An obesogenic environment, in the young",
          sub: "Only ~29% of teens meet activity targets while ~65% are sedentary — the behavioural footprint of a car-dependent, low-green-space landscape.",
          source: "Source: Global School-based Student Health Survey (GSHS) 2011, ages 13–15."
        };
      });
    }
  };

  window.BarbadosCharts = {
    render: function (view) {
      var b = builders[view];
      if (!b) return Promise.reject(new Error("Unknown chart view: " + view));
      return b();
    },
    destroy: destroy
  };
})();
