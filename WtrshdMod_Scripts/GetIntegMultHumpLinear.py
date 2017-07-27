# ----------------------------------------------------------------------------------------
# GetIntegMultHumpLinear.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-05-15
# Last Edit: 2017-05-15
# Creator:  Kirsten R. Hazler
#
# Summary:
# Given a Watershed Integrity Score raster and specific X and Y coordinates, derives a prioirty multiplier raster based on the assumption that priority relates to integrity in a hump-shaped relationship with truncation at extremes and linear functions between inflection points.
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

outScratch = arcpy.env.scratchGDB # Use this for subset of interim products only
arcpy.AddMessage('Certain scratch products will be stored in %s' % outScratch)

# Required arguments to be input by user...
in_Integ = arcpy.GetParameterAsText(0) 
   # An input raster representing the Watershed Integrity Score.  Must have values ranging from 0 to 100.
Y = arcpy.GetParameter(1) 
   # Value for Y-coordinate representing minimum priority value.
X1 = arcpy.GetParameter(2) 
   # Value for X-coordinate at first inflection point
X2 = arcpy.GetParameter(3) 
   # Value for X-coordinate at second inflection point
X3 = arcpy.GetParameter(4) 
   # Value for X-coordinate at third inflection point
X4 = arcpy.GetParameter(5) 
   # Value for X-coordinate at fourth inflection point
out_Mult = arcpy.GetParameterAsText(6) 
   # An output raster representing the priority multiplier.

# Declare some additional parameters

# Set environmental variables
arcpy.env.scratchWorkspace = outScratch # Set the scratch workspace for geoprocessing
arcpy.env.overwriteOutput = True # Existing data may be overwritten

# Derive slopes and intercepts for linear functions
Slope1 = (100 - Y)/(X2 - X1)
arcpy.AddMessage('Slope 1 is %s' %str(Slope1))
Int1 = 100 - Slope1*X2
arcpy.AddMessage('Intercept 1 is %s' %str(Int1))
Slope2 = (100 - Y)/(X3 - X4)
arcpy.AddMessage('Slope 2 is %s' %str(Slope2))
Int2 = 100 - Slope2*X3
arcpy.AddMessage('Intercept 2 is %s' %str(Int2))

# Create temporary rasters from linear functions
Rast1 = Slope1 * Raster(in_Integ) + Int1
outRast1 = outScratch + os.sep + 'Rast1'
Rast1.save(outRast1)
arcpy.AddMessage('First temp raster saved to %s' % outRast1)
Rast2 = Slope2 * Raster(in_Integ) + Int2
outRast2 = outScratch + os.sep + 'Rast2'
Rast2.save(outRast2)
arcpy.AddMessage('Second temp raster saved to %s' % outRast2)

# Create final output raster
Integ = Raster(in_Integ)
outRast = Con((Integ <= X1) | (Integ >= X4),50,Con((Integ >= X2)&(Integ <= X3),100,Con(Integ < X2,Rast1, Rast2)))
outRast.save(out_Mult)

