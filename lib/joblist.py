#!/usr/bin/env python3

import os, subprocess
from hostlist import expand_hostlist

jobScheduler    = 0   # 0 = unknown, 1 = PBS, 2 = Slurm
nodesSeenBefore = dict()
simpleNodeList  = []
nodeInfo        = dict()
jobList         = []

# ******************************************************************************

def init(config):
  global jobScheduler

  if config.has_option("Jobs", "pbs"):
    jobScheduler = 1
  elif config.has_option("Jobs", "slurm"): 
    jobScheduler = 2
  else:
    print('Error: config must have a "Jobs" section with a pbs or a slurm option.')

  return jobScheduler > 0

# ******************************************************************************

# Stores information about a job
def updateLists(jobid, userid, nodes, account):
  global nodesSeenBefore, simpleNodeList, nodeInfo

  # do not store jobs that are not running
  if len(nodes) == 1 and nodes[0][0] == '-':
    return

  jobinfo = [jobid, userid, len(nodes), account]

  for node in nodes:
    if node in nodesSeenBefore:
      # add information about this job to the information about the node
      nodeInfo[node].append(jobinfo)
    else:
      # make a list of the nodes that are in use, so that it can be sorted
      nodesSeenBefore[node] = 1
      simpleNodeList.append(node)

      # make a new list about job info and store this in the node information
      nodeInfo[node] = [jobinfo]

# ******************************************************************************

# Finds (job, user, node) for all running jobs
def getJobInfo_PBS():
  # Get the list of runnning jobs for this user
  result = subprocess.run(
    ["qstat -wtn1"],
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True,  # Works in 3.6 and 3.9 (decodes stdout/stderr to str)
    check=True,  # Optional: raises CalledProcessError if return code != 0
  )
  jobs = result.stdout.strip().split('\n')

  # Check each job that this user has running right now, while skipping the 
  # 4 line header
  readingJob = 0
  for i in range(4, len(jobs)):
    line = jobs[i]

    info   = line.split()
    jobid  = info[0].split('.')[0]
    userid = info[1]
    status = info[9]

    # Find the value of Account_Name
    result = subprocess.run(
      ["qstat -f %s" % jobid],
      shell=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      universal_newlines=True,  # Works in 3.6 and 3.9 (decodes stdout/stderr to str)
      check=True,  # Optional: raises CalledProcessError if return code != 0
    )
    lines = result.stdout.strip().split('\n')

    account = ''
    for line in lines:
      if "Account_Name" in line:
        account = line.split('=')[1].strip()


    # update the lists with the information about the job
    if status == 'R':
      nodes = [] 
      parts = info[11].lstrip().split('+')
      for p in parts:
        if p != "":
          nodes.append(p.split('/')[0])

      updateLists(jobid, userid, nodes, account)

# Finds (job, user, node) for all running jobs
def getJobInfo_SLURM():
  # Get the list of runnning jobs for this user
  result = subprocess.run(
    ["squeue -ho %i:%u:%t:%N:%a"],
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True,  # Works in 3.6 and 3.9 (decodes stdout/stderr to str)
    check=True,  # Optional: raises CalledProcessError if return code != 0
  )
  jobs = result.stdout.strip().split('\n')

  # Check each job that this user has running right now
  for i in range(0, len(jobs)):
    line = jobs[i]

    # read information about the job
    info    = line.split(':')
    jobid   = info[0]
    userid  = info[1]
    status  = info[2]
    account = info[4]

    if status == 'R':
      # convert e.g. 'c3-[1-2,9]' to 'c3-1,c3-2,c3-9'
      nodes = expand_hostlist(info[3])

      # convert e.g. 'c9-19' to 'compute-9-19'
#      for j in range(0, len(nodes)):
#        nodes[j] = "compute-"+nodes[j][1:]

      # update the lists with the information about this job
      updateLists(jobid, userid, nodes, account)

# ******************************************************************************

# Store a line for each node in a file
# Each line is in the format: hostname:jobid1,userid1;jobid2,userid2;...
def write(fileName):
  global simpleNodeList, nodeInfo

  if jobScheduler == 1:
    getJobInfo_PBS()
  elif jobScheduler == 2:
    getJobInfo_SLURM()

  # Rewrite all information to the log file
  file = open(fileName, "w")

  # sort the simple node list
  simpleNodeList.sort()

  for node in simpleNodeList:
    line = node+":"
    firstJob = 1
    for jobid, userid, nodeCount, account in nodeInfo[node]:
      if not firstJob:
        line += ";"
      line += jobid+","+userid+","+str(nodeCount)+","+account
      firstJob = 0
    file.write(line+"\n")

  file.close()

# ******************************************************************************

# Reads a list of jobs running on this compute node from a file written by the
# function above.
def read(filename, hostname):
  global jobList

  jobList = []

  # Check if the file with the job lists exists
  if os.path.exists(filename):
    # Check for file corruption
    result = subprocess.run(
      ['file -b %s' % (filename)],
      shell=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      universal_newlines=True,  # Works in 3.6 and 3.9 (decodes stdout/stderr to str)
      check=True,  # Optional: raises CalledProcessError if return code != 0
    )
    output = result.stdout.strip()

    if not "ASCII text" in output and not "CSV text" in output:
      # Write a warning about the corrupted file
      iFileName = rootDir+"log/"+hostname+".err"
      with open(iFileName, "w") as file:
        file.write(hostname+": Unable to read "+filename+"\n")
      sys.exit()

    # Search for hostname in the file
    for line in open(filename):
      node, jobInfoList = line.rstrip('\n').split(':')
      if node == hostname:
        for job in jobInfoList.split(';'):
          jobid, userid, nodeCount, account = job.split(',')
          jobList.append([jobid,userid,nodeCount,account])
        return 

# ******************************************************************************

# Get the job id and the number of nodes that the user is running on.
def getJobInfo(userid):
  global jobList

  for job, user, nodeCount, account in jobList:
    if user == userid:
      return (job, nodeCount, account)

  return ("", "", "")
