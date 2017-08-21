from osgeo import ogr, gdal, osr
from spaceNetUtilities import geoToolsGPD as gT
import json
import os
import subprocess
import geopandas as gpd
from geopandas.geoseries import Polygon
import geopandas_osm

def returnBoundBoxM(tmpGeom, metersRadius=50):
    poly = gT.createPolygonFromCenterPoint(tmpGeom.GetX(), tmpGeom.GetY(),
                                    metersRadius)

    polyEnv = poly.envelope




    return polyEnv
def createPolygonShapeFileFromOSM(polyBounds, pointOfInterestList, outVectorFile='', debug=True):
    gdfOSM = gpd.GeoDataFrame([])
    for pointOfInterestKey in pointOfInterestList.keys():
        gdfPOITemp = geopandas_osm.osm.query_osm('way', polyBounds, recurse='down', tags='{}'.format(pointOfInterestKey))
        gdfOSM = gdfOSM.concat(gdfPOITemp)

    gdfFinal = createPolygonShapeFileGPD(pointOfInterestList, gdfOSM, outVectorFile=outVectorFile)

    return gdfFinal


def createPolygonShapeFileFromShapefile(srcVectorFile, pointOfInterestList, outVectorFile=''):

    gdfOrig = gpd.read_file(srcVectorFile)
    gdfFinal = createPolygonShapeFileGPD(pointOfInterestList, gdfOrig, outVectorFile=outVectorFile)

    return gdfFinal



def createPolygonShapeFileGPD(pointOfInterestList, gdfOrig, outVectorFile=''):

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

           # "compensator": {
           #                    "featureIdNum": 1,
           #                    "featureChipScaleM": 200,
           #                    "featureBBoxSizeM": 5
           #                },
            # project subset to UTM so that actions can be done with regard to meters
            gdfPOITempUTM = ox.project_gdf(gdfPOITemp)
            # buffer geometry to create circle around point with x meters
            gdfPOITempUTM.geometry=gdfPOITempUTM.buffer(pointOfInterestList[pointOfInterestKey][objectName]['featureBBoxSizeM'])
            # calculate the envelope of the circle to create a bounding box for each object
            gdfPOITempUTM.geometry=gdfPOITempUTM.envelope

            # reporject to wgs84 (lat long)
            gdfPOITemp = ox.project_gdf(gdfPOITempUTM, to_latlong=True)
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

def createPolygonShapeFile(srcVectorFile, outVectorFile, pointOfInterestList):

    ## Turn Point File into PolygonFile


    srcDS = ogr.Open(srcVectorFile, 0)
    inLayer = srcDS.GetLayer()
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    outDriver = ogr.GetDriverByName("GeoJSON")
    if os.path.exists(outVectorFile):
        outDriver.DeleteDataSource(outVectorFile)

    dstDS = outDriver.CreateDataSource(outVectorFile)

    outLayer = dstDS.CreateLayer('polygons', srs, geom_type=ogr.wkbPolygon)

    # Get Attribute names
    inLayerDefn = inLayer.GetLayerDefn()
    for i in range(0, inLayerDefn.GetFieldCount()):
        fieldDefn = inLayerDefn.GetFieldDefn(i)
        outLayer.CreateField(fieldDefn)

    outLayerDefn = outLayer.GetLayerDefn()

    # Copy Features
    for i in range(0, inLayer.GetFeatureCount()):

        inFeature = inLayer.GetFeature(i)
        outFeature = ogr.Feature(outLayerDefn)
        for i in range(0, outLayerDefn.GetFieldCount()):
            outFeature.SetField(outLayerDefn.GetFieldDefn(i).GetNameRef(), inFeature.GetField(i))
        # Set geometry as centroid
        tmpGeom = inFeature.GetGeometryRef()
        poly = returnBoundBoxM(tmpGeom, metersRadius=pointOfInterestList[inFeature.GetField('spaceNetFeature')]['featureBBoxSizeM'])

        outFeature.SetGeometry(poly)

        outLayer.CreateFeature(outFeature)
        outFeature = None
        inFeature = None

    srcDS = None
    dstDS = None

def createProcessedPOIData(srcVectorFile, pointOfInterestList, rasterFileList, shapeFileSrcList,
                           baseName='',
                           className='',
                           outputDirectory='',
                           seperateImageFolders=False,
                           minPartialToInclue = 0.70,
                           fieldName='spacefeat'):


    chipSummaryList = []
    srcDS = srcDS = ogr.Open(srcVectorFile, 0)
    srcLayer = srcDS.GetLayer()


    shapeSrcList = []
    for shapeFileSrc in shapeFileSrcList:
        print(shapeFileSrc[1])
        shapeSrcList.append([ogr.Open(shapeFileSrc[0],0), shapeFileSrc[1]])

    ## determinePixelSize in Meters
    print rasterFileList
    print rasterFileList[0][0]
    srcRaster = gdal.Open(rasterFileList[0][0])
    geoTransform = srcRaster.GetGeoTransform()
    metersPerPix = abs(round(geoTransform[5]*111111,1))

    imgId = 0
    for feature in srcLayer:

        geom = feature.GetGeometryRef()

        if geom.GetGeometryName != 'POINT':
            geom = geom.Centroid()


        spacenetFeatureName = feature.GetField('spaceNetFeature')
        if seperateImageFolders:
            className = spacenetFeatureName.replace(' ', '')
        else:
            className = ''
        clipSize = pointOfInterestList[spacenetFeatureName]['featureChipScaleM']
        halfClipSizeXm = round((clipSize/metersPerPix)/2)

        xCenter = geom.GetX()
        yCenter = geom.GetY()

        maxXCut = xCenter + halfClipSizeXm*geoTransform[1]
        maxYCut = yCenter + abs(halfClipSizeXm*geoTransform[5])
        minYCut = yCenter - abs(halfClipSizeXm*geoTransform[5])
        minXCut = xCenter - halfClipSizeXm*geoTransform[1]

        imgId = imgId + 1

        chipSummary = gT.createclip(outputDirectory, rasterFileList, shapeSrcList,
                       maxXCut, maxYCut, minYCut, minXCut,
                       rasterFileBaseList=[],
                       minpartialPerc=minPartialToInclue,
                       outputPrefix='',
                       createPix=False,
                       rasterPolyEnvelope=ogr.CreateGeometryFromWkt("POLYGON EMPTY"),
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








if __name__ == '__main__':

    createOutVectorFile = True
    srcVectorFile = '/path/To/PointOfInterestSummary.geojson'
    outVectorFile = '/path/To/PolygonOfInterestSummary.geojson'
    outputDirectory = '/path/To/processedDataPOI/'
    baseName = 'AOI_3_Paris'
    featureDescriptionJson = '../configFiles/OSM_Power.json'
    className = 'POIAll'
    seperateImageFolders = False
    splitGeoJson = False
    deduplicateGeoJsonFlag = True

    if deduplicateGeoJsonFlag:
        srcVectorFile = deduplicateGeoJson(srcVectorFile)

    splitGeoJson_latMin = -22.94
    splitGeoJson_latMax = 90
    splitGeoJson_lonMin = -43.25
    splitGeoJson_lonMax = 180

    srcVectorFileList = [[srcVectorFile, 'all']]

    #if splitGeoJson:
    #    srcVectorTrain, srcVectorTest = splitVectorFileGPD(srcVectorFile,
    #                                                    latMin=splitGeoJson_latMin,
    #                                                    latMax=splitGeoJson_latMax,
    #                                                    lonMin=splitGeoJson_lonMin,
    #                                                    lonMax=splitGeoJson_lonMax,
    #                                                    )

    #    srcVectorFileList = [
    #                        [srcVectorTrain, 'train'],
    #                        [srcVectorTest, 'test']
    #                        ]





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

    # create Polygon of Interet from Point of Interest File.  This will create bounding boxes of specified size.
    for srcVectorFile, folderType in srcVectorFileList:
        outVectorFile = srcVectorFile.replace('.geojson', 'poly.shp')
        if createOutVectorFile:
            createPolygonShapeFileGPD(srcVectorFile, pointOfInterestList, outVectorFile=outVectorFile)

        outputDirectoryTmp = os.path.join(outputDirectory, folderType)

        shapeFileSrcList = [
            [outVectorFile, 'POIAll']
        ]
    # create Folder Structure to place files into.

        for rasterFile in rasterFileList:
            for keyName in pointOfInterestList.keys():
                tmpPath = os.path.join(outputDirectoryTmp, rasterFile[1], keyName.replace(' ', ''))
                if not os.path.exists(tmpPath):
                    os.makedirs(tmpPath)

                for objectName in pointOfInterestList[keyName].keys():
                    tmpPath = os.path.join(outputDirectoryTmp, rasterFile[1], keyName.replace(' ', ''), objectName.replace(" ",""))
                    if not os.path.exists(tmpPath):
                        os.makedirs(tmpPath)

        # create Processed Point of Interest Data.
        createProcessedPOIData(srcVectorFile, pointOfInterestList, rasterFileList, shapeFileSrcList,
                               baseName=baseName,
                               className='',
                               outputDirectory=outputDirectoryTmp,
                               seperateImageFolders=seperateImageFolders,
                               minPartialToInclue=0.70)





