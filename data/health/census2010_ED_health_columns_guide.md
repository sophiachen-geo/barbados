# 2010 Census ED-level CSV — column guide for the health pipeline

Source file: `2010_Demographics_4087252853532491516.csv` (424 KB, ~600 rows = enumeration districts)

The file came from a shapefile attribute table (`Shape__Area` and `Shape__Length` columns are present). To do anything spatial with it you need the matching ED shapefile — request from Barbados Statistical Service (`stats.gov.bb`) or Lands & Surveys Department.

## Identifier columns

| Column | Purpose |
|---|---|
| `FID` | ArcGIS internal feature ID — do not use as a permanent join key |
| `ID` | Stable ED identifier — **use this to join to the shapefile** |
| `Enumeration District` | ED number within parish |
| `Parish Name` | One of: St. Michael, Christ Church, St. Philip, St. John, St. Joseph, St. Andrew, St. Lucy, St. Peter, St. James, St. Thomas, St. George |
| `Shape__Area`, `Shape__Length` | Geometry in degrees (WGS84) — area in deg² |

## Population denominators

`Total Population`, `Males`, `Females` — use these to convert raw disease counts to per-capita rates.

## Direct disease counts (the join targets)

| Column (verbatim) | Suggested derived field |
|---|---|
| `Asthma` | `asthma_per1000 = Asthma / Total_Population * 1000` |
| `Diabeted` | `diabetes_per1000` (note CSV typo — preserve original name in joins, rename in derivative) |
| `Kidney Disease` | `kidney_per1000` |
| `Heart Disease` | `heart_disease_per1000` ← **primary CVD signal** |
| `Hypertension` | `hypertension_per1000` ← **top BNR risk factor** |
| `No Disease Stated` | denominator check |
| `Other Disease` | residual |

## Mobility / functional limitation

These are likely under-reported but informative as relative measures across EDs:

- `Doctor Diagnosed Disability`
- `Deafness`, `Hearing Impaired`, `Blindness`, `Vision Impaired`, `Unable to Speak`
- `Severe Arthritis`, `Unable to Walk`, `Unable to Climb Stairs`, `Unable to Care for Self`
- `Mental Illness`, `Intellectually Challenged`, `Learning Disability`
- `Needs Wheelchair`, `Needs Walker`, `Needs Crutches`, `Needs Cane`

## Dwelling-vintage cohorts — DIRECT crosswalk to your urban-expansion analysis

The CSV has the count of dwellings in each ED by construction era:

| Census column | Maps to GEE epoch |
|---|---|
| `Dwellings Built Before 1990` | Pre-baseline (already-urban in your 1984-86 composite) |
| `Dwellings Built 1991-1999` | Early-expansion epoch |
| `Dwellings Built 2000-2003` | Mid-expansion |
| `Dwellings Built 2004-2007` | Late-2000s boom |
| `Dwelling Units Built in 2008` | Pre-recession peak |
| `Dwelling Units Built in 2009` | Recession |
| `Dwelling Units Built in 2010` | Recovery |

**Validation use:** for each ED, the sum of post-1990 dwellings should correlate with the count of "new-urban" pixels (1984→2020) intersecting that ED. If they don't, your Landsat classification is suspect for that ED.

## Tourism / housing-speculation signals

| Column | Interpretation |
|---|---|
| `Townhouse or Condominium` | Tourism-oriented dwelling type |
| `Flat or Apartment` | Often short-term-rentable |
| `Separate Houses` | Resident-oriented |
| `Unoccupied Dwellings for Rent` | Short-term-rental supply OR vacant rental stock |
| `Unoccupied Dwellings for Sale` | Speculative inventory |
| `Unoccupied Dwellings for Rent or Sale` | Combined idle stock |
| `Unoccupied Dwellings with Other Arrangements` | Often second homes |
| `Dwelling Units that are Derelict` | **Community displacement / abandonment signal** |
| `Dwelling Units Under Inactive Construction` | Stalled development |
| `Occupied Dwellings that are Privately Rented/Leased` | Renter share |

Suggested composite:

```
tourism_pressure_index = (Townhouse_or_Condominium
                        + Unoccupied_For_Rent
                        + Unoccupied_For_Rent_or_Sale
                        + Unoccupied_For_Sale
                        + Unoccupied_With_Other_Arrangements)
                       / Number_of_Dwelling_Units
```

Range 0-1+ (can exceed 1 if many unoccupied per occupied). High values on the West Coast parishes predict the 7thHeaven listing locations.

```
abandonment_share = Dwelling_Units_that_are_Derelict / Number_of_Dwelling_Units
```

## Wealth / SES confounders

Don't omit — these are the main confounders in any "land-use causes disease" regression:

- Vehicle ownership: `Dwellings with 0 / 1 / 2 / 3 / 4+ Private Vehicles Kept at Home`
- Income bands: `0-49999YEA`, `50000-9999`, `100000-149`, `150000-199`, `200000YEAR`
- Education: `Highest Attainment: Tertiary`, `Highest Attainment: Post-Secondary`, etc.
- Internet: `Internet Used Most Often At Home`
- Tenure: `Occupied Dwellings that are Owned` vs `Rented/Leased`
- Appliances: refrigerator/microwave/AC/dishwasher counts

## Safety covariates (interact with outdoor activity)

- `Persons a Victim of Crime in the Past 12 Months`
- `Persons a Victim of Robbery`, `Persons a Victim of Wounding`, etc.

High crime victimisation can suppress walking/recreation independent of physical built environment.

## How to actually do the join (once you have the shapefile)

```python
# After you have Barbados.gdb/Vector/EnumerationDistricts loaded
import arcpy
arcpy.management.JoinField(
    in_data="Barbados.gdb/Vector/EnumerationDistricts",
    in_field="ED_ID",                                                # or whatever the shapefile calls it
    join_table=r"Health_Data\2010_Demographics_4087252853532491516.csv",
    join_field="ID",
    fields=["Heart Disease", "Hypertension", "Diabeted", "Asthma",
            "Kidney Disease", "Total Population",
            "Dwellings Built Before 1990",
            "Dwelling Units that are Derelict",
            # ...and any other columns you want available downstream
            ],
)
```

Then add the per-capita and composite-index fields with `arcpy.management.CalculateField`. After that, every Phase 6/7/8 step in the pipeline can use the ED layer as `role: admin_fine` and produce ED-level outputs.
