# RescalePollutantsToScores.py
# Version:  Python 2.7.5
# Creation Date: 2015-07-26
# Last Edit: 2017-04-26
# Creator:  Roy Gilb/Kirsten Hazler
#
# Summary: Calculates scores between 0 - 100 for NSPECT coefficients.
#     
# Usage Tips: 
# When running this tool in ArcMap, it appears that the field has not been created.  But it HAS.  You will only see it if you close out ArcMap and reopen.  ANNOYING!  Better to run it within ArcCatalog.
#
# Syntax:
# ----------------------------------------------------------------------------------------

# Import required modules
import arcpy
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")
import os # provides access to operating system funtionality such as file and directory paths
import sys # provides access to Python system functions
import traceback # used for error handling
from datetime import datetime # for time-stamping

# Script arguments to be input by user
in_Tab = arcpy.GetParameterAsText(0) 
   # Input table containing NSPECT coefficients
fld_Coeff = arcpy.GetParameterAsText(1) 
   # Name of existing field(s) containing coefficients to be converted to scores

# Set overwrite to be true.         
arcpy.env.overwriteOutput = True

fldList = [field.name for field in arcpy.ListFields(in_Tab)]

# Loop through the coefficient fields
for fld in fld_Coeff.split(';'):
   # Specify name for new field to contain scores corresponding to input coefficients
   fld_Scores = fld + '_score'
   
   # Check the input table for the existence of the scores field.  If it doesn't exist, create it.  
   if fld_Scores in fldList:
      arcpy.AddMessage("%s field already exists. Existing score values will be overwritten..." %fld_Scores)
   else:
      arcpy.AddMessage("Creating new scores field: %s" %fld_Scores)
      arcpy.AddField_management(in_Tab, fld_Scores, "DOUBLE")

   # Get the minimum and maximum values from fld_Coeff.  Store these as variables cMin and cMax.
   # Create a list of values
   vals = [row.getValue(fld) for row in arcpy.SearchCursor(in_Tab)]
   # Filter out the nulls.  
   arcpy.AddMessage('unfiltered: ' + str(vals))
   vals = filter(lambda a: a != None, vals)
   cMin = min(vals)
   cMax = max(vals)

   # Calculate fld_Scores based on the correct equation
   # For all pollutant values, scores should decrease with increasing pollution, so we use the negative function
   expression = "outScore(!%s!,%s, %s)" %(fld, cMin, cMax)
   codeblock = """def outScore(coeff, minThresh, maxThresh):
      if coeff == None:
         score = None
      elif coeff < minThresh:
         score = 100
      elif coeff > maxThresh:
         score = 0
      else:
         score = 100*(maxThresh - coeff)/(maxThresh - minThresh)
      return score"""
   arcpy.AddMessage('Calculating field...')
   arcpy.CalculateField_management (in_Tab, fld_Scores, expression, 'PYTHON', codeblock)







