import sys
sys.path.extend(['/Users/dlindenbaum/cosmiQGit/spaceNetUtilities_DaveL/python'])
from spaceNetUtilities import evalToolsGPD as eT

import geopandas as gpd

srcTruthVector = '/Users/dlindenbaum/dataStorage/spaceNetPrivate_Truth/AOI_2_Vegas/srcData/vectorData/Vegas_Footprints.shp'
srcTestVector  = '/Users/dlindenbaum/dataStorage/xd_Vegas/15OCT22183656-S2AS_R1C7-056155973080_01_P001.shp'


truthDF = gpd.read_file(srcTruthVector)
testDF = gpd.read_file(srcTestVector)

prop_polysPoly = testDF.geometry.values
sol_polysPoly = truthDF.geometry.values


truthIndex = truthDF.sindex

eval_function_input_list = [['ImageId', prop_polysPoly, sol_polysPoly, truthIndex]]
print('Starting Eval')
resultList = eT.evalfunction(eval_function_input_list[0])
