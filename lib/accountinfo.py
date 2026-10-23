#!/usr/bin/env python3

import os, sys, grp, subprocess
import configparser

accountQueryMethod = 0   # 0 = unknown, 1 = Gold, 2 = Slurm
goldPath           = ""
slurmQuotaFile     = ""
priv               = 0

systemProjects = ['nn9999k', 'testsupport', 'mifasupport', 'uio', 'staff', 'uit-swtest-001', 'uit-staff-000', 'norgrid', 'test', 'atlas-conf']
admGroup           = ""

def init(config, section):
  global accountQueryMethod, slurmQuotaFile, goldPath, userQueryMethod
  global admGroup, priv

  ok = 1

  if config.has_option(section, "goldPath"):
    goldPath = config.get(section, "goldPath").strip()
    if os.path.exists(goldPath):
      accountQueryMethod = 1
    else:
      print("Error: goldPath does not exist")
      ok = 0

  if accountQueryMethod == 0 and config.has_option(section, "slurmQuotaFile"):
    slurmQuotaFile = config.get(section, 'slurmQuotaFile').strip()
    if os.path.exists(slurmQuotaFile):
      accountQueryMethod = 2
    else:
      print("Error: slurmQuotaFile does not exist")
      ok = 0

  if accountQueryMethod==0:
    print("Error: no method for retreiving account information specified")
    ok = 0

  if config.has_option(section, "admGroup"):
    admGroup = config.get(section, 'admGroup').strip()

  if ok and priv == 0:
    # set permissions level
    for group in os.getgroups():
      try:
        first_group = grp.getgrgid(group)[0]
      except:
        first_group = ""
      if (admGroup != "" and first_group == admGroup) or first_group == "root":
        priv = 1

  return ok

# ******************************************************************************

def systemProject(account):
  return account in systemProjects

def checkAccountName(account):
  return not systemProject(account) and account[:2]=="nn" and account[-1]=="k" 

# ******************************************************************************

def queryGold():
  global goldPath

  accounts      = []
  account_users = dict()
  account_quota = dict()
  account_usage = dict()

  all_accounts  = []
  all_users     = dict()

  # Get the list of all accounts and users from Gold
  cmd = "%s/glsproject --raw -q" % (goldPath)
  result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
  lines = result.stdout.strip().split('\n')
  for line in lines:
    fields  = line.split('|')
    account = fields[0]
    # Remove '-' from user names
    tmp   = fields[2].split(',')
    users = []
    for u in tmp:
      u2 = u.replace("-","")
      # Ignore dummy users
      if not u2 in IGNORED_USERS:
        users.append(u2)
  
    if len(users) > 0 and users[0] != '' and checkAccountName(account):
      all_accounts.append(account)
      all_users[account] = users

  # Get the account usage from Gold
  for account in all_accounts:
    cmd = "%s/gbalance -q --show Deposited,Reserved,Available --raw -p %s" % (goldPath, account)
    p1 = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    lines = p1.communicate()[0].strip().split('\n')
    skip = 0
    if "does not exist" in lines[0] or "has no connected users" in lines[0]:
      skip = 1
    else:
      try:
        fields   = lines[0].split('|')
        quota    = float(fields[0])
        reserved = float(fields[1])
        avail    = float(fields[2])
        usage    = quota - avail - reserved

        if usage == 0.0 and quota == 0.0:
          skip = 1
        else:
          squota   = "%.2f" % (quota/3600.0)
          susage   = "%.2f" % (usage/3600.0)
      except:
        skip = 1

    if not skip:
      accounts.append(account)
      account_users[account] = all_users[account]
      account_quota[account] = squota
      account_usage[account] = susage

  return accounts, account_users, account_quota, account_usage

# ******************************************************************************

def querySlurm():
  global slurmQuotaFile

  accounts      = []
  account_users = dict()
  account_quota = dict()
  account_usage = dict()

  ok = 0
  # Get the list of all accounts from the quota file
  account = ""
  for line in open(slurmQuotaFile):
    # Remove the ending newline character
    line = line.rstrip('\n')

    # Process account names
    if len(line) > 0 and line[0] == '[' and 'account' in line and not 'user' in line:
      # Remove [ and ] from the string
      account = line.lstrip('[').rstrip(']')
      account_split = account.split('.')
      if len(account_split) == 3:
        account = account_split[1]
      else:
        continue

      # Compare the account name with the specified flags
      ok = checkAccountName(account)
      if not ok:
        continue

      # Reset the quota for this account
      account_quota[account] = "0"

      # Get the users for this account from Slurm
      cmd = "sshare --noheader --parsable2 --account=%s --all" % (account)
      result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
      lines = result.stdout.strip().split('\n')
      for line in lines:
        fields  = line.split('|')
        if len(fields) < 5:
          continue
        name    = fields[1]
        if name != "" and not ('dummy' in name or name[0] == '-'):
          if not account in accounts:
            accounts.append(account)
          if account in account_users:
            account_users[account].append(name)
          else:
            account_users[account] = [name]
    elif ok: # Process the quota for the last account encountered
      if "billing =" in line:
        line_split = line.split('=')
        if len(line_split) != 2:
          continue
        quota = line_split[1].strip()
        account_quota[account] = "%d" % (int(account_quota[account]) + int(quota))

  # Get the usage for each account from Slurm
  for account in accounts:
    cmd = 'sshare --noheader --parsable2 --accounts=%s --all' % (account)
    result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    lines = result.stdout.strip().split('\n')

    # The line without a name contains the total usage
    for line in lines:
      fields = line.split('|')
      if fields[1].strip() == "":
        iusage = int(fields[4]) / 3600
        account_usage[account] = "%d" % (iusage)

  return accounts, account_users, account_quota, account_usage

# ******************************************************************************

# Get account information from Gold or Slurm
def getInfo():
  global accountQueryMethod

  if accountQueryMethod==1:
    return queryGold() 
  elif accountQueryMethod==2:
    return querySlurm() 

# ******************************************************************************

# This is old code that probably should be updated.

# Read the list of projects in the etc directory
def readAccountList(accountFile):
  list = []

  for line in open(accountFile):
    # Remove the ending newline character
    line = line.rstrip('\n')
   
    # Update the list with the account
    if len(line) > 0:
      account = line.lower()

      if account[:2]!="nn" or account[-1]!="k":
        continue

      list.append( account )

  return list

# ******************************************************************************

def getUsers(project):
  global accountQueryMethod, goldPath 

  users = []

  if accountQueryMethod==1:
    try:
      cmd = '%s/glsproject -q --show Users %s' % (goldPath, project)
      result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
      lines = result.stdout.strip().split('\n')
      users = lines[0].rstrip(' ').split(',')
    except:
      print("An error happened while using a Gold command.")
      sys.exit(1)
  else:
    try:
      cmd = 'sacctmgr --noheader --parsable2 show account name=%s withassoc' % (project)
      result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
      lines = result.stdout.strip().split('\n')
      for line in lines:
        user = line.split('|')[5]
        if user != "":
          users.append(user)
    except:
      print("An error happened while using a Slurm command.")
      sys.exit(1)

  return(users)

# ******************************************************************************

def check_username(username):
  global accountQueryMethod, goldPath 

  if accountQueryMethod==1:
    cmd = '%s/glsuser -q --show Name -u "%s"' % (goldPath, username)
  else:
    cmd = 'sacct -u "%s"' % (username)

  result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

  if result.stderr:
    print('Error: the user "%s" does not exist.' % (username))
    sys.exit(1)

# ******************************************************************************

def user_accounts(username):
  global accountQueryMethod, goldPath 

  # get list of user projects
  if accountQueryMethod==1:
    try:
      cmd = '%s/glsaccount -u %s -q --show Projects' % (goldPath, username)
      result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
      lines = result.stdout.strip().split('\n')
    except:
      print("An error happened while using a Gold command.")
      sys.exit(1)

    projects = out
  else:
    try:
      cmd = 'sacctmgr --noheader --parsable2 show user name=%s withassoc' % (username)
      result = subprocess.run([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
      lines = result.stdout.strip().split('\n')
    except:
      print("An error happened while using a Slurm command.")
      sys.exit(1)

    projects = []
    for line in lines:
      account = line.split('|')[4]
      projects.append(account)

  return projects

def check_priv(username=None, project=None):
  if project:
    if not priv:
      projects = user_accounts(username)
      for proj in projects:
        if proj.rstrip() == project:
          return None
      print('Error: %s is not a member of %s' % (username, project))
      sys.exit(4)
    else:
      return None
  elif username:
    if not priv:
      own_username = os.environ.get("LOGNAME")
      if own_username != username:
        print("Error: you can only check your own account")
        sys.exit(4)
    else:
      return None

  if not priv:
    print('%s: option not recognized' % sys.argv[0])
    print('Try \'%s -h\' for more information.' % sys.argv[0])
    sys.exit(4)
  
  return None 

# ******************************************************************************

