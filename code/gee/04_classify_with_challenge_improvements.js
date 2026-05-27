// =====================================================================
// Barbados Land Cover — Challenge improvements applied
// Source: https://servir-amazonia.github.io/barbados-training/landcover-mapping-gee/challenge.html
//
// Same workflow as 03_classify_and_change.js, but with the model-robustness
// changes suggested on the challenge page:
//   - Per-class sample count raised from 100 to 300 (challenge suggests 200-500)
//   - Random Forest tree count raised from 100 to 500
// Date range (1984-86 vs 2020) is already a challenge-style modification.
// =====================================================================

// --- AOI ---
var countryName = 'Barbados';
var countries = ee.FeatureCollection("FAO/GAUL/2015/level0");
var aoi = countries.filter(ee.Filter.eq('ADM0_NAME', countryName));
Map.addLayer(aoi, {}, 'AOI', false);
Map.centerObject(aoi, 12);

// --- Reference land cover ---
var refLandCover = ee.Image("projects/caribbean-trainings/assets/barbados-2022/images/CopernicusLC_8Class")
  .selfMask();
var lcViz = {min:1, max:8, palette:['#f096ff','#b4b4b4','#ffff4c','#007800',
                                    '#ffbb22','#fa0000','#0032c8','#0096a0']};
Map.addLayer(refLandCover, lcViz, 'Copernicus 8 Class Landcover');

// --- Band dictionaries + functions ---
var sensorBandDictLandsatTOA = {'L9': [1, 2, 3, 4, 5, 9, 6, 11],
                                'L8': [1, 2, 3, 4, 5, 9, 6, 11],
                                'L7': [0, 1, 2, 3, 4, 5, 7, 9],
                                'L5': [0, 1, 2, 3, 4, 5, 6, 7]};
var bandNamesLandsatTOA = ['blue', 'green', 'red', 'nir', 'swir1',
                           'temp', 'swir2', 'QA_PIXEL'];

function cloudShadowMask(image) {
  var cloudShadowBitMask = (1 << 4);
  var cloudsBitMask = (1 << 3);
  var qa = image.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0)
              .and(qa.bitwiseAnd(cloudsBitMask).eq(0));
  return ee.Image(image).updateMask(mask);
}

function calculateIndices(img){
  var ndvi = img.normalizedDifference(['nir', 'red']).rename('ndvi');
  var lswi = img.normalizedDifference(['nir', 'swir1']).rename('lswi');
  var ndmi = img.normalizedDifference(['swir2', 'red']).rename('ndmi');
  var mndwi = img.normalizedDifference(['green', 'swir2']).rename('mndwi');
  return img.addBands(ndvi).addBands(lswi).addBands(ndmi).addBands(mndwi);
}

function buildComposite(startdate, enddate, cloudMax, label) {
  var dateFilter = ee.Filter.date(startdate, enddate);

  var lt5 = ee.ImageCollection('LANDSAT/LT05/C02/T1_TOA')
      .filterBounds(aoi)
      .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
      .select(sensorBandDictLandsatTOA['L5'], bandNamesLandsatTOA);
  var le7 = ee.ImageCollection('LANDSAT/LE07/C02/T1_TOA')
      .filterBounds(aoi)
      .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
      .select(sensorBandDictLandsatTOA['L7'], bandNamesLandsatTOA);
  var lc8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_TOA')
      .filterBounds(aoi)
      .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
      .select(sensorBandDictLandsatTOA['L8'], bandNamesLandsatTOA);
  var lc9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_TOA')
      .filterBounds(aoi)
      .filter(ee.Filter.lt('CLOUD_COVER', cloudMax))
      .select(sensorBandDictLandsatTOA['L9'], bandNamesLandsatTOA);

  var merged = lt5.map(cloudShadowMask).map(calculateIndices)
    .merge(le7.map(cloudShadowMask).map(calculateIndices))
    .merge(lc8.map(cloudShadowMask).map(calculateIndices))
    .merge(lc9.map(cloudShadowMask).map(calculateIndices));

  var filtered = merged.filter(dateFilter);
  print('processed Landsat Collection (' + label + ')', filtered);
  print('  scene count (' + label + ')', filtered.size());

  var composite = filtered.median().clip(aoi);
  var bands = composite.bandNames().remove('QA_PIXEL');
  return composite.select(bands);
}

var composite_2020 = buildComposite('2020-01-01', '2020-12-31', 25, '2020');
var composite_early = buildComposite('1984-01-01', '1986-12-31', 60, '1984-86');

var bands = composite_2020.bandNames();
print('bands to pass to classifier', bands);

Map.addLayer(composite_2020, {bands: ['red','green','blue'], min:0, max:0.2}, 'Median Composite 2020');
Map.addLayer(composite_early, {bands: ['red','green','blue'], min:0, max:0.2}, 'Median Composite 1984-86');

// --- Challenge change #1: more samples per class (100 -> 300) ---
var label = 'class';
var samples = composite_2020
  .addBands(refLandCover)
  .stratifiedSample({
    numPoints: 300,           // challenge.html: try 200-500 per class
    classBand: label,
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
print('Samples Breakdown', samples.aggregate_histogram(label));

var training = samples.filter(ee.Filter.lte('random', 0.8));
var testing  = samples.filter(ee.Filter.gt('random', 0.8));
print('training size: ', training.size());
print('testing size: ', testing.size());

// --- Challenge change #2: more trees (100 -> 500) ---
var classifier = ee.Classifier.smileRandomForest({
    numberOfTrees: 500        // challenge.html: try more trees
  })
  .train({
    features: training,
    classProperty: label,
    inputProperties: bands
  });

// Classify 2020
var classified_2020 = composite_2020.clip(aoi).select(bands).classify(classifier);
Map.addLayer(classified_2020, lcViz, 'classified 2020 (improved)');

// Training & testing accuracy
print('RF error matrix [Training Set]: ', classifier.confusionMatrix());
print('RF accuracy [Training Set]: ', classifier.confusionMatrix().accuracy());

var classificationVal = testing.classify(classifier);
var confusionMatrix = classificationVal.errorMatrix({
  actual: label,
  predicted: 'classification'
});
print('Confusion matrix [Testing Set]:', confusionMatrix);
print('Overall Accuracy [Testing Set]:', confusionMatrix.accuracy());
print('Producers Accuracy [Testing Set]:', confusionMatrix.producersAccuracy());
print('Users Accuracy [Testing Set]:', confusionMatrix.consumersAccuracy());

// Apply same classifier to 1984-86 + change map (extension, same as script 03)
var classified_early = composite_early.clip(aoi).select(bands).classify(classifier);
Map.addLayer(classified_early, lcViz, 'classified 1984-86 (improved)');

var change = classified_early.neq(classified_2020).rename('change').selfMask();
Map.addLayer(change, {min:0, max:1, palette:['#000000','#ff0000']}, 'Change 1984-86 -> 2020 (improved)');

var changeFromTo = classified_early.multiply(10).add(classified_2020).rename('fromto');
Map.addLayer(changeFromTo, {min:11, max:88}, 'From-To 1984-86 -> 2020 (improved)', false);

// Exports
Export.image.toDrive({
  image: classified_2020.toByte(),
  description: 'ToDrive_Classified_2020_v2',
  fileNamePrefix: 'Classified_2020_v2',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: classified_early.toByte(),
  description: 'ToDrive_Classified_1984_1986_v2',
  fileNamePrefix: 'Classified_1984_1986_v2',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: change.toByte(),
  description: 'ToDrive_Change_1984_to_2020_v2',
  fileNamePrefix: 'Change_1984_to_2020_v2',
  region: aoi, scale: 30, maxPixels: 1e13
});
Export.image.toDrive({
  image: changeFromTo.toByte(),
  description: 'ToDrive_FromTo_1984_to_2020_v2',
  fileNamePrefix: 'FromTo_1984_to_2020_v2',
  region: aoi, scale: 30, maxPixels: 1e13
});
