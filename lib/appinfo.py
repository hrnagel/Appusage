#!/usr/bin/env python3

import os
from fnmatch import fnmatch
import configparser

softwareDirs        = []
softwareDirPatterns = []
mappings            = []

# ******************************************************************************

def init(config, section, rootDir):
  global softwareDirs, softwareDirPatterns, mappings

  # Read the list of directories where software is installed
  if config.has_option(section, "softwareDirs"):
    list = config.get(section, "softwareDirs").strip().split(',')
    for item in list:
      softwareDir = item.strip()

      # Create the software directory pattern
      if not softwareDir.endswith('/'):
        softwareDir += '/'
      softwareDirPattern = softwareDir + '*'

      softwareDirs.append(softwareDir)
      softwareDirPatterns.append(softwareDirPattern)

  # Read the categories file with a list of mappings of regular patterns
  # to application names.
  cfgFile = rootDir + 'etc/categories'
  if os.path.exists(cfgFile):
    for line in open(cfgFile):
      # Remove the ending newline character
      line = line.rstrip('\n')

      # Split the line into tab separated words
      words = line.split('\t')
      if len(words) < 2: # Skip empy lines
        continue
      
      # Multiple tabs separate the pattern and the appname, so store 
      # the first and the last word in a tuple
      mapping = (words[0].strip(), words[len(words)-1].strip())

      mappings.append(mapping)

# ******************************************************************************

# Finds the name of the application to which the executable belongs
def getAppName(path):
  global softwareDirs, softwareDirPatterns, mappings

  # Search the list with application names
  for pattern, app in mappings:
    if fnmatch(path, pattern):
      return app

  # If not there, then use the directory name in the main software directory
  for i in range(len(softwareDirPatterns)):
    if fnmatch(path, softwareDirPatterns[i]):
      return path.replace(softwareDirs[i], '').split('/')[0]

  return "Unknown"

# ******************************************************************************

