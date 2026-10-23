#!/usr/bin/env python3

import os, subprocess
import configparser

userQueryMethod = 0   # 0 = pinky, 1 = user names file
userNamesFile   = ""

def init(config, section):
  global userQueryMethod, userNamesFile

  ok = 1

  if config.has_option(section, "userNamesFile"):
    userNamesFile = config.get('Appusage', 'userNamesFile').strip()
    if os.path.exists(userNamesFile):
      userQueryMethod = 1
    else:
      print("Error: userNamesFile does not exist")
      ok = 0

  return ok

# ******************************************************************************

def getNameFromPinky(user):
  cmd = "pinky %s | sed -E 's/\S+\s+//' | cut -c1-19" % (user)

  result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
  lines = result.stdout.strip().split('\n')

  if len(lines) == 1:
    name = "-"
  else:
    try:
      name = lines[1].strip()
    except Exception:
      name = "-"

  return name

# ******************************************************************************

userNames = dict()

# Read the user name file
userNamesRead = 0
def getNameFromFile(user):
  global userNamesFile, userNames, userNamesRead

  if not userNamesRead:
    name  = ""
    uname = ""
    for line in open(userNamesFile):
      if line.startswith("name ="):
        line_split = line.split('=')
        if len(line_split) != 2:
          continue
        name = line_split[1].strip().strip('"')
    
      if line.startswith("uname ="):
        line_split = line.split('=')
        if len(line_split) != 2:
          continue
        uname = line_split[1].strip().strip('"')

      if name != "" and uname != "":
        userNames[uname] = name
        name = ""
        uname = ""

    userNamesRead = 1

  if user in userNames:
    return userNames.get(user) 
  else:
    return ""

# ******************************************************************************

# Get the name of the user
def getName(uname):
  global userQueryMethod

  name = ""
  if userQueryMethod==0:
    name = getNameFromPinky(uname)
  else:
    name = getNameFromFile(uname)

  try:
    str = name.encode('latin1').decode('utf8')
  except Exception:
    str = name.encode('latin1', 'ignore').decode('cp1252')

  return str

# ******************************************************************************

