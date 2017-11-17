import geopandas as gpd
from shapely import geometry
import numpy as np
import osmnx as ox
import os
import pandas as pd
from shapely import wkt
import csv





def deduplicateRoadsCSV(csvFileName, verbose=False, testOnly=False, cleanWKT_Pix=True):
    
    tmpCSVDF = pd.read_csv(csvFileName)
    tmpCSVGDF = gpd.GeoDataFrame(tmpCSVDF, geometry=[wkt.loads(wkt_str) for wkt_str in tmpCSVDF['WKT_Pix'].values])
    
    if cleanWKT_Pix:
        tmpCSVGDF['WKT_Pix'] = [wkt.dumps(geom, output_dimension=2, rounding_precision=2) for geom in tmpCSVGDF.geometry.values]
    
    uniqueNamesList = list(set(tmpCSVGDF['ImageId'].values))
    verbose=False
    rowToReplaceList=[]
    totalBadRowList=[]
    finalListGDFList = []
    badGDFList = []
    for imageId in uniqueNamesList:
        smallGDF = tmpCSVGDF[tmpCSVGDF['ImageId']==imageId].copy()

        smallGDF = deduplicateEdgeGDF(smallGDF, badRowsList=[], verbose=verbose)
        finalListGDFList.append(smallGDF)
    
    if verbose:
        print("done")

            
    return finalListGDFList


def deduplicateRoadsCSVTest(csvFileName, verbose=False, testOnly=False):
    
    tmpCSVDF = pd.read_csv(csvFileName)
    tmpCSVGDF = gpd.GeoDataFrame(tmpCSVDF, geometry=[wkt.loads(wkt_str) for wkt_str in tmpCSVDF['WKT_Pix'].values])

    
    uniqueNamesList = list(set(tmpCSVGDF['ImageId'].values))
    rowToReplaceList=[]
    totalBadRowList=[]
    finalListGDFList = []
    badGDFList = []
    for imageId in uniqueNamesList:
        smallGDF = tmpCSVGDF[tmpCSVGDF['ImageId']==imageId].copy()
                 
        badRowList = detectDuplicateEdgeGDF(smallGDF, verbose=verbose)
        if badRowList:
            print("# of Duplicate edges = {}".format(len(badRowList)))
        finalListGDFList.append(smallGDF)
    
    if verbose:
        print("done")

            
    return finalListGDFList



def writeListOfDFToCSV(csvFileName, finalListGDFList):
    with open(csvFileName, 'w') as csvfile:
        writerTotal = csv.writer(csvfile, delimiter=',', lineterminator='\n')
        
        writerTotal.writerow(['ImageId', 'WKT_Pix'])
        
        for finalGDF in finalListGDFList:
            for idx, row in finalGDF.iterrows():
                if row.geometry.geom_type=='LineString':
                    writerTotal.writerow([row['ImageId'], row['WKT_Pix']])
                else:
                    print(row.geometry.geom_type)
                    for lineItem in row.geometry:
                        writerTotal.writerow([row['ImageId'], lineItem.wkt])
                    
        
        
    

def detectDuplicateEdgeGDF(smallGDF, verbose=False):
    # returns list of rows that are duplicates in GDF.  If list is empty, no duplicates exost
    badRowList = []

    # Iterate through rows
    for idx, row in smallGDF.iterrows():
        #remove selve entry from GDF
        tmpGDF = smallGDF[smallGDF.index!=idx]     
        
        if inspectRow(row, verbose=False):
            badRow = row.copy()
            badRowList.append(badRow)
        else:
            tmpLineStringTotal = row['geometry']

            # extract line strings from row split multistrings into linestrings if they exost
            tmpLineStringList = []
            if tmpLineStringTotal.geom_type=='LineString':
                tmpLineStringList.append(tmpLineStringTotal)

            else:
                for tmpLine in tmpLineStringTotal:
                    tmpLineStringList.append(tmpLineStringTotal)


            # For each line check if linestring has any overlap with other linestrings if so return row with overlap
            for tmpLine in tmpLineStringList:

                interSectLength = np.max(tmpGDF.intersection(tmpLine).length)
                # if overlap exists add row to badRowList
                if  0.00 < interSectLength:
                    if verbose:
                            print("Exploding overlaps")
                            print("missed connection minDistance ={} , wkt = {}".format(interSectLength,
                                        tmpLine))


                    badRow = row.copy()
                    badRowList.append(badRow)

    if verbose:
        
        print("Num Bad Rows = {}".format(len(badRowList)))
    
    
    return badRowList


def deduplicateEdgeGDF(smallGDF, badRowsList=[], verbose=False):
    
    #if #badRowsListDF not specified detectBadRows
    if not badRowsList:
        badRowsList = detectDuplicateEdgeGDF(smallGDF, verbose=verbose)
    
    if badRowsList:
        badRowsListDF = gpd.GeoDataFrame(badRowsList)
        lineList=[]
        if verbose:
            print("Original GDF Shape: {}".format(smallGDF.shape))
        
        # iterate through bad rows and explode
        for idx, rowToReplace in badRowsListDF.iterrows():
            
            # drop row
            smallGDF = smallGDF.drop(idx)
            
            newRowList = explodeRow(rowToReplace, verbose=False)
            
            #append row to GDF
            smallGDF = appendRowToGDF(smallGDF, newRowList)
            
            
        # remove duplicateGeometries
        dedupGDF = removeDuplicateGeometries(smallGDF, verbose=False)  
        
        if verbose:
            print("Exploded GDF Shape: {}".format(dedupGDF.shape))
        
        return dedupGDF
    
    else:
    
        if verbose:
            print("No Errors Detected")
        return smallGDF
    

def explodeLineString(lineStringGeom, verbose=False):
    coordList = list(lineStringGeom.coords)
    lineList = []
    for idxa in range(len(coordList)-1):
                lineList.append(geometry.LineString([coordList[idxa],
                                                     coordList[idxa+1]
                                                    ]
                                                   )
                               )
    if verbose:
        print("index = {},  Number of Exploded Lines created: {}".format(idx, len(lineList)))

    return lineList

def explodeRow(rowToReplace, verbose=False):

    newRowList = []
    lineList = explodeLineString(rowToReplace.geometry, verbose=verbose)
    


    
    for lineItem in lineList:
        tmpRow = rowToReplace.copy()
        tmpRow['geometry']=lineItem
        newRowList.append(tmpRow)
        
    
    return newRowList

def appendRowToGDF(srcGDF, newRowList):

    tmpGDF = srcGDF.copy()
    
    for newRow in newRowList:
        tmpGDF = tmpGDF.append(newRow)
        
    return tmpGDF
        
def removeDuplicateGeometries(srcGDF, verbose=False):
    
    # iterage through rows to remove duplicate:
    newGDF = srcGDF.reset_index().copy()
    newGDF['dupIdx'] = 0

    for idx, row in newGDF.iterrows():
        tmpLineStringTotal = row.geometry
        if verbose:
            print(np.max(newGDF.intersection(tmpLineStringTotal).length))
        newGDF['dupIdx'].loc[newGDF.intersection(tmpLineStringTotal).length>0]=idx


    newGDF = newGDF.drop_duplicates(subset='dupIdx')
    newGDF['WKT_Pix'] = [wkt.dumps(geom, output_dimension=2, rounding_precision=2) for geom in newGDF.geometry.values]
    newGDF = newGDF.drop('dupIdx', axis=1)

    return newGDF

def inspectRow(rowToInspect, verbose=False):
    geomList = inspectLine(rowToInspect.geometry)
    
    
    return geomList    
    
    
    
    
def inspectLine(lineStringGeom, verbose=False):
    explodedLineString = explodeLineString(lineStringGeom)
    testGDF = gpd.GeoDataFrame(geometry=explodedLineString)
    newGDF = removeDuplicateGeometries(testGDF, verbose=False)
    
    if newGDF.shape[0] != testGDF.shape[0]:
        
        if verbose:
            print("overlap in LineString")
    
        return list(newGDF.geometry.values)
    else:
        
        return []
    