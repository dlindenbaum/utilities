from osgeo import ogr, gdal, osr
from spaceNetUtilities import geoTools as gT
import argparse
import os



def returnBoundBoxM(tmpGeom, metersRadius=50):
    poly = gT.createPolygonFromCenterPoint(tmpGeom.GetX(), tmpGeom.GetY(),
                                    metersRadius)

    polyEnv = gT.get_envelope(poly)




    return polyEnv

### Define Point of Interest Dictionary
# {'spacenetFeatureName':
#   {'featureIdNum': '1', # iterative feature id. Used for object name to class number mapping
#    'featureChipScaleM': 200, # Size of chip to create in meters
#    'featureBBoxSizeM': 10 # Feature Bounding Box Assumption.  Code will draw an x meter bounding box around the point
#                           # indicating in the geojson.  This will be used in creating polygons for IOU scoring
#    }

pointOfInterestList = {'Airfield_POIApron Lights Tower': {
    'featureIdNum': '1',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 10
    },
    'Airfield_POIHangar': {
    'featureIdNum': '2',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
    'Airfield_POIHelipad': {
    'featureIdNum': '3',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
'Airfield_POISupport Facility': {
    'featureIdNum': '4',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 10
    },
'Bridges_TunnelsBridgePedestrian': {
    'featureIdNum': '5',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
'Bridges_TunnelsBridgeRoad': {
    'featureIdNum': '6',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
'Commercial_POIServiceBar': {
    'featureIdNum': '7',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
'Electrical_POITransmission Tower': {
    'featureIdNum': '8',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 10
    },
'EmbassiesConsulate': {
    'featureIdNum': '9',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
'Olympic_Venues': {
    'featureIdNum': '10',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 50
    },
'Public_Transportation_POIBusStop': {
    'featureIdNum': '11',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 5
    },
'Railways_POI999999Station': {
    'featureIdNum': '12',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
'Recreation_POIPark': {
    'featureIdNum': '13',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 50
    },
'Recreation_POIPool': {
    'featureIdNum': '14',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 50
    },
'Recreation_POISports Facility': {
    'featureIdNum': '15',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 50
    },
'Religious_InstitutionsChurch': {
    'featureIdNum': '16',
    'featureChipScaleM': 200,
    'featureBBoxSizeM': 25
    },
}


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
                           outputDirectory=''):


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
                       minpartialPerc=0,
                       outputPrefix='',
                       createPix=False,
                       rasterPolyEnvelope=ogr.CreateGeometryFromWkt("POLYGON EMPTY"),
                       className=spacenetFeatureName.replace(' ', ''),
                       baseName=baseName,
                       imgId=imgId)

        chipSummaryList.append(chipSummary)

    return chipSummaryList

if __name__ == '__main__':

    createOutVectorFile = True
    srcVectorFile = '/path/To/PointOfInterestSummary.geojson'
    outVectorFile = '/path/To/PolygonOfInterestSummary.geojson'
    outputDirectory = '/path/To/processedDataPOI/'
    className = 'POIAll'
    baseName = 'AOI_1_RIO'

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

    # create Polygon of Interet from Point of Interest File.  This will create bounding boxes of specified size.
    if createOutVectorFile:
        createPolygonShapeFile(srcVectorFile, outVectorFile, pointOfInterestList)


    # create Folder Structure to place files into.

    for rasterFile in rasterFileList:
        for featureName in pointOfInterestList.keys():
            tmpPath = os.path.join(outputDirectory, rasterFile[1], featureName.replace(' ', ''))
            if not os.path.exists(tmpPath):
                os.makedirs(tmpPath)

    # create Processed Point of Interest Data.
    createProcessedPOIData(srcVectorFile, pointOfInterestList, rasterFileList, shapeFileSrcList,
                           baseName=baseName,
                           className='',
                           outputDirectory=outputDirectory)





