# KfactToScores.py
# Version:  Python 2.7.5
# Creation Date: 2015-07-26
# Last Edit: 2017-01-26
# Creator:  Roy Gilb/Kirsten Hazler
#
# Summary: Calculates scores between 0 - 100 for K-factor values.
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
   # Input table containing kFactor values
kFact = arcpy.GetParameterAsText(1) 
   # Name of existing field(s) containing k-values to be converted to scores

# Set overwrite to be true.         
arcpy.env.overwriteOutput = True

fldList = [field.name for field in arcpy.ListFields(in_Tab)]

fld_Scores = kFact + '_score'
   
#Check the input table for the existence of the scores field.  If it doesn't exist, create it.  
if fld_Scores in fldList:
   arcpy.AddMessage("%s field already exists. Existing score values will be overwritten..." %fld_Scores)
else:
   arcpy.AddMessage("Creating new scores field: %s" %fld_Scores)
   #Add K-factor scores field
   arcpy.AddField_management(in_Tab, fld_Scores, "LONG")

cMin = 0
cMax = 0.55

# Calculate fld_Scores based on the correct equation
# For all K-factor values, scores should increase with increasing K-factor values, so we use the positive function
expression = "outScore(!%s!,%s, %s)" %(kFact, cMin, cMax)
codeblock = """def outScore(kF, minThresh, maxThresh):
   if float(kF) < minThresh:
      score = 0
   elif float(kF) > maxThresh:
      score = 100
   else:
      score = 100*(float(kF) - minThresh)/(maxThresh - minThresh)
   return score"""
arcpy.AddMessage('Calculating field...')
arcpy.CalculateField_management (in_Tab, fld_Scores, expression, 'PYTHON', codeblock)








