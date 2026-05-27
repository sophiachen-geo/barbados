# Barbados Health Data Synthesis — for Land Use × Tourism × Health Project

Curated extraction from three sources, scoped to your project's window (≤2020) and to variables that plausibly link land-use change and tourism real-estate expansion to health outcomes.

| Source | Coverage | Spatial unit | Years |
|---|---|---|---|
| 2010 Census Demographics CSV (Barbados Statistical Service / Lands & Surveys) | Population, dwelling, **self-reported chronic disease** | Enumeration District (ED, ~600 EDs) | 2010 cross-section |
| Barbados National Registry CVD Annual Report 2024 | Heart attack + stroke incidence, mortality, risk factors | National (with QEH catchment context) | Annual 2013-2022 |
| National Strategic Plan for NCD Prevention & Control 2020-2025 | Risk-factor epidemiology, behavioural data, NCD policy framework | National + school-based | Various, mostly 2010-2018 |

---

## 1. The 2010 Census ED-level data — your most powerful spatial join

This is the only health dataset you have at **sub-parish resolution**. ~600 EDs nest inside the 11 parishes you already have polygons for. The CSV came from a shapefile (`Shape__Area`, `Shape__Length` columns are present), so the ED geometry exists somewhere on the BSS / Lands & Surveys side — you should request the matching shapefile, or reconstruct it by re-exporting from the source.

### Health-relevant columns (exact CSV field names)

| Column | Type | Interpretation for your project |
|---|---|---|
| `Doctor Diagnosed Disability` | count | Any disability — proxy for accumulated health burden |
| `Asthma` | count | Most affected by air quality / heat / urban density |
| `Diabeted` (sic — typo for Diabetes) | count | Tied to obesogenic built environment |
| `Kidney Disease` | count | Downstream of diabetes/hypertension |
| `Heart Disease` | count | The direct CVD signal |
| `Hypertension` | count | Top risk factor for both stroke and AMI in BNR data |
| `No Disease Stated` | count | Healthy denominator |
| `Other Disease` | count | Misc — drop unless cleaning specific |
| `Severe Arthritis` | count | Mobility-limiting; affects walkability response |
| `Unable to Walk`, `Unable to Climb Stairs`, `Unable to Care for Self` | counts | Mobility — interacts directly with built environment |
| `Mental Illness` | count | Less directly land-use-linked but worth flagging |

### Built-environment columns relevant as covariates

| Column | Use |
|---|---|
| `Total Population`, `Males`, `Females`, age proxies | Denominators for prevalence rates |
| `Dwellings Built Before 1990` … `Dwelling Units Built in 2010` (7 cohorts) | **Crosswalk to your 1984-2020 urban-expansion raster.** Pre-1990 buildings should geographically coincide with stable-urban pixels; post-1990 builds should coincide with newly-urban pixels. This is a direct validation of the GEE classification. |
| `Unoccupied Dwellings for Rent`, `…for Sale`, `…for Rent or Sale`, `Derelict` | **Tourism/speculation proxy.** High unoccupied-for-rent counts on the West Coast = short-term-rental supply. Derelict counts = community displacement signal. |
| `Townhouse or Condominium`, `Flat or Apartment` | Tourism-oriented housing types vs `Separate Houses` (resident-oriented) |
| `Dwellings with 0/1/2/3+ Private Vehicles` | Car dependence — interacts with walkability and physical inactivity |
| `Number of Refrigerators / TVs / Computers / Air Conditioners (implied)` etc. | Wealth/affluence proxies — confounders to control for |
| `Persons a Victim of Crime …` (and breakdowns) | Safety — affects outdoor activity, neighborhood selection by tourists |
| `Internet Used Most Often At Home` | Digital connectivity — relates to remote-work housing demand (Welcome Stamp era) |

### How this joins to your pipeline

In `config/barbados.yaml`, you already have a `Parishes` admin vector. **Add an `EDs` vector** once you have the shapefile. Every Phase 6/7 analysis becomes available at ED resolution:

- Phase 6.1 transition matrix per ED (much more granular than per-parish)
- Phase 6.2 leisuring rate per ED
- Phase 7 listings get richer joined attributes (ED-level chronic disease prevalence as covariate)
- Phase 8 GLR/GWR gains a vastly larger sample size (~600 vs 11), unlocking real spatial statistics

---

## 2. CVD Annual Report — national time series (2013-2022)

National-only data; **no parish or ED breakdown exists publicly**. But the temporal trend is your main joining axis to the 1984-2020 land-use change.

Saved as: [`barbados_cvd_timeseries_2013_2022.csv`](barbados_cvd_timeseries_2013_2022.csv) — 10 rows × 18 columns ready to plot or join by year.

### Headline trend (2013 → 2020, your project window)

| Metric | 2013 | 2020 | Change |
|---|---|---|---|
| AMI cases (total) | 352 | 547 | **+55%** |
| AMI crude incidence per 100k | 124 | 190 | **+53%** |
| AMI ASIR men | 93 | 124 | +33% |
| AMI ASIR women | 57 | 77 | +35% |
| AMI ASMR men | 56 | 66 | +18% |
| Stroke cases (total) | 695 | 700 | flat |
| Stroke crude incidence per 100k | 244.5 | 243.6 | flat |
| Stroke ASIR men | 162 | 149 | −8% |

The **AMI signal is the story**: a real 50%+ increase in heart-attack incidence over the same 7-year window your pipeline's recent-Esri-S2 change analysis covers (2017-2024). Stroke is stable. This means:

- Your "Welcome-Stamp-era recent change" analysis (Phase 6.5: 2017→2024 Esri/IO transitions) should overlay temporally on rising AMI.
- Hypertension and diabetes are the two top BNR-reported risk factors (65% and 47% of hospitalised AMI patients in 2022). Both are obesogenic-environment-driven. **This is your causal-pathway argument**: built environment intensification → reduced walkability/green space → obesity/HTN/DM → AMI.

### Important methodological caveat for the project

> "Out-of-hospital deaths and in-hospital deaths within 24 hours were identified through the national vital registration department by checking all death certificate diagnoses that list any form of ischemic heart disease (IHD) as the main cause of death."

So the **address of the deceased** is in the vital registration record. The BNR could, in principle, produce parish-level mortality — they just don't publish it. If you want sub-national CVD data, contact:

- BNR / GA-CDRC, UWI Cave Hill — Dr Natasha Sobers (Head of NCD Surveillance, bnr@cavehill.uwi.edu, +246 426 6416)

Worth asking for: AMI + stroke counts by parish 2013-2020. Would dramatically strengthen the spatial analysis.

---

## 3. NCD Strategic Plan 2020-2025 — context + risk-factor framing

The plan is national-level, no spatial breakdowns, but it provides **the explicit policy framing** that lets you justify the land-use→health pathway in your paper's introduction.

### Key prevalence numbers (HoTNS 2012-2013, adults 25+)

- **8 in 10 men** and **9 in 10 women** had ≥1 NCD risk factor
- **2 of every 3 adults** were overweight or obese
- ~10% women / ~5% men had BMI ≥ 35 ("gross obesity")
- 1 in 10 men / 1 in 50 women reported daily tobacco use
- Combination of 3+ risk factors more common in women and older adults

### Children (GSHS 2011, ages 13-15)

- 31.9% overweight; 14.2% obese
- **Only 29.1% physically active 60min/day on 5+ days/week** ← direct built-environment indicator
- **64.9% spent 3+ hours/day sedentary**
- 73.3% drank soft drinks 1+ times/day

### Mortality framing (WHO 2016 estimates for Barbados)

| Cause | % of all deaths |
|---|---|
| CVD | 29% |
| Cancer | 23% |
| Other NCDs | 18% |
| Diabetes | 9% |
| Chronic respiratory | 4% |
| **NCDs subtotal** | **83%** |
| Premature mortality risk from NCDs (men) | 20% |
| Premature mortality risk from NCDs (women) | 13% |

### Healthcare-system burden (your "loss of public goods" angle)

- NCDs = **70% of QEH budget** + Drug Service budget
- **80% of polyclinic visits** (excluding maternal/child) are for chronic disease
- Polyclinic prescription spend: 49.7% hypertension, 32.4% diabetes, 8.6% glaucoma, 7.4% asthma, 1.9% cancer
- In 2014: 584 strokes (481 admitted); 411 AMI/SCD events
  - Of hospitalised stroke patients: 89% HTN, 72% DM, 67% high cholesterol, 39% obese
  - Of hospitalised AMI patients: 86% HTN, 86% obese, 80% DM, 76% high cholesterol

### Critical quotes for paper framing

> "The Global Syndemic of obesity, undernutrition, and climate change … with major systems of food and agriculture, transportation, **urban design, and land use** driving the syndemic."

> "The obesogenic environment is defined as 'the sum of influences that the surroundings, opportunities, or conditions of life have on promoting obesity in individuals or populations.'" — Lake & Townshend 2006

> "Creation of an enabling environment — including policy, legislation, regulations and wellness grants — that facilitates, encourages, and supports healthy choices…"

The plan explicitly names the Ministry of Transport, Works and Maintenance (MTWM) as a partner — i.e., the Barbados government already accepts that road/land/transport planning belongs in the NCD response. Your project provides the missing spatial evidence to operationalise that.

### Programme to cite as a real-world hook

> "Barbados Moves' parish by parish, through direct activities…"

This is a national physical-activity promotion program. Your parish-level leisuring rate (Phase 6.2 output) maps directly onto the geographic units that program already targets. If certain parishes are losing green/open space fastest, those are exactly the parishes where Barbados Moves should be intensified.

---

## 4. Concrete pipeline updates to add

These are additive — they don't break what we already built. I've not modified `barbados.yaml` yet; check the proposals below first.

### A. Add ED-level admin layer (highest leverage)

In `config/barbados.yaml`, under `vectors:`, add:

```yaml
  - name: EnumerationDistricts
    source_file: Inputs_Vector/EDs/barbados_eds_2010.shp   # TODO: obtain from BSS
    gdb_target: Vector/EnumerationDistricts
    role: admin_fine
    name_field: ED_ID
    join_csv: Health_Data/2010_Demographics_4087252853532491516.csv
    join_field: ID                                           # CSV "ID" column -> ED_ID
```

Then a new Phase 4b ("ingest ED-level census") joins the CSV columns onto the EDs feature class. Every Phase 6 analysis can then run twice — once at parish, once at ED — with the same code.

### B. Add CVD time series for temporal correlation

The CSV I just wrote (`Health_Data/barbados_cvd_timeseries_2013_2022.csv`) is national-only — there's no spatial join. But you can use it to test:

1. Annual change in urban hectares (from the Esri/IO multidimensional mosaic, Phase 3 output, summed by year)
2. Annual AMI crude incidence (from the CSV)
3. Plot together → visual correlation; compute Pearson/Spearman r on the 8-year overlap (2017-2022 Esri S2 vs 2017-2022 AMI).

Save as `Outputs/temporal_correlation_urbanization_vs_ami.csv` — a one-table deliverable.

### C. Designate "tourism intensification" composite from 2010 census

Build a per-ED index from the unoccupied-dwelling columns:

```
tourism_pressure = (Unoccupied_For_Rent + Unoccupied_For_Sale + Townhouse_Condominium)
                 / Total_Dwelling_Units
```

This becomes a new explanatory variable in Phase 8 GLR/GWR, joined to listings via spatial location.

### D. Health-outcome dependent variables for Phase 8

Once you have the ED layer joined, your dependent variable options widen:

- `heart_disease_per_capita` = Heart_Disease / Total_Population
- `hypertension_per_capita` = Hypertension / Total_Population
- `chronic_disease_burden` = (Heart_Disease + Hypertension + Diabeted + Asthma + Kidney_Disease) / Total_Population

Run separate GLR/GWR per dependent variable with the same explanatory set (leisuring rate, urban expansion %, distance to coast, tourism pressure index). The variable with the strongest coefficient on leisuring rate is the headline finding.

---

## 5. What's missing — and where to find it

| Gap | Why it matters | Where to look |
|---|---|---|
| Parish/ED CVD incidence + mortality | Sub-national time series would let you do panel regression of land-use change → CVD with proper controls | Request from BNR (Dr Natasha Sobers, UWI Cave Hill). Likely requires a data-use agreement. |
| 2020 (or later) census equivalent | Refresh the 2010 ED data | BSS — 2020 census fieldwork was COVID-disrupted; check `stats.gov.bb` for status |
| Mortality cause-of-death by parish | Closes the loop on "more change → more disease → more death" | Vital Statistics Registration Dept, Ministry of Health and Wellness |
| Air quality / PM2.5 / NO2 | Mechanistic pathway (urban heat + traffic emissions → CVD) | CAMS reanalysis (free via Copernicus); MODIS AOD as proxy |
| Land surface temperature | Direct heat exposure (already extracted from your Landsat composites!) | **You already have this**: `Derivatives/TEMP_2020.tif` from GEE composite band 6 |
| Walkability / road density | Active-transport opportunity | Compute from `Vector/Roads` (OSM extract) — line density per ED via Spatial Analyst |
| Healthcare access | Distance-to-polyclinic confounds incidence (sicker pop near hospitals?) | Get parish polyclinic locations from MOH — geocode 9 polyclinic addresses |

---

## 6. The single-sentence finding your project is set up to defend

> Between 1984 and 2020, Barbados's tourism-driven urban expansion converted ~X% of formerly herbaceous and agricultural land along the West Coast to built area, with significantly elevated AMI incidence trajectories (and a documented obesogenic-environment risk-factor profile) in the parishes that lost the most non-urban land.

The pipeline produces the X% (Phase 6.1). The 2010 ED data provides the spatial overlap of disease prevalence at the time of greatest tourism real-estate intensification. The CVD time series provides the temporal trend. The NCD Strategic Plan provides the policy framing and risk-factor mechanism.
