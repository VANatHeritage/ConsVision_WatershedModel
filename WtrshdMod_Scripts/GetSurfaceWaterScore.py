# ----------------------------------------------------------------------------------------
# GetSurfaceWaterScore.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-01-24
# Last Edit: 2017-04-28
# Creator:  Kirsten R. Hazler
#
# Summary:

#
# Usage Tips:

#
# Syntax:  
# ----------------------------------------------------------------------------------------
# Import required modules
import arcpy # provides access to all ArcGIS geoprocessing functions
import os # provides access to operating system funtionality 
import sys # provides access to Python system functions
import traceback # used for error handling
import math
import csv # provides ability to write rows to a text file
import gc # garbage collection
from datetime import datetime as dt # for timestamping

# Check out ArcGIS Spatial Analyst extension license and modules
arcpy.CheckOutExtension("Spatial")
from arcpy.sa import *

# Get path to toolbox, then import it
# Scenario 1:  script is in separate folder within folder holding toolbox
tbx1 = os.path.abspath(os.path.join(sys.argv[0],"../..", "WtrshModTools.tbx"))
# Scenario 2:  script is embedded in tool
tbx2 = os.path.abspath(os.path.join(sys.argv[0],"..", "WtrshModTools.tbx"))
if os.path.isfile(tbx1):
   arcpy.ImportToolbox(tbx1)
   arcpy.AddMessage("Toolbox location is %s" % tbx1)
elif os.path.isfile(tbx2):
   arcpy.ImportToolbox(tbx2)
   arcpy.AddMessage("Toolbox location is %s" % tbx2)
else:
   arcpy.AddError('Required toolbox not found.  Check script for errors.')

outScratchKeep = arcpy.env.scratchGDB # Use this for subset of interim products only
arcpy.AddMessage('Certain scratch products will be stored in %s' % outScratchKeep)
outScratch = "in_memory" # Use this for most scratch products

# Required arguments to be input by user...
in_SrcPts = arcpy.GetParameterAsText(0) 
   # An input feature class or feature layer representing water source points
   # Default: D:\DCR_Work_DellD\ConsVision_WtrshdMod\DataConsolidation\wm_Inputs_Albers.gdb\odw_WaterSrcPts
in_SrcZone = arcpy.GetParameterAsText(1) 
   # An feature class or feature layer representing ODW's designated "Zone 2" catchments
   # Default: D:\DCR_Work_DellD\ConsVision_WtrshdMod\DataConsolidation\wm_Inputs_Albers.gdb\odw_sw_zone2
fld_SrcID = arcpy.GetParameterAsText(2) 
   # The name of the field containing the unique ID used to link source water points and polygons
   # Default: TINWSF_IS_NUMBER
fld_PopEst = arcpy.GetParameterAsText(3)
   # The name of the field containing the estimated population served by the source water point
   # Default: EstPop
in_Snap = arcpy.GetParameterAsText(4)
   # An input raster used for snapping, extent, cell size specs
   # Default: D:\DCR_Work_DellD\ConsVision_WtrshdMod\DataConsolidation\wm_Inputs_Albers.gdb\nlcd2011_lc
out_swScore = arcpy.GetParameterAsText(5) 
   # An output raster representing the Surface Water Score

# Declare some additional parameters

# Create an empty list to store IDs of features that fail to get processed
myFailList = []

# Declare path/name of output data and workspace
drive, path = os.path.splitdrive(out_swScore) 
path, filename = os.path.split(path)
myWorkspace = drive + os.sep + path
myFolder = os.path.abspath(os.path.join(myWorkspace,".."))
out_fname = filename
ts = dt.now().strftime("%Y%m%d_%H%M%S") # timestamp
myFailLog = myFolder + os.sep + 'FailLog56_%s' % ts 
   # text file storing features that fail to get processed

# Set environmental variables
arcpy.env.workspace = myWorkspace # Set the workspace for geoprocessing
arcpy.env.scratchWorkspace = outScratch # Set the scratch workspace for geoprocessing
arcpy.env.overwriteOutput = True # Existing data may be overwritten
arcpy.env.snapRaster = in_Snap # Set the snap raster for proper alignment 
arcpy.env.extent = in_Snap # Set the processing extent to the snap raster

# Set additional variables
zeroRast = outScratchKeep + os.sep + "zeroRast"
maxRast = outScratchKeep + os.sep + "maxRast"
sumRast = outScratchKeep + os.sep + "sumRast"
swMax = myWorkspace + os.sep + "swMax"
swMaxScore = myWorkspace + os.sep + "swDistance_subscore"
swSum = myWorkspace + os.sep + "swSum"
swSumScore = myWorkspace + os.sep + "swDensity_subscore"

try:   
   # Process:  Select (Analysis)
   # Extract the surface water (SW) points
   arcpy.AddMessage("Extracting surface water points...")
   where_clause = "WATER_TYPE_CODE = 'SW'"
   swPts = outScratchKeep + os.sep + 'swPts'
   arcpy.Select_analysis (in_SrcPts, swPts, where_clause)

   # Process:  Create a zero raster as baseline for running score
   arcpy.AddMessage("Creating zero raster...")
   snapRast = Raster(in_Snap)
   zeros = Con(IsNull(snapRast), 0, 0)
   RunningMax = zeros
   RunningSum = zeros
   zeros.save(zeroRast)
   arcpy.AddMessage("Zero raster set as baseline for running scores...")
      
   # Loop through the individual points
   myPoints = arcpy.da.SearchCursor(swPts, [fld_SrcID, fld_PopEst]) # Get the set of features
   for myPt in myPoints: 
   # for each point, do the following...
      try: # Even if one feature fails, script can proceed to next feature
         # Extract the point ID and population estimate
         myID = myPt[0]
         myPop = myPt[1]

         # Add a progress message
         arcpy.AddMessage("Working on Point %s ..." % str(int(myID)))
         
         # Set within-loop variables
         tmpPt = outScratch + os.sep + "tmpPt"
         tmpPtBuff = outScratch + os.sep + "tmpPtBuff"
         tmpPoly = outScratch + os.sep + "tmpPoly"
         tmpPtRaster = outScratch + os.sep + "tmpRaster"
         tmpEucDist = outScratch + os.sep + "tmpEucDist"
         tmpScore = outScratch + os.sep + "tmpScore"
         tmpMax = outScratch + os.sep + "tmpMax"
         tmpSum = outScratch + os.sep + "tmpSum"

         # Process:  Select (Analysis)
         # Create temp feature classes including only the current point and zone polygon
         where_clause = "%s = %s" % (fld_SrcID, str(int(myID)))
         arcpy.Select_analysis (in_SrcPts, tmpPt, where_clause)
         arcpy.Select_analysis (in_SrcZone, tmpPoly, where_clause)

         # Process:  Buffer Point
         # Necessary because not all points actually fall within their corresponding drainage zones!!  This was resulting in null outputs.
         arcpy.Buffer_analysis (tmpPt, tmpPtBuff, 150, "", "", "NONE", "", "PLANAR")
         
         # Process:  Append (point buffer to polygon feature class)
         arcpy.Append_management ([tmpPtBuff], tmpPoly, "NO_TEST", "", "")
         
         # Process:  Polygon to Raster
         arcpy.AddMessage("Creating source raster from point buffer...")
         arcpy.PolygonToRaster_conversion (tmpPtBuff, fld_SrcID, tmpPtRaster, "MAXIMUM_COMBINED_AREA", "", 30)
         
         # Process:  Euclidean Distance
         arcpy.AddMessage("Calculating Euclidean distance...")
         arcpy.env.mask = tmpPoly
         eucDist = EucDistance (tmpPtRaster, "", 30)
         eucDist.save(tmpEucDist)
         
         # Process:  Convert distances to scores
         arcpy.AddMessage("Converting distance to score...")
         arcpy.RasterValToScoreNeg_WtrshModTools(tmpEucDist, 8046.72, 80467.2, tmpScore)
         # Note:  8046.72 meters = 5 miles, which is the distance ODW uses for Zone 1 protection around surface water sources.  
         
         # Update the running scores with the current scores
         # Distance Subscore
         arcpy.AddMessage("Updating running max...")
         arcpy.env.mask = in_Snap
         updateMaxScore = CellStatistics ([tmpScore, RunningMax], "MAXIMUM", "DATA")
         updateMaxScore.save(tmpMax) # for trouble-shooting only
         updateMaxScore.save(maxRast)
         RunningMax = Raster(maxRast)
         
         # Density Subscore
         arcpy.AddMessage("Weighting score by estimate of population served and updating running sum...")
         tmpScore = Raster(tmpScore)/100 * myPop
         updateSumScore = CellStatistics ([tmpScore, RunningSum], "SUM", "DATA")
         updateSumScore.save(tmpSum) # for trouble-shooting only
         updateSumScore.save(sumRast)
         RunningSum = Raster(sumRast)
         
         # Add final progress message
         arcpy.AddMessage("Finished processing point %s ..." % str(int(myID)))  

      except:       
         # Add failure message and append failed feature ID to list
         arcpy.AddMessage("Failed to process point %s ..." % str(int(myID))) 
         myFailList.append(str(int(myID)))

         # Error handling code swiped from "A Python Primer for ArcGIS"
         tb = sys.exc_info()[2]
         tbinfo = traceback.format_tb(tb)[0]
         pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
         msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

         arcpy.AddWarning(msgs)
         arcpy.AddWarning(pymsg)
         arcpy.AddMessage(arcpy.GetMessages(1))

         # Add status message
         arcpy.AddMessage("\nMoving on to the next feature.  Note that the output will be incomplete.")  

   # Process:  Finalize the outputs
   # Sometimes the saving fails for some reason, so add protection against that.
   # Distance Subscore
   try:
      arcpy.AddMessage("Saving running maximum as swDistance_subscore")
      RunningMax.save(swMaxScore)
   except:
      arcpy.AddMessage("Save failed. Saving to scratch instead.")
      swMaxScore = outScratchKeep + os.sep + "swDistance_subscore"
      RunningMax.save(swMaxScore)
   
   # Density Subscore
   try:
      arcpy.AddMessage("Saving running sum as swSum")
      RunningSum.save(swSum)
   except:
      arcpy.AddMessage("Save failed. Saving to scratch instead.")
      swSum = outScratchKeep + os.sep + "swSum"
      RunningSum.save(swSum)   
   try:   
      arcpy.AddMessage("Rescaling sum and saving as swDensity_subscore")
      arcpy.RasterValToScorePos_WtrshModTools(swSum, 1000, 100000, swSumScore)
   except:
      arcpy.AddMessage("Save failed. Saving to scratch instead.")
      swSumScore = outScratchKeep + os.sep + "swDensity_subscore"
      arcpy.RasterValToScorePos_WtrshModTools(swSum, 1000, 100000, swSumScore)
  
   FinScore = CellStatistics ([swMaxScore, swSumScore], "MEAN", "DATA")
   try:
      FinScore.save(out_swScore)
   except:
      arcpy.AddMessage("Save failed. Saving to scratch instead.")
      out_swScore = outScratchKeep + os.sep + "out_swScore"
      RFinScore.save(out_swScore) 
   
   # Once the script as a whole has succeeded, let the user know if any individual 
   # features failed
   if len(myFailList) == 0:
      arcpy.AddMessage("All features successfully processed")
   else:
      arcpy.AddWarning("Output is not accurate, because processing failed for the following features: " + str(myFailList))
      arcpy.AddWarning("See the log file " + myFailLog)
      with open(myFailLog, 'wb') as csvfile:
         myCSV = csv.writer(csvfile)
         for value in myFailList:
            myCSV.writerow([value])

   
   
# This code block determines what happens if the "try" code block fails
except:
   # Error handling code swiped from "A Python Primer for ArcGIS"
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = "ARCPY ERRORS:\n" + arcpy.GetMessages(2) + "\n"

   arcpy.AddError(msgs)
   arcpy.AddError(pymsg)
   arcpy.AddMessage(arcpy.GetMessages(1))
 
# Additional code to run regardless of whether the script succeeds or not










