// =====================================================================
// Barbados Land Cover Mapping — Tutorial Part 1 + Part 2 + Change
// Part 1: https://servir-amazonia.github.io/barbados-training/landcover-mapping-gee/step-through-1.html
// Part 2: https://servir-amazonia.github.io/barbados-training/landcover-mapping-gee/step-through-2.html
//
// This script:
//   1. Builds the 2020 Landsat median composite (Part 1)
//   2. Builds the 1984-86 Landsat median composite (Part 1, earliest era)
//   3. Generates stratified training samples from the 2020 composite +
//      Copernicus 8-class reference (Part 2)
//   4. Trains a Random Forest classifier (Part 2)
//   5. Classifies both composites with the SAME trained classifier
//   6. Computes a binary change map (class_1984_86 != class_2020)
//   7. Exports classified 2020, classified 1984-86, and change map to Drive
// =====================================================================

// --- Step 1: Define Area of Interest ---
var countryName = 'Barbados';
var countries = ee.FeatureCollection("FAO/GAUL/2015/level0");
var aoi = countries.filter(ee.Filter.eq('ADM0_NAME', countryName));
Map.addLayer(aoi,{},'AOI',false);
Map.centerObject(aoi,12);

// --- Step 2: Load Reference Land Cover Data ---
var refLandCover = ee.Image("projects/caribbean-trainings/assets/barbados-2022/images/CopernicusLC_8Class")
.selfMask();
var lcViz = {min:1,max:8,palette:['#f096ff','#b4b4b4','#ffff4c','#007800',
                                  '#ffbb22','#fa0000','#0032c8','#0096a0']};
Map.addLayer(refLandCover,lcViz,'Copernicus 8 Class Landcover');

// --- Step 3: Landsat band dictionaries + cloud / index functions (Part 1) ---
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

// Helper: build a Landsat composite for a given date range + cloud threshold
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

// --- Build both composites ---
var composite_2020 = buildComposite('2020-01-01', '2020-12-31', 25, '2020');
var composite_early = buildComposite('1984-01-01', '1986-12-31', 60, '1984-86');

var bands = composite_2020.bandNames();
print('bands to pass to classifier', bands);

var visParamPreProcessed = {bands: ['red', 'green', 'blue'], min: 0, max: 0.2};
Map.addLayer(composite_2020, visParamPreProcessed, 'Median Composite 2020');
Map.addLayer(composite_early, visParamPreProcessed, 'Median Composite 1984-86');

// =====================================================================
// PART 2 — Train Random Forest on 2020 composite + Copernicus reference
// =====================================================================

// --- Create reference sample points for model training and testing ---
var label = 'class'; // our Y variable - or the variable we want to classify
var samples = composite_2020
.addBands(refLandCover)            // stack land cover img with predictor bands
.stratifiedSample({                // create a stratified random sample of points
  numPoints:100,
  classBand:label,
  region:aoi,
  scale:30,
  projection:'EPSG:3857',
  seed:12,
  // classValues:[1,2,3,4],         // these override numPoints if defined
  // classPoints:[100,100,50,50],
  dropNulls:true,
  tileScale:2,
  geometries:true})
  .randomColumn();                 // create a random value property

print('Sample size: ', samples.size());
print('First sample', samples.first());
print('Samples Breakdown', samples.aggregate_histogram(label));

// --- Split sample data into training and testing ---
var training = samples.filter(ee.Filter.lte('random', 0.8));
var testing  = samples.filter(ee.Filter.gt('random', 0.8));
print('training size: ', training.size());
print('testing size: ', testing.size());

// --- Train the classifier ---
var classifier = ee.Classifier.smileRandomForest({
  numberOfTrees:100})
  .train({
    features:training,
    classProperty: label,
    inputProperties:bands
  });

// --- Run the classification on 2020 composite ---
var classified_2020 = composite_2020.clip(aoi).select(bands).classify(classifier);
Map.addLayer(classified_2020, lcViz, 'classified 2020');

// =====================================================================
// PART 2 — Accuracy Assessment
// =====================================================================

// Training accuracy (optimistic — model has seen these points)
print('RF error matrix [Training Set]: ', classifier.confusionMatrix());
print('RF accuracy [Training Set]: ', classifier.confusionMatrix().accuracy());

// Testing accuracy (realistic)
var classificationVal = testing.classify(classifier);
print('Classified points', classificationVal.limit(5));

var confusionMatrix = classificationVal.errorMatrix({
  actual: label,
  predicted: 'classification'
});

print('Confusion matrix [Testing Set]:', confusionMatrix);
print('Overall Accuracy [Testing Set]:', confusionMatrix.accuracy());
print('Producers Accuracy [Testing Set]:', confusionMatrix.producersAccuracy());
print('Users Accuracy [Testing Set]:', confusionMatrix.consumersAccuracy());

// =====================================================================
// CHANGE EXTENSION — apply same classifier to 1984-86 + difference
// =====================================================================

// Apply the SAME trained classifier to the historical composite.
// Caveat: Landsat 5 TM has different spectral response than Landsat 8 OLI, so
// the historical map will be noisier than 2020. This is the standard approach
// when no historical ground-truth exists.
var classified_early = composite_early.clip(aoi).select(bands).classify(classifier);
Map.addLayer(classified_early, lcViz, 'classified 1984-86');

// Binary change: 1 where class changed between epochs, 0 where stable
var change = classified_early.neq(classified_2020).rename('change').selfMask();
Map.addLayer(change, {min:0, max:1, palette:['#000000','#ff0000']}, 'Change 1984-86 -> 2020');

// "From-to" change code: early_class * 10 + recent_class
// e.g. 47 = forest (4) in 1984-86 -> urban (6) in 2020? — codes match the
// Copernicus 8-class scheme (1 ag, 2 bare, 3 herb, 4 forest, 5 shrub, 6 urban, 7 water, 8 wetland)
var changeFromTo = classified_early.multiply(10).add(classified_2020).rename('fromto');
Map.addLayer(changeFromTo, {min:11, max:88}, 'From-To 1984-86 -> 2020', false);

// =====================================================================
// Exports
// =====================================================================

Export.image.toDrive({
  image: classified_2020.toByte(),
  description: 'ToDrive_Classified_2020',
  fileNamePrefix: 'Classified_2020',
  region: aoi,
  scale: 30,
  maxPixels: 1e13
});

Export.image.toDrive({
  image: classified_early.toByte(),
  description: 'ToDrive_Classified_1984_1986',
  fileNamePrefix: 'Classified_1984_1986',
  region: aoi,
  scale: 30,
  maxPixels: 1e13
});

Export.image.toDrive({
  image: change.toByte(),
  description: 'ToDrive_Change_1984_to_2020',
  fileNamePrefix: 'Change_1984_to_2020',
  region: aoi,
  scale: 30,
  maxPixels: 1e13
});

Export.image.toDrive({
  image: changeFromTo.toByte(),
  description: 'ToDrive_FromTo_1984_to_2020',
  fileNamePrefix: 'FromTo_1984_to_2020',
  region: aoi,
  scale: 30,
  maxPixels: 1e13
});
