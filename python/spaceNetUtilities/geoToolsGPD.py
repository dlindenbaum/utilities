from osgeo import gdal, osr, ogr
import numpy as np
import os
import csv
import subprocess
import math
import geopandas as gpd
import shapely
import pandas as pd
import rasterio as rio
import affine as af
from shapely.geometry import Point
import pyproj
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.linestring import LineString
from shapely.geometry.multilinestring import MultiLineString
from functools import partial
try:
    import rtree
    import centerline
    import osmnx
except:
    print("rtree not installed, Will break evaluation code")


def import_summary_geojsonGPD(geojsonfilename, removeNoBuildings=True):
    """read summary spacenetV2 geojson into geopandas dataFrame.

       Keyword arguments:
       geojsonfilename -- geojson to read
       removeNoBuildings -- remove all samples with BuildingId == -1 (default =True)
    """


    buildingList_df = gpd.read_file(geojsonfilename)


    if removeNoBuildings:
        buildingList_df = buildingList_df[buildingList_df['BuildingId']!=-1]

    buildingList_df['poly'] = buildingList_df.geometry

    return buildingList_df


def import_chip_geojson(geojsonfilename, ImageId=''):
    """read spacenetV2 chip geojson into geopandas dataFrame.

           Keyword arguments:
           geojsonfilename -- geojson to read
           ImageId -- Specify ImageId.  If not specified. ImageId is defined by
            os.path.splitext(os.path.basename(geojsonfilename))[0]
    """

    buildingList_df = gpd.read_file(geojsonfilename)

    datasource = ogr.Open(geojsonfilename, 0)
    if ImageId=='':
        ImageId = os.path.splitext(os.path.basename(geojsonfilename))[0]

    buildingList_df['ImageId']=ImageId
    buildingList_df['BuildingId'] = range(1, len(buildingList_df) + 1)
    buildingList_df['poly']       = buildingList_df.geometry #[shapely.wkt.loads(x) for x in buildingList_df.geometry.values]

    return buildingList_df


def mergePolyList(geojsonfilename):
    """read geoJson and return dataframe of unary_union

           Keyword arguments:
           geojsonfilename -- geojson to read
 
    """


    buildingList_df = gpd.read_file(geojsonfilename)


    return buildingList_df.unary_union

def readwktcsv(csv_path):
    """read spacenetV2 csv and return geopandas dataframe

               Keyword arguments:
            
               csv_path -- path to csv of spacenetV2 ground truth or solution submission format 
                    csv Format Expected = ['ImageId', 'BuildingId', 'PolygonWKT_Pix', 'PolygonWKT_Geo'] or
                    csv Format Expected = ['ImageId', 'BuildingId', 'PolygonWKT', 'Confidence']
                
            see https://community.topcoder.com/longcontest/?module=ViewProblemStatement&rd=16892&pm=14551 to 
            learn more about the spacenetV2 csv formats   
    """
    #


    df = pd.read_csv(csv_path)
    crs={}
    if 'PolygonWKT_Geo' in df.columns:
        geometry = [shapely.wkt.loads(x) for x in df['PolygonWKT_Geo'].values]
        crs = {'init': 'epsg:4326'}
    elif 'PolygonWKT_Pix' in df.columns:
        geometry = [shapely.wkt.loads(x) for x in df['PolygonWKT_Pix'].values]
    elif 'PolygonWKT' in df.columns:
        geometry = [shapely.wkt.loads(x) for x in df['PolygonWKT'].values]

    else:
        print('Eror No Geometry Column detected, column must be called "PolygonWKT_Geo", "PolygonWKT_Pix", or "PolygonWKT"')
        return -1

    geo_df = gpd.GeoDataFrame(df, crs=crs, geometry=geometry)

    return geo_df


def exporttogeojson(geojsonfilename, geo_df):
    """Write geopandas dataframe to geo_df 

           Keyword arguments:
           geojsonfilename -- geojson to create
           geo_df          -- geopandas dataframe

    """

    #geo_df.to_file(geojsonfilename, driver='GeoJSON', crs=from_epsg(4326))
    geo_df.to_file(geojsonfilename, driver='GeoJSON')

    return geojsonfilename


def createmaskfrompolygons(polygons):
    ## todo implement through label tools
    pass
    ## see labelTools createRasterFromGeoJson


def geomGeo2geomPixel(geom, affineObject=[], input_raster='', gdal_geomTransform=[]):
    # This function transforms a shapely geometry in geospatial coordinates into pixel coordinates
    # geom must be shapely geometry
    # affineObject = rasterio.open(input_raster).affine
    # gdal_geomTransform = gdal.Open(input_raster).GetGeoTransform()
    # input_raster is path to raster to gather georectifcation information
    if not affineObject:
        if input_raster != '':
            affineObject = rio.open(input_raster).affine
        else:
            affineObject = af.Affine.from_gdal(gdal_geomTransform)

    affineObjectInv = ~affineObject

    geomTransform = shapely.affinity.affine_transform(geom,
                                      [affineObjectInv.a,
                                       affineObjectInv.b,
                                       affineObjectInv.d,
                                       affineObjectInv.e,
                                       affineObjectInv.xoff,
                                       affineObjectInv.yoff]
                                      )

    return geomTransform


def geomPixel2geomGeo(geom, affineObject=[], input_raster='', gdal_geomTransform=[]):
    # This function transforms a shapely geometry in pixel coordinates into geospatial coordinates
    # geom must be shapely geometry
    # affineObject = rasterio.open(input_raster).affine
    # gdal_geomTransform = gdal.Open(input_raster).GetGeoTransform()
    # input_raster is path to raster to gather georectifcation information
    if not affineObject:
        if input_raster != '':
            affineObject = rio.open(input_raster).affine
        else:
            affineObject = af.Affine.from_gdal(gdal_geomTransform)


    geomTransform = shapely.affinity.affine_transform(geom,
                                                      [affineObject.a,
                                                       affineObject.b,
                                                       affineObject.d,
                                                       affineObject.e,
                                                       affineObject.xoff,
                                                       affineObject.yoff]
                                                      )

    return geomTransform



def returnBoundBox(xCenter, yCenter, pixDim, affineObject=[], input_raster='', gdal_geomTransform=[], pixelSpace=False):

    geom = Point(xCenter, yCenter)
    geom = geom.buffer(pixDim)
    geom = geom.envelope

    if not pixelSpace:
        geom = geomPixel2geomGeo(geom, affineObject=affineObject, input_raster=input_raster, gdal_geomTransform=gdal_geomTransform)
    else:
        geom

    return geom


def createBoxFromLine(tmpGeom, ratio=1, halfWidth=-999, transformRequired=True, transform_WGS84_To_UTM='', transform_UTM_To_WGS84=''):
    # create Polygon Box Oriented with the line

    if transformRequired:
        if transform_WGS84_To_UTM == '':
            transform_WGS84_To_UTM, transform_UTM_To_WGS84 = createUTMTransform(tmpGeom)

        tmpGeom = shapely.ops.tranform(transform_WGS84_To_UTM, tmpGeom)




    # calculatuate Centroid

    lengthM = tmpGeom.length
    if halfWidth ==-999:
        halfWidth = lengthM/(2*ratio)

    polyGeom = tmpGeom.buffer(halfWidth, cap_style=shapely.geometry.CAP_STYLE.flat)

    angRad = math.atan2((tmpGeom.coords[1][1]-tmpGeom.coords[0][1],
                        tmpGeom.coords[1][0] - tmpGeom.coords[0][0]))

    areaM = polyGeom.area

    if transformRequired:
        polyGeom = shapely.ops.tranform(transform_UTM_To_WGS84, polyGeom)



    return (polyGeom, areaM, angRad, lengthM)





def geoWKTToPixelWKT(geom, inputRaster, targetSR, geomTransform, pixPrecision=2):


    print('Deprecated')
    ## shapely.wkt.dumps(geom, trim=pixPrecision)
    ## newGeom = geom
    ## newGeom.coords = np.round(np.array(geom.coords), pixPrecision)





def create_rtreefromdict(buildinglist):
    # create index
    index = rtree.index.Index(interleaved=False)
    for idx, building in enumerate(buildinglist):
        index.insert(idx, building['poly'].GetEnvelope())

    return index

def search_rtree(test_building, index):
    # input test shapely polygon geometry  and rtree index
    if test_building.geom_type == 'Polygon' or \
                    test_building.geom_type == 'MultiPolygon':
        fidlist = list(index.intersection(test_building.bounds))
    else:
        fidlist = []

    return fidlist


def get_envelope(poly):

    return poly.envelope

def utm_getZone(longitude):

    return (int(1+(longitude+180.0)/6.0))


def utm_isNorthern(latitude):

    if (latitude < 0.0):
        return 0
    else:
        return 1

def createUTMandLatLonCrs(polyGeom):

    polyCentroid = polyGeom.centroid
    utm_zone = utm_getZone(polyCentroid.x)
    is_northern = utm_isNorthern(polyCentroid.y)
    if is_northern:
        directionIndicator = '+north'
    else:
        directionIndicator = '+south'

    utm_crs = {'datum': 'NAD83',
               'ellps': 'GRS80',
               'proj': 'utm',
               'zone': utm_zone,
               'units': 'm'}

    latlong_crs = {'init': 'epsg:4326'}

    return utm_crs, latlong_crs

def createUTMTransform(polyGeom):

    polyCentroid = polyGeom.centroid
    utm_zone = utm_getZone(polyCentroid.x)
    is_northern = utm_isNorthern(polyCentroid.y)
    if is_northern:
        directionIndicator = '+north'
    else:
        directionIndicator = '+south'

    projectTO_UTM = partial(
        pyproj.transform,
        pyproj.Proj("+proj=longlat +datum=WGS84 +no_defs"),  #Proj(proj='latlong',datum='WGS84')
        pyproj.Proj("+proj=utm +zone={} {} +ellps=WGS84 +datum=WGS84 +units=m +no_defs".format(utm_zone,
                                                                                               directionIndicator))
    )


    projectTO_WGS = partial(
        pyproj.transform,
        pyproj.Proj("+proj=utm +zone={} {} +ellps=WGS84 +datum=WGS84 +units=m +no_defs".format(utm_zone,
                                                                                               directionIndicator)
                    ),
        pyproj.Proj("+proj=longlat +datum=WGS84 +no_defs"),  # Proj(proj='latlong',datum='WGS84')

    )

    return projectTO_UTM,  projectTO_WGS


def getRasterExtent(srcImage):

    poly = Polygon(((srcImage.bounds.left, srcImage.bounds.top),
                   (srcImage.bounds.right, srcImage.bounds.top),
                   (srcImage.bounds.right, srcImage.bounds.bottom),
                   (srcImage.bounds.left, srcImage.bounds.bottom))
                    )



    return srcImage.affine, \
           poly, \
           srcImage.bounds.left, \
           srcImage.bounds.top, \
           srcImage.bounds.right, \
           srcImage.bounds.bottom

def createPolygonFromCenterPointXY(cX,cY, radiusMeters, transform_WGS_To_UTM_Flag=True):


    point = Point(cX, cY)

    return createPolygonFromCenterPoint(point, radiusMeters, transform_WGS_To_UTM_Flag=True)

def createPolygonFromCenterPoint(point, radiusMeters, transform_WGS_To_UTM_Flag=True):


    transform_WGS84_To_UTM, transform_UTM_To_WGS84 = createUTMTransform(point)
    if transform_WGS_To_UTM_Flag:
        point = shapely.ops.tranform(transform_WGS84_To_UTM, point)

    poly = point.Buffer(radiusMeters)

    if transform_WGS_To_UTM_Flag:
        poly = shapely.ops.tranform(transform_UTM_To_WGS84, poly)

    return poly


def createPolygonFromCentroidGDF(gdf, radiusMeters, transform_WGS_To_UTM_Flag=True):

    if transform_WGS_To_UTM_Flag:
        transform_WGS84_To_UTM, transform_UTM_To_WGS84 = createUTMTransform(gdf.centroid.values[0])
        gdf.to_crs()
        point = shapely.ops.tranform(transform_WGS84_To_UTM, point)

    poly = point.Buffer(radiusMeters)

    if transform_WGS_To_UTM_Flag:
        poly = shapely.ops.tranform(transform_UTM_To_WGS84, poly)

    return poly


def createPolygonFromCorners(left,bottom,right, top):
    # Create ring
    poly = Polygon((left, top),
                   (right, top),
                   (right, bottom),
                   (left, bottom)
                    )

    return poly


def clipShapeFileGPD(geoDF, outputFileName, polyToCut, minpartialPerc=0.0, shapeLabel='Geo', debug=False):
    # check if geoDF has origAreaField
    outGeoJSon = os.path.splitext(outputFileName)[0] + '.geojson'
    if not os.path.exists(os.path.dirname(outGeoJSon)):
        os.makedirs(os.path.dirname(outGeoJSon))
    if debug:
        print(outGeoJSon)

    if 'origarea' in geoDF.columns:
        pass
    else:
        geoDF['origarea'] = geoDF.area



    cutGeoDF = geoDF[geoDF.intersetion(polyToCut).area/geoDF['origarea'] > minpartialPerc]
    cutGeoDF['partialDec'] = cutGeoDF.area/cutGeoDF['origarea']
    cutGeoDF['truncated'] = cutGeoDF['partialDec']==1.0

    ##TODO Verify this works in DockerBuild
    cutGeoDF.to_file(outGeoJSon, driver='GeoJSON')

def clipShapeFile(shapeSrc, outputFileName, polyToCut, minpartialPerc=0.0, shapeLabel='Geo', debug=False):
    ## Deprecated
    print('Deprecated use clipShapeFileGPD')
    source_layer = shapeSrc.GetLayer()
    source_srs = source_layer.GetSpatialRef()
    # Create the output Layer

    outGeoJSon = os.path.splitext(outputFileName)[0] + '.geojson'
    if not os.path.exists(os.path.dirname(outGeoJSon)):
        os.makedirs(os.path.dirname(outGeoJSon))
    print(outGeoJSon)
    outDriver = ogr.GetDriverByName("geojson")
    if os.path.exists(outGeoJSon):
        outDriver.DeleteDataSource(outGeoJSon)

    if debug:
        outGeoJSonDebug = outputFileName.replace('.tif', 'outline.geojson')
        outDriverDebug = ogr.GetDriverByName("geojson")
        if os.path.exists(outGeoJSonDebug):
            outDriverDebug.DeleteDataSource(outGeoJSonDebug)
        outDataSourceDebug = outDriver.CreateDataSource(outGeoJSonDebug)
        outLayerDebug = outDataSourceDebug.CreateLayer("groundTruth", source_srs, geom_type=ogr.wkbPolygon)

        outFeatureDebug = ogr.Feature(source_layer.GetLayerDefn())
        outFeatureDebug.SetGeometry(polyToCut)
        outLayerDebug.CreateFeature(outFeatureDebug)


    outDataSource = outDriver.CreateDataSource(outGeoJSon)
    outLayer = outDataSource.CreateLayer("groundTruth", source_srs, geom_type=ogr.wkbPolygon)
    # Add input Layer Fields to the output Layer
    inLayerDefn = source_layer.GetLayerDefn()
    for i in range(0, inLayerDefn.GetFieldCount()):
        fieldDefn = inLayerDefn.GetFieldDefn(i)
        outLayer.CreateField(fieldDefn)
    outLayer.CreateField(ogr.FieldDefn("partialBuilding", ogr.OFTReal))
    outLayer.CreateField(ogr.FieldDefn("partialDec", ogr.OFTReal))
    outLayerDefn = outLayer.GetLayerDefn()
    source_layer.SetSpatialFilter(polyToCut)
    for inFeature in source_layer:

        outFeature = ogr.Feature(outLayerDefn)

        for i in range (0, inLayerDefn.GetFieldCount()):
            outFeature.SetField(inLayerDefn.GetFieldDefn(i).GetNameRef(), inFeature.GetField(i))

        geom = inFeature.GetGeometryRef()
        geomNew = geom.Intersection(polyToCut)
        partialDec = -1
        if geomNew:

            if geomNew.GetGeometryName()=='POINT':
                outFeature.SetField("partialDec", 1)
                outFeature.SetField("partialBuilding", 1)
            else:

                if geom.GetArea() > 0:
                    partialDec = geomNew.GetArea() / geom.GetArea()
                else:
                    partialDec = 0

                outFeature.SetField("partialDec", partialDec)

                if geom.GetArea() == geomNew.GetArea():
                    outFeature.SetField("partialBuilding", 0)
                else:
                    outFeature.SetField("partialBuilding", 1)


        else:
            outFeature.SetField("partialBuilding", 1)
            outFeature.SetField("partialBuilding", 1)


        outFeature.SetGeometry(geomNew)
        if partialDec >= minpartialPerc:
            outLayer.CreateFeature(outFeature)
            #print ("AddFeature")


def cutChipFromMosaicGPD(rasterFileList, shapeFileSrcList, outlineSrc='',outputDirectory='', outputPrefix='clip_',
                         clipSizeMX=100, clipSizeMY=100, clipOverlap=0.0, minpartialPerc=0.0, createPix=False,
                         baseName='',
                         imgIdStart=-1,
                         parrallelProcess=False,
                         noBlackSpace=False,
                         randomClip=-1,
                         debug=False
                         ):

    srcImage = rio.open(rasterFileList[0][0])
    geoTrans, poly, ulX, ulY, lrX, lrY = getRasterExtent(srcImage)
    # geoTrans[1] w-e pixel resolution
    # geoTrans[5] n-s pixel resolution
    if outputDirectory=="":
        outputDirectory=os.path.dirname(rasterFileList[0][0])

    rasterFileBaseList = []
    for rasterFile in rasterFileList:
        rasterFileBaseList.append(os.path.basename(rasterFile[0]))

    if not createPix:
        transform_WGS84_To_UTM, transform_UTM_To_WGS84 = createUTMTransform(poly)
        poly = shapely.ops.tranform(transform_WGS84_To_UTM, poly)

    minX, minY, maxX, maxY = poly.bounds

    #return poly to WGS84
    if not createPix:
        poly = shapely.ops.tranform(transform_UTM_To_WGS84, poly)


    shapeSrcList = []
    for shapeFileSrc in shapeFileSrcList:
        print(shapeFileSrc[1])
        shapeSrcList.append([ogr.Open(shapeFileSrc[0],0), shapeFileSrc[1]])


    if outlineSrc == '':
        geomOutline = poly
    else:
        outline = gpd.read_file(outlineSrc)
        geomOutlineBase = outline.geometry[0]
        geomOutline = geomOutlineBase.Intersection(poly)

    chipSummaryList = []

    for rasterFile in rasterFileList:
        if not os.path.exists(os.path.join(outputDirectory, rasterFile[1])):
            os.makedirs(os.path.join(outputDirectory, rasterFile[1]))
    idx = 0
    if createPix:
        if debug:
            print(geoTrans)

        clipSizeMX=clipSizeMX*geoTrans[1]
        clipSizeMY=abs(clipSizeMY*geoTrans[5])

    xInterval = np.arange(minX, maxX, clipSizeMX*(1.0-clipOverlap))
    if debug:
        print('minY = {}'.format(minY))
        print('maxY = {}'.format(maxY))
        print('clipsizeMX ={}'.format(clipSizeMX))
        print('clipsizeMY ={}'.format(clipSizeMY))

    yInterval = np.arange(minY, maxY, clipSizeMY*(1.0-clipOverlap))

    if debug:
        print(xInterval)
        print(yInterval)

    for llX in xInterval:

        for llY in yInterval:
            uRX = llX+clipSizeMX
            uRY = llY+clipSizeMY

            # check if uRX or uRY is outside image
            if noBlackSpace:
                if uRX > maxX:
                    uRX = maxX
                    llX = maxX - clipSizeMX
                if uRY > maxY:
                    uRY = maxY
                    llY = maxY - clipSizeMY

            polyCut = createPolygonFromCorners(llX, llY, uRX, uRY)


            if not createPix:

                polyCut.Transform(transform_UTM_To_WGS84)
            ## add debug line do cuts
            if (polyCut).Intersects(geomOutline):

                if debug:
                    print("Do it.")

                minXCut = llX
                minYCut = llY
                maxXCut = uRX
                maxYCut = uRY

                if debug:
                    print('minYCut = {}'.format(minYCut))
                    print('maxYCut = {}'.format(maxYCut))
                    print('minXCut = {}'.format(minXCut))
                    print('maxXCut = {}'.format(maxXCut))
                    print('clipsizeMX ={}'.format(clipSizeMX))
                    print('clipsizeMY ={}'.format(clipSizeMY))

                idx = idx+1
                if imgIdStart == -1:
                    imgId = -1
                else:
                    imgId = idx

                chipSummary = createclip(outputDirectory, rasterFileList, shapeSrcList,
                                         maxXCut, maxYCut, minYCut, minXCut,
                                         rasterFileBaseList=rasterFileBaseList,
                                         minpartialPerc=minpartialPerc,
                                         outputPrefix=outputPrefix,
                                         createPix=createPix,
                                         rasterPolyEnvelope=poly,
                                         baseName=baseName,
                                         imgId=imgId)

                chipSummaryList.append(chipSummary)

    return chipSummaryList

def cutChipFromMosaic(rasterFileList, shapeFileSrcList, outlineSrc='',outputDirectory='', outputPrefix='clip_',
                      clipSizeMX=100, clipSizeMY=100, clipOverlap=0.0, minpartialPerc=0.0, createPix=False,
                      baseName='',
                      imgIdStart=-1,
                      parrallelProcess=False,
                      noBlackSpace=False,
                      randomClip=-1):
    #rasterFileList = [['rasterLocation', 'rasterDescription']]
    # i.e rasterFileList = [['/path/to/3band_AOI_1.tif, '3band'],
    #                       ['/path/to/8band_AOI_1.tif, '8band']
    #                        ]
    # open Base Image
    #print(rasterFileList[0][0])
    srcImage = gdal.Open(rasterFileList[0][0])
    geoTrans, poly, ulX, ulY, lrX, lrY = getRasterExtent(srcImage)
    # geoTrans[1] w-e pixel resolution
    # geoTrans[5] n-s pixel resolution
    if outputDirectory=="":
        outputDirectory=os.path.dirname(rasterFileList[0][0])

    rasterFileBaseList = []
    for rasterFile in rasterFileList:
        rasterFileBaseList.append(os.path.basename(rasterFile[0]))

    if not createPix:
        transform_WGS84_To_UTM, transform_UTM_To_WGS84 = createUTMTransform(poly)
        poly = shapely.ops.tranform(transform_WGS84_To_UTM, poly)

    env = poly.GetEnvelope()
    minX = env[0]
    minY = env[2]
    maxX = env[1]
    maxY = env[3]

    #return poly to WGS84
    if not createPix:
        poly = shapely.ops.tranform(transform_UTM_To_WGS84, poly)


    shapeSrcList = []
    for shapeFileSrc in shapeFileSrcList:
        print(shapeFileSrc[1])
        shapeSrcList.append([ogr.Open(shapeFileSrc[0],0), shapeFileSrc[1]])


    if outlineSrc == '':
        geomOutline = poly
    else:
        outline = ogr.Open(outlineSrc)
        layer = outline.GetLayer()
        featureOutLine = layer.GetFeature(0)
        geomOutlineBase = featureOutLine.GetGeometryRef()
        geomOutline = geomOutlineBase.Intersection(poly)

    chipSummaryList = []

    for rasterFile in rasterFileList:
        if not os.path.exists(os.path.join(outputDirectory, rasterFile[1])):
            os.makedirs(os.path.join(outputDirectory, rasterFile[1]))
    idx = 0
    if createPix:
        print(geoTrans)
        clipSizeMX=clipSizeMX*geoTrans[1]
        clipSizeMY=abs(clipSizeMY*geoTrans[5])

    xInterval = np.arange(minX, maxX, clipSizeMX*(1.0-clipOverlap))
    print('minY = {}'.format(minY))
    print('maxY = {}'.format(maxY))
    print('clipsizeMX ={}'.format(clipSizeMX))
    print('clipsizeMY ={}'.format(clipSizeMY))

    yInterval = np.arange(minY, maxY, clipSizeMY*(1.0-clipOverlap))
    print(xInterval)
    print(yInterval)
    for llX in xInterval:
        if parrallelProcess:
            for llY in yInterval:
                pass

        else:
            for llY in yInterval:
                uRX = llX+clipSizeMX
                uRY = llY+clipSizeMY

                # check if uRX or uRY is outside image
                if noBlackSpace:
                    if uRX > maxX:
                        uRX = maxX
                        llX = maxX - clipSizeMX
                    if uRY > maxY:
                        uRY = maxY
                        llY = maxY - clipSizeMY




                polyCut = createPolygonFromCorners(llX, llY, uRX, uRY)







                if not createPix:

                    polyCut.Transform(transform_UTM_To_WGS84)
                ## add debug line do cuts
                if (polyCut).Intersects(geomOutline):
                    print("Do it.")
                    #envCut = polyCut.GetEnvelope()
                    #minXCut = envCut[0]
                    #minYCut = envCut[2]
                    #maxXCut = envCut[1]
                    #maxYCut = envCut[3]

                    #debug for real
                    minXCut = llX
                    minYCut = llY
                    maxXCut = uRX
                    maxYCut = uRY

                    #print('minYCut = {}'.format(minYCut))
                    #print('maxYCut = {}'.format(maxYCut))
                    #print('minXCut = {}'.format(minXCut))
                    #print('maxXCut = {}'.format(maxXCut))

                    #print('clipsizeMX ={}'.format(clipSizeMX))
                    #print('clipsizeMY ={}'.format(clipSizeMY))



                    idx = idx+1
                    if imgIdStart == -1:
                        imgId = -1
                    else:
                        imgId = idx

                    chipSummary = createclip(outputDirectory, rasterFileList, shapeSrcList,
                                             maxXCut, maxYCut, minYCut, minXCut,
                                             rasterFileBaseList=rasterFileBaseList,
                                             minpartialPerc=minpartialPerc,
                                             outputPrefix=outputPrefix,
                                             createPix=createPix,
                                             rasterPolyEnvelope=poly,
                                             baseName=baseName,
                                             imgId=imgId,
                                             s3Options=[])
                    chipSummaryList.append(chipSummary)

    return chipSummaryList

def createclip(outputDirectory, rasterFileList, shapeSrcList,
               maxXCut, maxYCut, minYCut, minXCut,
               rasterFileBaseList=[],
               minpartialPerc=0,
               outputPrefix='',
               createPix=False,
               rasterPolyEnvelope=ogr.CreateGeometryFromWkt("POLYGON EMPTY"),
               className='',
               baseName='',
               imgId=-1,
               s3Options=[]):

    #rasterFileList = [['rasterLocation', 'rasterDescription']]
    # i.e rasterFileList = [['/path/to/3band_AOI_1.tif, '3band'],
    #                       ['/path/to/8band_AOI_1.tif, '8band']
    #                        ]

    polyCutWGS = createPolygonFromCorners(minXCut, minYCut, maxXCut, maxYCut)


    if not rasterFileBaseList:
        rasterFileBaseList = []
        for rasterFile in rasterFileList:
            rasterFileBaseList.append(os.path.basename(rasterFile[0]))

    if rasterPolyEnvelope == '':
        pass

    chipNameList = []
    for rasterFile in rasterFileList:
        if className == '':
            if imgId==-1:
                chipNameList.append(outputPrefix + rasterFile[1] +
                                    "_" + baseName + "_{}_{}.tif".format(minXCut, minYCut))
            else:
                chipNameList.append(outputPrefix + rasterFile[1] +
                                    "_" + baseName + "_img{}.tif".format(imgId))
        else:
            if imgId==-1:
                chipNameList.append(outputPrefix + className + "_" +
                                    rasterFile[1] + "_" + baseName + "_{}_{}.tif".format(minXCut, minYCut))
            else:
                chipNameList.append(outputPrefix + className + '_' +
                                rasterFile[1] + "_" + baseName + "_img{}.tif".format(imgId))

    # clip raster

    for chipName, rasterFile in zip(chipNameList, rasterFileList):
        outputFileName = os.path.join(outputDirectory, rasterFile[1], className, chipName)
        ## Clip Image
        print(rasterFile)
        print(outputFileName)

        #TODO replace gdalwarp with rasterio and windowed reads
        cmd = ["gdalwarp", "-te", "{}".format(minXCut), "{}".format(minYCut),  "{}".format(maxXCut),
                         "{}".format(maxYCut),
                         '-co', 'PHOTOMETRIC=rgb',
                         rasterFile[0], outputFileName]
        cmd.extend(s3Options)
        subprocess.call(cmd)

    baseLayerRasterName = os.path.join(outputDirectory, rasterFileList[0][1], className, chipNameList[0])
    outputFileName = os.path.join(outputDirectory, rasterFileList[0][1], chipNameList[0])


    ### Clip poly to cust to Raster Extent
    if rasterPolyEnvelope.GetArea() == 0:
        srcImage = gdal.Open(rasterFileList[0][0])
        geoTrans, rasterPolyEnvelope, ulX, ulY, lrX, lrY = getRasterExtent(srcImage)
        polyVectorCut = polyCutWGS.Intersection(rasterPolyEnvelope)
    else:
        polyVectorCut = polyCutWGS.Intersection(rasterPolyEnvelope)

    # Interate thorough Vector Src List
    for shapeSrc in shapeSrcList:
        if imgId == -1:
            outGeoJson = outputPrefix + shapeSrc[1] + \
                         "_" + baseName + "_{}_{}.geojson".format(minXCut, minYCut)
        else:
            outGeoJson = outputPrefix + shapeSrc[1] + \
                         "_" + baseName + "_img{}.geojson".format(imgId)

        outGeoJson = os.path.join(outputDirectory, 'geojson', shapeSrc[1], outGeoJson)

        clipShapeFile(shapeSrc[0], outGeoJson, polyVectorCut, minpartialPerc=minpartialPerc)


    chipSummary = {'rasterSource': baseLayerRasterName,
                   'chipName': chipNameList[0],
                   'geoVectorName': outGeoJson,
                   'pixVectorName': ''
                   }

    return chipSummary

def cutChipFromRasterCenter(rasterFileList, shapeFileSrc, outlineSrc='',
                            outputDirectory='', outputPrefix='clip_',
                            clipSizeMeters=50, createPix=False,
                            classFieldName = 'TYPE',
                            minpartialPerc=0.1,
                            ):
    #rasterFileList = [['rasterLocation', 'rasterDescription']]
    # i.e rasterFileList = [['/path/to/3band_AOI_1.tif, '3band'],
    #                       ['/path/to/8band_AOI_1.tif, '8band']
    #                        ]
    srcImage = gdal.Open(rasterFileList[0][0])
    geoTrans, poly, ulX, ulY, lrX, lrY = getRasterExtent(srcImage)

    if outputDirectory == "":
        outputDirectory = os.path.dirname(rasterFileList[0])

    rasterFileBaseList = []
    for rasterFile in rasterFileList:
        rasterFileBaseList.append(os.path.basename(rasterFile[0]))

    transform_WGS84_To_UTM, transform_UTM_To_WGS84, utm_cs = createUTMTransform(poly)
    poly.Transform(transform_WGS84_To_UTM)
    env = poly.GetEnvelope()

    # return poly to WGS84
    poly.Transform(transform_UTM_To_WGS84)

    shapeSrc = ogr.Open(shapeFileSrc, 0)
    if outlineSrc == '':
        geomOutline = poly
    else:
        outline = ogr.Open(outlineSrc)
        layer = outline.GetLayer()
        featureOutLine = layer.GetFeature(0)
        geomOutlineBase = featureOutLine.GetGeometryRef()
        geomOutline = geomOutlineBase.Intersection(poly)

    shapeSrcBase = ogr.Open(shapeFileSrc, 0)
    layerBase = shapeSrcBase.GetLayer()
    layerBase.SetSpatialFilter(geomOutline)
    for rasterFile in rasterFileList:
        if not os.path.exists(os.path.join(outputDirectory, rasterFile[1])):
            os.makedirs(os.path.join(outputDirectory, rasterFile[1]))
    for feature in layerBase:
        featureGeom = feature.GetGeometryRef()
        cx, cy, cz = featureGeom.Centroid().GetPoint()
        polyCut = createPolygonFromCenterPoint(cx, cy, radiusMeters=clipSizeMeters)
        print(classFieldName)
        classDescription = feature.GetField(classFieldName)
        classDescription = classDescription.replace(" ","")
        envCut = polyCut.GetEnvelope()
        minXCut = envCut[0]
        minYCut = envCut[2]
        maxXCut = envCut[1]
        maxYCut = envCut[3]
        createclip(outputDirectory, rasterFileList, shapeSrc,
                       maxXCut, maxYCut, minYCut, minXCut,
                       rasterFileBaseList=rasterFileBaseList,
                       minpartialPerc=minpartialPerc,
                       outputPrefix=outputPrefix,
                       createPix=createPix,
                       rasterPolyEnvelope=poly,
                       className=classDescription)



def rotateClip(clipFileName, sourceGeoJson, rotaionList=[0,90,180,275]):
    # will add "_{}.ext".formate(rotationList[i]
    pass



def createMaskedMosaic(input_raster, output_raster, outline_file):

    subprocess.call(["gdalwarp", "-q", "-cutline", outline_file, "-of", "GTiff", input_raster, output_raster,
                     '-wo', 'OPTIMIZE_SIZE=YES',
                     '-co', 'COMPRESS=JPEG',
                     '-co', 'PHOTOMETRIC=YCBCR',
                     '-co', 'TILED=YES'])



def explodeGeoPandasFrame(inGDF):

    #This function splits entries with MultiPolygon geometries into Polygon Geometries

    outdf = gpd.GeoDataFrame(columns=inGDF.columns)
    for idx, row in inGDF.iterrows():
        if type(row.geometry) == Polygon:
            outdf = outdf.append(row,ignore_index=True)
        if type(row.geometry) == MultiPolygon:
            multdf = gpd.GeoDataFrame(columns=inGDF.columns)
            recs = len(row.geometry)
            multdf = multdf.append([row]*recs,ignore_index=True)
            for geom in range(recs):
                multdf.loc[geom,'geometry'] = row.geometry[geom]
            multdf.head()
            outdf = outdf.append(multdf,ignore_index=True)

        if type(row.geometry) == LineString:
            outdf = outdf.append(row, ignore_index=True)

        if type(row.geometry) == MultiLineString:
            multdf = gpd.GeoDataFrame(columns=inGDF.columns)
            recs = len(row.geometry)
            multdf = multdf.append([row]*recs,ignore_index=True)
            for geom in range(recs):
                multdf.loc[geom,'geometry'] = row.geometry[geom]
            multdf.head()
            outdf = outdf.append(multdf,ignore_index=True)


    outdf.crs = inGDF.crs


    return outdf

def calculateCenterLineFromGeopandasPolygon(inGDF,
                                            centerLineDistanceInput_Meters=5,
                                            simplifyDistanceMeters=5,
                                            projectToUTM=True):

    # project To UTM for GeoSpatial Measurements
    if projectToUTM:
        tmpGDF = osmnx.project_gdf(inGDF)
    else:
        tmpGDF = inGDF

    # Explode GeoPandas
    tmpGDF1 = explodeGeoPandasFrame(tmpGDF)
    tmpGDF1.crs = tmpGDF.crs
    gdf_centerline_utm = tmpGDF1


    # Loop through Geomertries to calculate Centerline for Each Polygon
    listOfGeoms = tmpGDF1['geometry'].values
    lineStringList = []

    for geom in listOfGeoms:
        tmpGeom = centerline.Centerline(geom, centerLineDistanceInput_Meters)
        lineStringList.append(tmpGeom.createCenterline())

    gdf_centerline_utm['geometry'] = lineStringList

    lineList = gdf_centerline_utm['geometry'].values
    lineSimplifiedList = []

    for geo in lineList:


        if geo.type == 'MultiLineString':

            geoNew = shapely.ops.linemerge(geo).simplify(simplifyDistanceMeters, preserve_topology=False)

        else:

            geoNew = geo.simplify(simplifyDistanceMeters, preserve_topology=False)

        lineSimplifiedList.append(geoNew)

    simplifiedGdf_utm = gpd.GeoDataFrame({'geometry': lineSimplifiedList})
    simplifiedGdf_utm.crs = tmpGDF.crs
    print (tmpGDF.crs)

    if projectToUTM:
        gdf_simple_centerline = simplifiedGdf_utm.to_crs(inGDF.crs)
    else:
        gdf_simple_centerline = simplifiedGdf_utm


    return gdf_simple_centerline


def calculateCenterLineFromOGR(inputSrcFile, centerLineDistanceInput_Meters=5, outputShpFile=''):

    inGDF = gpd.read_file(inputSrcFile)
    outGDF = calculateCenterLineFromGeopandasPolygon(inGDF, centerLineDistanceInput_Meters=centerLineDistanceInput_Meters)

    if outputShpFile != '':
        outGDF.to_file(outputShpFile)


    return outGDF


def createBufferGeoPandas(inGDF, bufferDistanceMeters=5, bufferRoundness=1, projectToUTM=True):
    # Calculate CenterLine
    ## Define Buffer Constraints


    # Transform gdf Roadlines into UTM so that Buffer makes sense
    if projectToUTM:
        tmpGDF = osmnx.project_gdf(inGDF)
    else:
        tmpGDF = inGDF

    gdf_utm_buffer = tmpGDF

    # perform Buffer to produce polygons from Line Segments
    gdf_utm_buffer['geometry'] = tmpGDF.buffer(bufferDistanceMeters,
                                                bufferRoundness)

    gdf_utm_dissolve = gdf_utm_buffer.dissolve(by='class')
    gdf_utm_dissolve.crs = gdf_utm_buffer.crs

    if projectToUTM:
        gdf_buffer = gdf_utm_dissolve.to_crs(inGDF.crs)
    else:
        gdf_buffer = gdf_utm_dissolve


    return gdf_buffer

#def project_gdfToUTM(gdf, lat=[], lon=[]):


