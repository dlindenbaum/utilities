import geopandas as gpd
import geopandas_osm
from osmnx import core
from shapely.geometry import Polygon


def createPolygonShapeFileFromOSM(polyBounds, pointOfInterestList, outVectorFile='', debug=True):

    gdfOSM = gpd.GeoDataFrame([])
    for pointOfInterestKey in pointOfInterestList.keys():

        gdfPOITemp = core.osm_net_download(polygon=polyBounds,
                                           infrastructure='node["{}"]'.format(pointOfInterestKey)
                                           )
        gdfOSM.append(gdfPOITemp)

        gdfPOITemp = core.osm_net_download(polygon=polyBounds,
                                           infrastructure='way["{}"]'.format(pointOfInterestKey)
                                           )

        gdfOSM.append(gdfPOITemp)

        #gdfPOITemp = geopandas_osm.osm.query_osm('way', polyBounds, recurse='down',
        #                                         tags='{}'.format(pointOfInterestKey))

        gdfOSM.append(gdfPOITemp)

        #gdfPOITemp = geopandas_osm.osm.query_osm('node', polyBounds, recurse='down',
        #                                         tags='{}'.format(pointOfInterestKey))

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


    return gdfOSM

    #gdfFinal = createPolygonShapeFileGPD(pointOfInterestList, gdfOSM, outVectorFile=outVectorFile)
