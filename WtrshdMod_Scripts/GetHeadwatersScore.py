# ------------------------------------------------------------------------------------------
# GetHeadwatersScore.py
# Version:  ArcGIS 10.2 / Python 2.7
# Creation Date:  2015-07-14
# Last Edit:  2015-11-20
# Creator:  Kirsten R. Hazler and Claire McCartney
#
# Summary:  Creates a "Headwaters Score" raster from the catchments of headwater stream segments.
#           Anything within the catchment area of a headwater stream reach receives a score of 100;
#           everything else gets a score of 0.
#
#           Each basin represented by the input directories is processed separately.  The final score
#           rasters will need to be mosaicked in a separate step to produce a seamless product.
#
# Usage Tips:
#           For each given input directory, there must be the following subdirectories:
#              NHDPlusAttributes
#              NHDPlusCatchment
#              NHDSnapshot
# ------------------------------------------------------------------------------------------

# Import required standard modules
import arcpy, os, sys, shutil, traceback
from datetime import datetime
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")

# Script arguments to be input by user
in_Dir = arcpy.GetParameterAsText(0) # Input NHDPlus directory(ies) to process
in_Snap = arcpy.GetParameterAsText(1) # Input snap raster for final product
in_Border = arcpy.GetParameterAsText(2) # Polygon feature outlining area to process
                                        # Use the HUC8 "HydroClip" feature
out_scratch = arcpy.GetParameterAsText(3) # Geodatabase to hold intermediate products
out_GDB = arcpy.GetParameterAsText(4) # Geodatabase to hold final products
ProcLogFile = arcpy.GetParameterAsText(5) # Text file to keep track of processing results

# Environment settings and derived variables
arcpy.env.overwriteOutput = True
arcpy.env.snapRaster = in_Snap
arcpy.env.cellSize = in_Snap
CellSize = arcpy.GetRasterProperties_management(in_Snap, "CELLSIZEX")
CellSize = int(CellSize[0]) # This step is necessary to convert a result object to a numeric value
outCS = arcpy.Describe(in_Snap).spatialReference

# Temporary files.  Each will be overwritten when loop returns to the beginning.
tmpStreams = out_scratch + os.sep + 'tmpStreams'
   # This is the temporary feature class to store the selected streams
tmpHdCatch = out_scratch + os.sep + 'tmpHdCatch'
   # This is the temporary feature class to store the headwater catchments
prjHdCatch = out_scratch + os.sep + 'prjHdCatch'
   # This is the temporary feature class to store the projected headwater catchments
tmpCatchRast = out_scratch + os.sep + 'tmpCatchRast'
   # This is the temporary raster to store the headwater catchments

arcpy.AddMessage("Intermediate outputs will be stored in your scratch geodatabase, %s" %out_scratch)
arcpy.AddMessage("Final products will be stored in your specified output geodatabase, %s" %out_GDB)

# Create and open a log file.
# If this log file already exists, it will be overwritten.  If it does not exist, it will be created.
Log = open(ProcLogFile, "w+")
FORMAT = '%Y-%m-%d %H:%M:%S'
timestamp = datetime.now().strftime(FORMAT)
Log.write("Process logging started %s" % timestamp)

for d in in_Dir.split(';'):
   try:
      # Set up the variables
      basename = os.path.basename(d)
         # This will yield the final directory name, e.g., "NHDPlus02"
      id = basename.replace('NHDPlus', '')
         # This yields an ID by stripping off the string "NHDPlus" from the basename
      streams = d + os.sep + 'NHDSnapshot' + os.sep + 'Hydrography' + os.sep + 'NHDFlowline.shp'
         # This is the path to the input streams from your input directory
      catchments = d + os.sep + 'NHDPlusCatchment' + os.sep + 'Catchment.shp'
         # This is the path to the catchments from your input directory
      att_tab = d + os.sep + 'NHDPlusAttributes' + os.sep + 'PlusFlowlineVAA.dbf'
         # This is the path to the relevant attribute table from your input directory
      msg = 'Working on basin %s...' % id
         # This lets the user know what basin is currently being processed
      arcpy.AddMessage(msg)
      Log.write('\n' + msg)

      # Select the streams intersecting in_Border, and save them to a temp feature class
      arcpy.MakeFeatureLayer_management(streams, "streams_lyr")
      arcpy.SelectLayerByLocation_management("streams_lyr", "intersect", in_Border)
      arcpy.CopyFeatures_management("streams_lyr", tmpStreams)
         ### Previously you had the output as "temp_streams".  
         ### You needed to specify the exact path for the output, which has now been defined above the loop.

      # Join the StartFlag attribute from att_tab to the temp streams
      arcpy.JoinField_management(tmpStreams, "COMID", att_tab, "ComID", "StartFlag")
         ### This was missing the linking field for the join table.  
         ### Note that "COMID" vs "ComID" is intentional due to slightly different field names in different tables.

      # Select the temp streams where StartFlag = 1.  These are the headwater reaches.
      ### You don't need the geometry at this point, just a table.
      where_clause = '"StartFlag" = 1'
      arcpy.MakeTableView_management (tmpStreams, "hdwtrs_tab", where_clause)
         ### You don't need a separate SelectLayerByAttribute step!

      # Extract the subset of catchments corresponding to the headwaters, based on the COMID field.
      arcpy.MakeFeatureLayer_management(catchments, "catch_lyr")
      arcpy.AddJoin_management ("catch_lyr", "FEATUREID", "hdwtrs_tab", "COMID", "KEEP_COMMON")
         ### This should return only the catchments with matching headwaters.  
         ### Note that there is no COMID field in the catchment layer.  The corresponding field is FEATUREID.
         ### Note that when this type of join is done, the resulting output field names include the name
         ### of the source tables.  Thus for example, COMID becomes tmpStreams_COMID.

      # Project the headwater catchment layer and add a score field
      ### Previously the layer was just copied, but it needed to be projected. 
      ### Adding and calculating the score field is also new.
      arcpy.CopyFeatures_management("catch_lyr", tmpHdCatch)
      arcpy.Project_management(tmpHdCatch, prjHdCatch, outCS)
         ### Output coordinate system (outCS) is taken from the snap raster, above the loop.
      arcpy.AddField_management (prjHdCatch, "HeadScore", "SHORT")
      arcpy.CalculateField_management (prjHdCatch, "HeadScore", "100", "PYTHON_9.3")
      
      # Convert headwater catchments to a temp raster, using HeadScore field for catchments
      arcpy.PolygonToRaster_conversion (prjHdCatch, "HeadScore", tmpCatchRast, "MAXIMUM_COMBINED_AREA", "HeadScore", CellSize)
         ### Cell size was obtained from snap raster above loop
         ### Replaced FeatureToRaster tool with PolygonToRaster
      # Set the null cells in the raster to the value 0
      finCatch = Con(IsNull(tmpCatchRast) == 1, 0, tmpCatchRast)
      
      # Save out the final raster
      outRast = out_GDB + os.sep + 'HdCatch_' + id
      finCatch.save(outRast)
      
      msg = 'Successfully processed basin %s...' % id
      arcpy.AddMessage(msg)
      Log.write('\n' + msg)

   except:
      # Error handling code swiped from "A Python Primer for ArcGIS"
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
      msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

      arcpy.AddWarning('Failed to fully process basin %s' %id)
      arcpy.AddWarning(msgs)
      arcpy.AddWarning(pymsg)
      arcpy.AddMessage(arcpy.GetMessages(1))

      print msgs
      print pymsg
      print arcpy.AddMessage(arcpy.GetMessages(1))
      Log.write('\nFailed to fully process basin %s' %id)
      Log.write('\n' + msgs)
      Log.write('\n' + pymsg)

timestamp = datetime.now().strftime(FORMAT)
Log.write("\nProcess logging ended %s" % timestamp)
Log.close()

























