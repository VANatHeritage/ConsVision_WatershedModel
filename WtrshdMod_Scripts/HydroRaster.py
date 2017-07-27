# ------------------------------------------------------------------------------------------
# HydroRaster.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date:  2015-07-22
# Last Edit:  2016-02-09
# Creator:  Kirsten R. Hazler
#
# Summary:  For a set of National Hydrography Dataset (NHD) geodatabases, selects a subset of 
#           features to rasterize based on a table of FCodes (NHD codes denoting feature type).
#           Selected features are coded as 1 in the output raster, with everything else null.
#           
#           Each NHD geodatabase is processed separately.  The final rasters will need to be 
#           mosaicked in a separate step to produce a seamless product.
#
# Usage Tips:
#
# ------------------------------------------------------------------------------------------

# Import required modules
import arcpy
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")
import os # provides access to operating system functionality such as file and directory paths
import sys # provides access to Python system functions
import traceback # used for error handling
import gc # garbage collection
from datetime import datetime # for time-stamping

# Script arguments to be input by user
inGDB = arcpy.GetParameterAsText(0) # Input set of NHD geodatabases to process
inFCodes = arcpy.GetParameterAsText(1) # Input table containing FCodes and a field for selecting them
   # Default:  H:\Backups\DCR_Work_DellD\ConsVision_WtrshdMod\DataConsolidation\wm_Inputs_Albers.gdb\tb_nhdFCodes
inSelFld = arcpy.GetParameterAsText(2) # Binary field indicating which records to select for FCodes
   # Default:  WtrshdMod_Water
inSnap = arcpy.GetParameterAsText(3) # A raster to be used for snapping and setting output cell size
   # Default: H:\Backups\DCR_Work_DellD\ConsVision_WtrshdMod\DataConsolidation\wm_Inputs_Albers.gdb\nlcd2011_lc
scratchGDB = arcpy.GetParameterAsText(4) # Geodatabase to hold intermediate products
outGDB = arcpy.GetParameterAsText(5) # Geodatabase to hold final products

# Additional script parameters and environment settings
arcpy.env.overwriteOutput = True # Set overwrite option so that existing data may be overwritten
arcpy.env.snapRaster = inSnap # Make sure outputs align with snap raster
arcpy.env.extent = 'MAXOF' # Make sure outputs are not truncated
outCS = arcpy.Describe(inSnap).SpatialReference
if not scratchGDB:
   scratchGDB = "in_memory"

# Validate that snap raster has NAD83 datum
if outCS.GCS.Name != 'GCS_North_American_1983':
   arcpy.AddWarning('NHD data use the NAD83 datum, but your snap raster has a different datum.')
   arcpy.AddWarning('Proceeding, but the resulting raster may be suspect.')

# Generate a query expression to select desired features from NHD
CodeList = list()
where_clause = '"%s" = 1' %(inSelFld) # The initial record selection expression
with arcpy.da.SearchCursor(inFCodes, 'FCode', where_clause) as FCodes:
   for code in FCodes:
      CodeList.append(code[0])
CodeList = str(CodeList).replace('[', '(').replace(']',')')
where_clause = '"FCode" in %s' % CodeList # The final record selection expression

# Loop through the geodatabases
for gdb in inGDB.split(';'):
   try:
      # Set up some variables
      huc4 = os.path.basename(gdb)[4:8]
      nhdWB = gdb + os.sep + 'Hydrography' + os.sep + 'NHDWaterbody'
      nhdArea = gdb + os.sep + 'Hydrography' + os.sep + 'NHDArea'
      nhdFline = gdb + os.sep + 'Hydrography' + os.sep + 'NHDFlowline'

      arcpy.AddMessage('Working on watershed %s...' % huc4)

      # Merge the Area and Waterbody feature classes
      arcpy.AddMessage('Merging polygon features...')
      mergePFC = scratchGDB + os.sep + 'nhdMergedPolys' + huc4
      fldMap = "FCode \"FCode\" true true false 4 Long 0 0 ,First,#,%s,FCode,-1,-1,%s,FCode,-1,-1" %(nhdArea, nhdWB)
      arcpy.Merge_management ([nhdWB, nhdArea], mergePFC, fldMap)

      # Create subsets of polygon and line features based on FCodes, and add a 'Burn' field
      arcpy.AddMessage('Subsetting polygon features...')
      selectPFC = scratchGDB + os.sep + 'nhdSelectedPolys' + huc4
      arcpy.Select_analysis(mergePFC, selectPFC, where_clause)
      arcpy.AddField_management (selectPFC, 'Burn', 'SHORT')
      arcpy.CalculateField_management (selectPFC, 'Burn', 1, 'PYTHON')

      arcpy.AddMessage('Subsetting line features...')
      selectLFC = scratchGDB + os.sep + 'nhdSelectedLines' + huc4
      arcpy.Select_analysis(nhdFline, selectLFC, where_clause)
      arcpy.AddField_management (selectLFC, 'Burn', 'SHORT')
      arcpy.CalculateField_management (selectLFC, 'Burn', 1, 'PYTHON')

      # Project the subsets to match the snap raster's coordinate system
      arcpy.AddMessage('Projecting polygon features...')
      burnPFC = scratchGDB + os.sep + 'nhdBurnPolys' + huc4
      arcpy.Project_management (selectPFC, burnPFC, outCS)

      arcpy.AddMessage('Projecting line features...')
      burnLFC = scratchGDB + os.sep + 'nhdBurnLines' + huc4
      arcpy.Project_management (selectLFC, burnLFC, outCS)
      
      # Get polygon centroids to ensure even the smallest features get rasterized, and add a 'Burn' field
      arcpy.AddMessage('Getting polygon centroids...')
      burnCntr = scratchGDB + os.sep + 'nhdBurnCntr' + huc4
      arcpy.FeatureToPoint_management (burnPFC, burnCntr, "INSIDE")
      arcpy.AddField_management (burnCntr, 'Burn', 'SHORT')
      arcpy.CalculateField_management (burnCntr, 'Burn', 1, 'PYTHON')

      # Rasterize the features
      arcpy.AddMessage('Rasterizing polygons...')
      polyburnRD = scratchGDB + os.sep + 'rdPolyBurn' + huc4
      arcpy.PolygonToRaster_conversion (burnPFC, 'Burn', polyburnRD, "MAXIMUM_COMBINED_AREA", 'None', inSnap)
      
      arcpy.AddMessage('Rasterizing polygon centroids...')
      cntrburnRD = scratchGDB + os.sep + 'rdCntrBurn' + huc4
      arcpy.PointToRaster_conversion (burnCntr, 'Burn', cntrburnRD, "MOST_FREQUENT", "", inSnap)

      arcpy.AddMessage('Rasterizing lines...')
      lineburnRD = scratchGDB + os.sep + 'rdLineBurn' + huc4
      arcpy.PolylineToRaster_conversion(burnLFC, 'Burn', lineburnRD, "MAXIMUM_COMBINED_LENGTH", 'None', inSnap)

      # Combine the rasters
      Feats2Burn = [lineburnRD, polyburnRD, cntrburnRD]
      HydroRaster = CellStatistics(Feats2Burn, "MAXIMUM", "DATA")
      HydroRaster.save(outGDB + os.sep + 'rdHydro' + huc4)

      arcpy.AddMessage('Completed watershed %s.  The output raster is %s.' % (huc4, HydroRaster))

   except:
      arcpy.AddWarning('Failed to process watershed %s.' % huc4)

      # Error handling code swiped from "A Python Primer for ArcGIS"
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
      msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

      arcpy.AddWarning(msgs)
      arcpy.AddWarning(pymsg)
      arcpy.AddMessage(arcpy.GetMessages(1))




