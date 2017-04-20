from osgeo import ogr, gdal, osr
from spaceNetUtilities import geoTools as gT
import json
import os
import subprocess
import geopandas as gpd


def returnBoundBoxM(tmpGeom, metersRadius=50):
    poly = gT.createPolygonFromCenterPoint(tmpGeom.GetX(), tmpGeom.GetY(),
                                    metersRadius)

    polyEnv = gT.get_envelope(poly)




    return polyEnv



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
                           minPartialToInclue = 0.70
                           ):


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

if __name__ == '__main__':

    createOutVectorFile = True
    srcVectorFile = '/path/To/PointOfInterestSummary.geojson'
    outVectorFile = '/path/To/PolygonOfInterestSummary.geojson'
    outputDirectory = '/path/To/processedDataPOI/'
    className = 'POIAll'
    baseName = 'AOI_1_RIO'
    featureDescriptionJson = '../configFiles/AOI_1_Rio_POI_Description.json'
    seperateImageFolders = False
    splitGeoJson = True
    deduplicateGeoJsonFlag = True

    if deduplicateGeoJsonFlag:
        srcVectorFile = deduplicateGeoJson(srcVectorFile)

    splitGeoJson_latCutOff = -22.94 #-500 is ignore
    splitGeoJson_lonCutOff = -43.25       #-500 is ignore
    srcVectorFileList = [[srcVectorFile, 'all']]

    if splitGeoJson:
        srcVectorTrain, srcVectorTest = splitVectorFile(srcVectorFile,
                                                        latCutOff=splitGeoJson_latCutOff,
                                                        lonCutOff=splitGeoJson_lonCutOff)

        srcVectorFileList = [
                            [srcVectorTrain, 'train'],
                            [srcVectorTest, 'test']
                            ]





    # List of Raster Images to Chip and an appropriate label.
    # This list will take any type of Raster supported by GDAL
    # VRTs are nice becasuse they create a virtual mosaic and allow for images covering a wide area to be considered one
    # In this case gdalbuildvrt can be run in a folder of tifs to create the VRT to be handed for processing
    rasterFileList = [['/path/To/3-BandVRT.vrt', '3band'],
                      ['/path/To/8-BandVRT.vrt', '8band']
                      ]

    shapeFileSrcList = [
        [outVectorFile, 'POIAll']
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
        outVectorFile = srcVectorFile.replace('.geojson', 'poly.geojson')
        if createOutVectorFile:
            createPolygonShapeFile(srcVectorFile, outVectorFile, pointOfInterestList)


        outputDirectoryTmp = os.path.join(outputDirectory, folderType)

        shapeFileSrcList = [
            [outVectorFile, 'POIAll']
        ]
    # create Folder Structure to place files into.

        for rasterFile in rasterFileList:
            for featureName in pointOfInterestList.keys():
                tmpPath = os.path.join(outputDirectoryTmp, rasterFile[1], featureName.replace(' ', ''))
                if not os.path.exists(tmpPath):
                    os.makedirs(tmpPath)

        # create Processed Point of Interest Data.
        createProcessedPOIData(srcVectorFile, pointOfInterestList, rasterFileList, shapeFileSrcList,
                               baseName=baseName,
                               className='',
                               outputDirectory=outputDirectoryTmp,
                               seperateImageFolders=seperateImageFolders,
                               minPartialToInclue=0.70)





