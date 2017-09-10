from spaceNetUtilities import geoToolsGPD as gT
import json
import os
import subprocess
import geopandas as gpd
from geopandas.geoseries import Polygon
import geopandas_osm
import osmnx as ox
import rasterio
import shapely.wkt
import pandas as pd



def returnBoundBoxM(tmpGeom, metersRadius=50):
    poly = gT.createPolygonFromCenterPoint(tmpGeom.GetX(), tmpGeom.GetY(),
                                    metersRadius)

    polyEnv = poly.envelope

    return polyEnv

def createPolygonShapeFileFromOSM(polyBounds, pointOfInterestList, outVectorFile='', debug=True):

    gdfOSM = gpd.GeoDataFrame([])
    for pointOfInterestKey in pointOfInterestList.keys():
        gdfPOITemp = geopandas_osm.osm.query_osm('way', polyBounds, recurse='down',
                                                 tags='{}'.format(pointOfInterestKey))

        gdfOSM.append(gdfPOITemp)

        gdfPOITemp = geopandas_osm.osm.query_osm('node', polyBounds, recurse='down',
                                                 tags='{}'.format(pointOfInterestKey))

        gdfOSM.append(gdfPOITemp)

    gdfOSM.drop_duplicates(subset=['id'], keep='first', inplace=True)

    ## convert closed LineStrings to Polygon
    geomList = []
    for geom in gdfOSM.geometry.values:
        if geom.is_closed & geom.geom_type == "LineString":
           geom = Polygon(geom)
        else:
           geom
        geomList.append(geom)

    gdfOSM.geometry = geomList

    gdfOSM = gdfOSM[(gdfOSM.geom_type=='Point') or (gdfOSM.geom_type=='Polygon')]
    ##

    gdfFinal = createPolygonShapeFileGPD(pointOfInterestList, gdfOSM, outVectorFile=outVectorFile)

    return gdfFinal


def createPolygonShapeFileFromShapefile(srcVectorFile, pointOfInterestList, outVectorFile=''):

    gdfOrig = gpd.read_file(srcVectorFile)
    gdfFinal = createPolygonShapeFileGPD(pointOfInterestList, gdfOrig, outVectorFile=outVectorFile)

    return gdfFinal



def createPolygonShapeFileGPD(pointOfInterestList, gdfOrig, outVectorFile=''):

    ## todo add support for polygons in addition to points
    firstKey = True
    ## Iterage through keys for valid points of interest, These correspond to OSM Tags such as Power or Places.
    for pointOfInterestKey in pointOfInterestList.keys():
        ## Select from Vector File all rows where Point of Interest Columns is not an empty String
        gdfKey = gdfOrig[gdfOrig[pointOfInterestKey] != '']

        # Get list of defined features in the set Tag List, i.e. power=objectName

        objectNameList = pointOfInterestList[pointOfInterestKey].keys()

        # iterate through object names to apply specific actions with regard to the object like bounding box size.

        for objectName in objectNameList:
            # select only those objects where the key=object i.e power=tower
            gdfPOITemp = gdfKey[gdfKey[pointOfInterestKey] == objectName]

            if gdfPOITemp.size>0:
                utm_crs, latlong_crs = gT.createUTMandLatLonCrs(gdfPOITemp.geometry.values[0])
               # "compensator": {
               #                    "featureIdNum": 1,
               #                    "featureChipScaleM": 200,
               #                    "featureBBoxSizeM": 5
               #                },
                # project subset to UTM so that actions can be done with regard to meters
                gdfPOITempUTM = gdfPOITemp.to_crs(utm_crs)
                # buffer geometry to create circle around point with x meters
                gdfPOITempUTM.geometry=gdfPOITempUTM.buffer(pointOfInterestList[pointOfInterestKey][objectName]['featureBBoxSizeM'])
                # calculate the envelope of the circle to create a bounding box for each object
                gdfPOITempUTM.geometry=gdfPOITempUTM.envelope

                # reporject to wgs84 (lat long)
                gdfPOITemp = gdfPOITempUTM.to_crs(latlong_crs)
                # assign a name to spacefeat for future use in the vector: "power:tower"
                gdfPOITemp['spacefeat']=pointOfInterestList[pointOfInterestKey][objectName]['spaceFeatureName']

            # if first key, create final gdf
                if firstKey:
                    gdfFinal = gdfPOITemp
                    firstKey = False
                else:
                    # else add new to end of gdfFinal
                    gdfFinal = gdfFinal.concat(gdfPOITemp)

    if outVectorFile != '':
        gdfFinal.to_file(outVectorFile)

    return gdfFinal


def createProcessedPOIDataGPD(srcVectorFile, pointOfInterestList, rasterFileList, shapeFileSrcList,
                           baseName='',
                           className='',
                           outputDirectory='',
                           seperateImageFolders=False,
                           minPartialToInclue = 0.70,
                           defaultfeatureChipScaleM=200,
                              verbose=False
                           ):

    fieldName = pointOfInterestList.keys()[0]
    fieldOfInterestList = pointOfInterestList[fieldName]
    chipSummaryList = []


    ## determinePixelSize in Meters
    if verbose:
        print(rasterFileList)
        print(rasterFileList[0][0])

    with rasterio.open(rasterFileList[0][0]) as src:
        geoTransform = src.affine.to_gdal()

    metersPerPix = abs(round(geoTransform[5]*111111,1))

    ## process pointShapeFile
    srcDf = gpd.read_file(srcVectorFile)

    ## check if fieldName is valid otherwise features are detectable:
    if fieldName in srcDf.columns:
        print("{} is detected, processing srcFile = {}".format(fieldName, srcVectorFile))
    else:
        print("Error {} is not a valid column Name, unable to process srcFile = {}".format(fieldName, srcVectorFile))
        print("Error Field name= {} is not in column names = {}". format(fieldName, srcDf.columns))
        print("Ensure {} is a column name, unable to process srcFile = {}".format(fieldName, srcVectorFile))

        return -1

    utm_crs, latlong_crs = gT.createUTMandLatLonCrs(srcDf.centroid.values[0])

    ## not sure if needed
    #gdf_utm = srcDf.to_crs(utm_crs)
    #halfClipSizeXm = round((clipSizeM/metersPerPix)/2)
    #gdf_utm.buffer(halfClipSizeXm).envelope




    imgId = 0
    for idx, feature in srcDf.iterrows():

        geom = feature.geometry.centroid


        featureName = feature[fieldName]

        if seperateImageFolders:
            className = featureName.replace(' ', '')
        else:
            className = ''
        if featureName in fieldOfInterestList.keys():
            clipSize = fieldOfInterestList[featureName]['featureChipScaleM']
        else:
            clipSize = defaultfeatureChipScaleM


        halfClipSizeXm = round((clipSize/metersPerPix)/2)


        maxXCut = geom.x + halfClipSizeXm*geoTransform[1]
        maxYCut = geom.y + abs(halfClipSizeXm*geoTransform[5])
        minYCut = geom.y - abs(halfClipSizeXm*geoTransform[5])
        minXCut = geom.x - halfClipSizeXm*geoTransform[1]

        imgId = imgId + 1

        chipSummary = gT.createclip(outputDirectory, rasterFileList, shapeFileSrcList,
                       maxXCut, maxYCut, minYCut, minXCut,
                       rasterFileBaseList=[],
                       minpartialPerc=minPartialToInclue,
                       outputPrefix='',
                       createPix=False,
                       rasterPolyEnvelope=shapely.wkt.loads('POLYGON EMPTY'),
                       className=className,
                       baseName=baseName,
                       imgId=imgId)

        chipSummaryList.append(chipSummary)

    return chipSummaryList


def splitVectorFile(geoJson, latCutOff=-500, lonCutOff=-500):


    longMin = -500
    latMin = -500
    if latCutOff == -500:
        latMax = 500
    else:
        latMax = latCutOff

    if lonCutOff == -500:
        longMax = 500
    else:
        longMax = lonCutOff


    outputGeoJsonTrain = geoJson.replace('.geojson', 'train.geojson')
    cmd = ['ogr2ogr', '-f', "GeoJSON", outputGeoJsonTrain, geoJson,
           '-clipsrc', '{}'.format(longMin), '{}'.format(latMin), '{}'.format(longMax), '{}'.format(latMax)]

    subprocess.call(cmd)
    longMin = -500
    latMin = -500
    if latCutOff == -500:
        latMax = 500
    else:
        latMin = latCutOff
        latMax = 500


    if lonCutOff == -500:
        longMax = 500
    else:
        longMin = lonCutOff
        longMax = 500

    outputGeoJsonTest = geoJson.replace('.geojson', 'test.geojson')
    cmd = ['ogr2ogr', '-f', "GeoJSON", outputGeoJsonTest, geoJson,
           '-clipsrc', '{}'.format(longMin), '{}'.format(latMin), '{}'.format(longMax), '{}'.format(latMax)]
    subprocess.call(cmd)


    return outputGeoJsonTrain, outputGeoJsonTest

def deduplicateGeoJson(geoJsonIn, geoJsonOut='', encoding='UTF-8'):


    df = gpd.read_file(geoJsonIn, encoding=encoding)
    df['y'] = df.geometry.map(lambda p: p.y)
    df['x'] = df.geometry.map(lambda p: p.x)
    df.drop_duplicates(subset=['spaceNetFeature', 'x', 'y'], keep='first', inplace=True)
    df.drop(['x', 'y'], 1, inplace=True)

    if geoJsonOut=='':
        geoJsonOut = geoJsonIn.replace('.geojson', 'dedup.geojson')
    df.to_file(geoJsonOut, driver='GeoJSON', encoding=encoding)

    return geoJsonOut

def splitVectorFileGPD(geoJson, latMin, latMax, lonMin, lonMax, encoding='UTF-8'):

    insidePoly = Polygon([(lonMin, latMin), (lonMin, latMax), (lonMax, latMax), (lonMax, latMin)])
    df = gpd.read_file(geoJson, encoding=encoding)

    outputGeoJsonTrain = geoJson.replace('.geojson', 'train.geojson')
    df[~df.intersects(insidePoly)].to_file(outputGeoJsonTrain, driver='GeoJSON', encoding=encoding)

    outputGeoJsonTest = geoJson.replace('.geojson', 'test.geojson')
    df[df.intersects(insidePoly)].to_file(outputGeoJsonTest, driver='GeoJSON', encoding=encoding)

    return outputGeoJsonTrain, outputGeoJsonTest




def processPointShapeFile():

    pass



if __name__ == '__main__':

    createOutVectorFile = True
    srcVectorFile = '/path/To/PointOfInterestSummary.geojson'
    outVectorFile = '/path/To/PolygonOfInterestSummary.geojson'
    outputDirectory = '/path/To/processedDataPOI/'
    baseName = 'AOI_3_Paris'
    featureDescriptionJson = '../configFiles/OSM_Power.json'
    className = 'POIAll'
    seperateImageFolders = True
    splitGeoJson = False




    srcVectorFileList = [[srcVectorFile, 'all']]

    # List of Raster Images to Chip and an appropriate label.
    # This list will take any type of Raster supported by GDAL
    # VRTs are nice becasuse they create a virtual mosaic and allow for images covering a wide area to be considered one
    # In this case gdalbuildvrt can be run in a folder of tifs to create the VRT to be handed for processing
    rasterFileList = [['/path/To/Pan-VRT.vrt', 'PAN'],
                      ['/path/To/MUL-VRT.vrt', 'MUL']
                      ['/path/To/RGB-PanSharpen-VRT.vrt', 'RGB-PanSharpen']
                      ['/path/To/MUL-PanSharpen-VRT.vrt', 'MUL-PanSharpen']
                      ]




    ### Define Point of Interest Dictionary
    # {'spacenetFeatureName':
    #   {'featureIdNum': '1', # iterative feature id. Used for object name to class number mapping
    #    'featureChipScaleM': 200, # Size of chip to create in meters
    #    'featureBBoxSizeM': 10 # Feature Bounding Box Assumption.  Code will draw an x meter bounding box around the point
    #                           # indicating in the geojson.  This will be used in creating polygons for IOU scoring
    #    }

    with open(featureDescriptionJson, 'r') as j:
        pointOfInterestList = json.load(j)


    # create Folder Structure to place files into.

    for rasterFile in rasterFileList:
        for keyName in pointOfInterestList.keys():
            tmpPath = os.path.join(outputDirectory, rasterFile[1], keyName.replace(' ', ''))
            if not os.path.exists(tmpPath):
                os.makedirs(tmpPath)

            for objectName in pointOfInterestList[keyName].keys():
                tmpPath = os.path.join(outputDirectory, rasterFile[1], keyName.replace(' ', ''), objectName.replace(" ",""))
                if not os.path.exists(tmpPath):
                    os.makedirs(tmpPath)

        # create Processed Point of Interest Data.
    createProcessedPOIDataGPD(srcVectorFile, pointOfInterestList, rasterFileList, srcVectorFileList,
                               baseName=baseName,
                               className='',
                               outputDirectory=outputDirectory,
                               seperateImageFolders=seperateImageFolders,
                               minPartialToInclue=0.70)





