// =====================================================================
// Barbados Land Cover — REVISED: Surface Reflectance + 5-class + extended window
//
// Drop-in replacement for 04_classify_with_challenge_improvements.js
//
// Fixes vs script 04:
//   1. Surface Reflectance (Collection 2 Level-2) instead of TOA Level-1
//      → proper atmospheric correction, critical for multi-decade analysis
//   2. Historical window extended: 1984-1986 → 1984-1988 (5 years instead of 3)
//   3. Historical cloud threshold raised: 60 → 90 (per-pixel QA mask handles
//      actual clouds; the metadata filter just gates which scenes load)
//   4. Class scheme collapsed: 8 → 5 (Ag, Natural Veg, Urban, Water, Bare)
//   5. Path/row diagnostics printed for both composites
//
// Outputs tagged _v3 so they don't collide with previous runs.
// =====================================================================

// --- AOI ---
var countryName = 'Barbados';
var countries = ee.FeatureCollection("FAO/GAUL/2015/level0");
var aoi = countries.filter(ee.Filter.eq('ADM0_NAME', countryName));
Map.addLayer(aoi, {}, 'AOI', false);
Map.centerObject(aoi, 12);

// --- Reference land cover: load 8-class, remap to 5-class ---
var refLandCover8 = ee.Image("projects/caribbean-trainings/assets/barbados-2022/images/CopernicusLC_8Class")
  .selfMask();

// 5-class scheme:
//   1 = Agriculture       (was Copernicus 1)
//   2 = Natural Vegetation (was Copernicus 3 Herb + 4 Forest + 5 Shrub + 8 Wetland)
//   3 = Urban             (was Copernicus 6)
//   4 = Water             (was Copernicus 7)
//   5 = Bare              (was Copernicus 2)
var refLandCover = refLandCover8.remap(
  [1, 2, 3, 4, 5, 6, 7, 8],      // original Copernicus classes
  [1, 5, 2, 2, 2, 3, 4, 2]       // new 5-class scheme
).rename('class');

var lcViz5 = {
  min: 1, max: 5,
  palette: ['#f096ff',  // 1 Ag — pink
            '#007800',  // 2 Natural Veg — green
            '#fa0000',  // 3 Urban — red
            '#0032c8',  // 4 Water — blue
            '#b4b4b4']  // 5 Bare — grey
};
Map.addLayer(refLandCover, lcViz5, '5-class Reference (Remapped)');

// --- Surface Reflectance scale factor application ---
// Collection 2 Level-2 SR bands need: DN * 0.0000275 + (-0.2) → 0-1 reflectance
// Surface Temperature bands need: DN * 0.00341802 + 149.0 → Kelvin
function applyScaleFactors(image) {
  var opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2);
  var thermalBand = image.select('ST_B.*').multiply(0.00341802).add(149.0);
  return image
    .addBands(opticalBands, null, true)
    .addBands(thermalBand, null, true);
}

// --- Band dictionaries for SR ---
// L5/L7: SR_B1=blue, B2=green, B3=red, B4=NIR, B5=SWIR1, B7=SWIR2, ST_B6=thermal
// L8/L9: SR_B2=blue, B3=green, B4=red, B5=NIR, B6=SWIR1, B7=SWIR2, ST_B10=thermal
//        (L8/L9 SR_B1 is coastal aerosol, dropped here)
var sensorBandDict = {
  'L9': ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'ST_B10', 'SR_B7', 'QA_PIXEL'],
  'L8': ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'ST_B10', 'SR_B7', 'QA_PIXEL'],
  'L7': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'ST_B6',  'SR_B7', 'QA_PIXEL'],
  'L5': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'ST_B6',  'SR_B7', 'QA_PIXEL']
};
var bandNames = ['blue', 'green', 'red', 'nir', 'swir1', 'temp', 'swir2', 'QA_PIXEL'];

// --- Cloud / shadow mask using QA_PIXEL ---
// Collection 2 L2 uses the same bit layout as L1 TOA for QA_PIXEL
function cloudShadowMask(image) {
  var cloudShadowBitMask = (1 << 4);   // bit 4 = cloud shadow
  var cloudsBitMask = (1 << 3);        // bit 3 = cloud
  var qa = image.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0)
              .and(qa.bitwiseAnd(cloudsBitMask).eq(0));
  return ee.Image(image).updateMask(mask);
}

// --- Spectral indices ---
function calculateIndices(img) {
  var ndvi  = img.normalizedDifference(['nir', 'red']).rename('ndvi');
  var lswi  = img.normalizedDifference(['nir', 'swir1']).rename('lswi');
  var ndmi  = img.normalizedDifference(['swir2', 'red']).rename('ndmi');
  var mndwi = img.normalizedDifference(['green', 'swir2']).rename('mndwi');
  return img.addBands(ndvi).addBands(lswi).addBands(ndmi).addBands(mndwi);
}

// --- Composite builder using SR collections ---
function buildComposite(startdate, enddate, cloudMax, label) {
  var dateFilter = ee.Filter.date(startdate, enddate);

  var lt5 = ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
    .map(applyScaleFactors)
    .select(sensorBandDict['L5'], bandNames);

  var le7 = ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
    .map(applyScaleFactors)
    .select(sensorBandDict['L7'], bandNames);

  var lc8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
    .map(applyScaleFactors)
    .select(sensorBandDict['L8'], bandNames);

  var lc9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
    .map(applyScaleFactors)
    .select(sensorBandDict['L9'], bandNames);

  var merged = lt5.map(cloudShadowMask).map(calculateIndices)
    .merge(le7.map(cloudShadowMask).map(calculateIndices))
    .merge(lc8.map(cloudShadowMask).map(calculateIndices))
    .merge(lc9.map(cloudShadowMask).map(calculateIndices));

  var filtered = merged.filter(dateFilter);
  print('processed Landsat Collection (' + label + ')', filtered);
  print('  scene count (' + label + ')', filtered.size());
  print('  scenes by WRS_PATH (' + label + ')', filtered.aggregate_histogram('WRS_PATH'));
  print('  scenes by WRS_ROW (' + label + ')', filtered.aggregate_histogram('WRS_ROW'));

  var composite = filtered.median().clip(aoi);
  var compBands = composite.bandNames().remove('QA_PIXEL');
  return composite.select(compBands);
}

// --- Build composites ---
// 2020: tight cloud filter, plenty of scenes available
var composite_2020 = buildComposite('2020-01-01', '2020-12-31', 25, '2020');
// Historical: extended window + relaxed cloud filter to maximize scene count
var composite_early = buildComposite('1984-01-01', '1988-12-31', 90, '1984-88');

var bands = composite_2020.bandNames();
print('bands to pass to classifier', bands);

// Visualization: SR reflectance scales to 0-1, typical land values 0.05-0.3
Map.addLayer(composite_2020,  {bands: ['red','green','blue'], min:0, max:0.3},
             'Median Composite 2020 (SR)');
Map.addLayer(composite_early, {bands: ['red','green','blue'], min:0, max:0.3},
             'Median Composite 1984-88 (SR)');

// =====================================================================
// Train RF on 2020 + 5-class reference
// =====================================================================

var samples = composite_2020
  .addBands(refLandCover)
  .stratifiedSample({
    numPoints: 300,
    classBand: 'class',
    region: aoi,
    scale: 30,
    projection: 'EPSG:3857',
    seed: 12,
    dropNulls: true,
    tileScale: 2,
    geometries: true
  })
  .randomColumn();

print('Sample size: ', samples.size());
print('Samples Breakdown', samples.aggregate_histogram('class'));

var training = samples.filter(ee.Filter.lte('random', 0.8));
var testing  = samples.filter(ee.Filter.gt('random', 0.8));
print('training size: ', training.size());
print('testing size: ', testing.size());

var classifier = ee.Classifier.smileRandomForest({numberOfTrees: 500})
  .train({
    features: training,
    classProperty: 'class',
    inputProperties: bands
  });

var classified_2020 = composite_2020.clip(aoi).select(bands).classify(classifier);
Map.addLayer(classified_2020, lcViz5, 'Classified 2020 (v3, 5-class SR)');

print('RF accuracy [Training Set]: ', classifier.confusionMatrix().accuracy());

var classificationVal = testing.classify(classifier);
var confusionMatrix = classificationVal.errorMatrix({
  actual: 'class',
  predicted: 'classification'
});
print('Confusion matrix [Testing Set]:', confusionMatrix);
print('Overall Accuracy [Testing Set]:', confusionMatrix.accuracy());
print('Producers Accuracy [Testing Set]:', confusionMatrix.producersAccuracy());
print('Users Accuracy [Testing Set]:', confusionMatrix.consumersAccuracy());

// =====================================================================
// Apply same classifier to historical composite + change products
// =====================================================================

var classified_early = composite_early.clip(aoi).select(bands).classify(classifier);
Map.addLayer(classified_early, lcViz5, 'Classified 1984-88 (v3, 5-class SR)');

// Binary change: 1 where class changed, 0 stable
var change = classified_early.neq(classified_2020).rename('change').selfMask();
Map.addLayer(change, {min:0, max:1, palette:['#000000','#ff0000']},
             'Change 1984-88 -> 2020');

// From-To: encoded transition (early * 10 + recent)
// With 5 classes, codes range 11 (Ag→Ag) to 55 (Bare→Bare).
// Tourism-relevant transitions:
//   12 = Ag → Natural Veg     (abandonment / golf conversion masked)
//   13 = Ag → Urban           (sprawl onto cropland)
//   23 = Natural Veg → Urban  (clearing for development)
//   21 = Natural Veg → Ag     (rare)
//   31 = Urban → Ag (rare)
var changeFromTo = classified_early.multiply(10).add(classified_2020).rename('fromto');
Map.addLayer(changeFromTo, {min:11, max:55}, 'From-To 1984-88 -> 2020', false);

// =====================================================================
// Exports
// =====================================================================

Export.image.toDrive({
  image: composite_2020.toFloat(),
  description: 'ToDrive_LandsatComposite_2020_SR',
  fileNamePrefix: 'LandsatComposite_2020_SR',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: composite_early.toFloat(),
  description: 'ToDrive_LandsatComposite_1984_1988_SR',
  fileNamePrefix: 'LandsatComposite_1984_1988_SR',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: classified_2020.toByte(),
  description: 'ToDrive_Classified_2020_v3',
  fileNamePrefix: 'Classified_2020_v3',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: classified_early.toByte(),
  description: 'ToDrive_Classified_1984_1988_v3',
  fileNamePrefix: 'Classified_1984_1988_v3',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: change.toByte(),
  description: 'ToDrive_Change_1984_88_to_2020_v3',
  fileNamePrefix: 'Change_1984_88_to_2020_v3',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: changeFromTo.toByte(),
  description: 'ToDrive_FromTo_1984_88_to_2020_v3',
  fileNamePrefix: 'FromTo_1984_88_to_2020_v3',
  region: aoi, scale: 30, maxPixels: 1e13
});
