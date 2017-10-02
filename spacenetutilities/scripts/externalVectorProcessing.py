from spacenetutilities import geoTools as gT
from spacenetutilities import labeltools as lT
import fiona as fio
import geopandas as gpd
import rasterio
import argparse
import os
import glob



def buildTindex(rasterFolder, rasterExtention='.tif'):

    rasterList = glob.glob(os.path.join(rasterFolder, '*{}'.format(rasterExtention)))
    print(rasterList)

    print(os.path.join(rasterFolder, '*{}'.format(rasterExtention)))



    featureList = []

    for rasterFile in rasterList:
        with rasterio.open(rasterFile) as srcImage:


            geoTrans, polyToCut, ulX, ulY, lrX, lrY = gT.getRasterExtent(srcImage)

        feature = {'geometry': polyToCut,
                   'location': rasterFile}

        featureList.append(feature)

        geoDFTindex = gpd.GeoDataFrame(featureList)

    return geoDFTindex


def createTiledGeoJsonFromSrc(rasterFolderLocation, vectorSrcFile, geoJsonOutputDirectory, rasterTileIndex='',
                              geoJsonPrefix='GEO', rasterFileExtenstion='.tif',
                              rasterPrefixToReplace='PAN'
                              ):
    if rasterTileIndex == '':
        geoDFTindex = buildTindex(rasterFolderLocation, rasterExtention=rasterFileExtenstion)
    else:
        geoDFTindex = gpd.read_file(rasterTileIndex)

    shapeSrc = gpd.read_file(vectorSrcFile)

    chipSummaryList = []
    for idx, feature in geoDFTindex.iterrows():
        featureGeom = feature['geometry']
        rasterFileName = feature['location']
        rasterFileBaseName = os.path.basename(rasterFileName)
        outGeoJson = rasterFileBaseName.replace(rasterPrefixToReplace, geoJsonPrefix)
        outGeoJson = outGeoJson.replace(rasterFileExtenstion, '.geojson')
        outGeoJson = os.path.join(geoJsonOutputDirectory, outGeoJson)

        gT.clipShapeFile(shapeSrc, outGeoJson, featureGeom, minpartialPerc=0.0, debug=False)
        imageId = rasterFileBaseName.replace(rasterPrefixToReplace+"_", "")
        chipSummary = {'chipName': rasterFileName,
                           'geoVectorName': outGeoJson,
                           'imageId': os.path.splitext(imageId)[0]}

        chipSummaryList.append(chipSummary)

    return chipSummaryList

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-imgDir", "--imgDir", type=str,
                        help="Directory of Raster Images")
    parser.add_argument("-vecSrc", "--vectorSrcFile", type=str,
                        help="Geo spatial Vector src file supported by GDAL and OGR")
    parser.add_argument("-vecPrFx", "--vectorPrefix", type=str,
                        help="Prefix to attach to image id to indicate type of geojson created",
                        default='OSM')
    parser.add_argument("-rastPrFx", "--rasterPrefix", type=str,
                        help="Prefix of raster images to replace when creating geojson of geojson created",
                        default='PAN')
    parser.add_argument("-rastExt", "--rasterExtension", type=str,
                        help="Extension of raster images to i.e. .tif, .png, .jpeg",
                        default='.tif')

    parser.add_argument("-o", "--outputCSV", type=str,
                        help="Output file name and location for truth summary CSV equivalent to SpacenetV2 competition")
    parser.add_argument("-pixPrecision", "--pixelPrecision", type=int,
                        help="Number of decimal places to include for pixel, uses round(xPix, pixPrecision)"
                             "Default = 2",
                        default=2)
    parser.add_argument("--CreateProposalFile",
                        help="Create proposals file in format approriate for SpacenetV2 competition",
                        action="store_true")




    args = parser.parse_args()



    rasterFolderLocation = args.imgDir
    vectorSrcFile = args.vectorSrcFile
    vectorPrefix = args.vectorPrefix
    rasterPrefix = args.rasterPrefix
    pixPrecision = args.pixelPrecision
    createProposalFile = args.CreateProposalFile
    rasterFileExtension = args.rasterExtension

    rasterFolderBaseName = os.path.basename(rasterFolderLocation)
    if rasterFolderBaseName == "":
        rasterFolderBaseName = os.path.basename(os.path.dirname(rasterFolderLocation))

    geoJsonOutputDirectory = os.path.join(os.path.dirname(vectorSrcFile), rasterFolderBaseName)
    chipSummaryList = createTiledGeoJsonFromSrc(rasterFolderLocation, vectorSrcFile, geoJsonOutputDirectory, rasterTileIndex='',
                              geoJsonPrefix=vectorPrefix, rasterFileExtenstion=rasterFileExtension,
                              rasterPrefixToReplace=rasterPrefix
                              )



    outputCSVFileName = geoJsonOutputDirectory+"OSM_Proposal.csv"
    lT.createCSVSummaryFile(chipSummaryList, outputCSVFileName,
                                replaceImageID=rasterPrefix+"_",
                                pixPrecision=pixPrecision,
                                createProposalsFile=createProposalFile
                                )





