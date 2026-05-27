// =====================================================================
// Barbados Land Cover Mapping — Tutorial Part 1
// Current composite: 2020-01-01 to 2020-12-31
// Source: https://servir-amazonia.github.io/barbados-training/landcover-mapping-gee/step-through-1.html
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

// --- Step 3: Preprocess Landsat Collections ---
var startdate = '2020-01-01';
var enddate   = '2020-12-31';
var dateFilter = ee.Filter.date(startdate,enddate);
var metadataCloudCoverMax = 25;

var sensorBandDictLandsatTOA = {'L9': [1, 2, 3, 4, 5, 9, 6, 11],
                                'L8': [1, 2, 3, 4, 5, 9, 6, 11],
                                'L7': [0, 1, 2, 3, 4, 5, 7, 9],
                                'L5': [0, 1, 2, 3, 4, 5, 6, 7]};
var bandNamesLandsatTOA = ['blue', 'green', 'red', 'nir', 'swir1',
                           'temp', 'swir2', 'QA_PIXEL'];

var lt5 = ee.ImageCollection('LANDSAT/LT05/C02/T1_TOA')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', metadataCloudCoverMax))
    .select(sensorBandDictLandsatTOA['L5'], bandNamesLandsatTOA);

var le7 = ee.ImageCollection('LANDSAT/LE07/C02/T1_TOA')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', metadataCloudCoverMax))
    .select(sensorBandDictLandsatTOA['L7'], bandNamesLandsatTOA);

var lc8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_TOA')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', metadataCloudCoverMax))
    .select(sensorBandDictLandsatTOA['L8'], bandNamesLandsatTOA);

var lc9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_TOA')
    .filterBounds(aoi)
    .filter(ee.Filter.lt('CLOUD_COVER', metadataCloudCoverMax))
    .select(sensorBandDictLandsatTOA['L9'], bandNamesLandsatTOA);

// --- Step 4: Cloud Masking Function ---
function cloudShadowMask(image) {
  var cloudShadowBitMask = (1 << 4);
  var cloudsBitMask = (1 << 3);
  var qa = image.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0)
                .and(qa.bitwiseAnd(cloudsBitMask).eq(0));
  return ee.Image(image).updateMask(mask);
}

// --- Step 5: Calculate Spectral Indices ---
function calculateIndices(img){
  var ndvi = img.normalizedDifference(['nir', 'red']).rename('ndvi');
  var lswi = img.normalizedDifference(['nir', 'swir1']).rename('lswi');
  var ndmi = img.normalizedDifference(['swir2', 'red']).rename('ndmi');
  var mndwi = img.normalizedDifference(['green', 'swir2']).rename('mndwi');
  return img.addBands(ndvi).addBands(lswi).addBands(ndmi).addBands(mndwi);
}

var lt5_preprocessed = lt5.map(cloudShadowMask).map(calculateIndices);
var le7_preprocessed = le7.map(cloudShadowMask).map(calculateIndices);
var lc8_preprocessed = lc8.map(cloudShadowMask).map(calculateIndices);
var lc9_preprocessed = lc9.map(cloudShadowMask).map(calculateIndices);

// --- Step 6: Merge Collections ---
var mergedLandsat = lt5_preprocessed
.merge(le7_preprocessed)
.merge(lc8_preprocessed)
.merge(lc9_preprocessed);

var landsatFiltered = mergedLandsat.filter(dateFilter);
print('processed Landsat Collection (2020)', landsatFiltered);

// --- Step 7: Create Composite ---
var composite = landsatFiltered.median().clip(aoi);
var bands = composite.bandNames().remove('QA_PIXEL');
composite = composite.select(bands);
print('bands to pass to classifier', composite.bandNames());

var visParamPreProcessed = {bands: ['red', 'green', 'blue'], min: 0, max: 0.2};
Map.addLayer(composite, visParamPreProcessed, 'Median Composite 2020');

// --- Step 8: Export ---
Export.image.toDrive({
  image: composite.toFloat(),
  description: 'ToDrive_LandsatComposite_2020',
  fileNamePrefix: 'LandsatComposite_2020',
  region: aoi,
  scale: 30,
  maxPixels: 1e13
});
