#!/usr/bin/python
"""
Enhanced Azkaban command line interface
"""
__author__ = 'Zhifeng Deng'
__email__ = 'zhdeng@linkedin.com'
__version__ = '1.5'

import os, time, re
import json
import base64
import ConfigParser
import urllib
from time import strftime
from datetime import datetime
import getpass


options = dict()
args = list()

ENV_MAGIC = 'magic'
ENV_NERTZ = 'nertz'
ENV_NERTZ2 = 'nertz2'
ENV_CANASTA = 'canasta'
ENV_WAR = 'war'

DEFAULT_SESSION_EXPIRE = 3600 * 4 # 4 hours

AZ_HOST = {
  ENV_MAGIC: 'https://eat1-magicaz01.grid.linkedin.com:8443',
  ENV_CANASTA: 'https://eat1-canastaaz01.grid.linkedin.com:8443',
  ENV_NERTZ: 'https://eat1-nertzaz01.grid.linkedin.com:8443',
  ENV_NERTZ2: 'https://eat1-nertzaz02.grid.linkedin.com:8443',
  ENV_WAR: 'https://lva1-waraz01.grid.linkedin.com:8443',
}

HOME_PATH = os.environ["HOME"]

AZ_STORE_PATH = HOME_PATH + '/.az_ctrl/'
DEFAULT_CONFIG = AZ_STORE_PATH + 'config'

ACTION_AUTH = 'auth'
ACTION_UNAUTH = 'unauth'
ACTION_CREATE = 'create'
ACTION_DELETE = 'delete'
ACTION_UPLOAD = 'upload'
ACTION_FETCH_FLOWS = 'flows'
ACTION_FETCH_JOBS = 'jobs'
ACTION_FETCH_EXECS = 'execs'
ACTION_FETCH_RUNING_EXECS = 'runningX'
ACTION_RUN = 'run'
ACTION_RUN_SINGLE_JOB = 'runJob'
ACTION_RUN_LAST_FAIL = 'runLF'
ACTION_RUN_LAST_KILL = 'runLK'
ACTION_CHECK_LAST_SUC = 'lastSuc'
ACTION_CHECK_LAST_RUN = 'lastRun'
ACTION_CANCEL = 'cancel'
ACTION_PAUSE = 'pause'
ACTION_RESUME = 'resume'
ACTION_FETCH_A_EXEC = 'fetch'
ACTION_FETCH_A_EXEC_LOGS = 'logs'
ACTION_FETCH_A_EXEC_UPDATES = 'updates'
ACTION_TRACK_FAILED = 'trackFailed'
ACTION_HELP = 'help'
ACTION_MORE_HELP = 'morehelp'


HANDLER_MANAGER = 'manager'
HANDLER_EXECUTOR = 'executor'

ACTION_EXAMPLE = [
  'auth -- authenticate',
  'unauth -- clean authenticate',
  'create name description -- create a project',
  'delete project -- delete a project',
  'upload project zipfile -- upload a project',
  'flows project -- fetch project flows',
  'jobs project flow -- fetch flow jobs',
  'execs porjcet flow start length -- fetch flow executions',
  'runningX porjcet flow -- fetch currect running executions',
  'run project flow -- run flow',
  'runJob project flow job -- run a specifed job under a flow',
  'runLF project flow [fetchCount=20] -- retry last failed run of a flow',
  'lastSuc project flow [fetchCount=20] -- check last successed run of a flow',
  'cancel project execId -- cancel running execution',
  'pause project execId -- pause a execution',
  'resume project execId -- resume a execution',
  'fetch project execId -- fetch a execution',
  'logs project execId jobId [offset=0] [length=1000] -- fetch a log for an execution',
  'updates project execId [lastUpdateTime=-1] -- fetch a updates for an execution',
  'help | morehelp'
]

ACTION_EXAMPLE2 = [
  'To specify azkaban environment --env=[magic,cansta,nertz,nertz2]',
  'Create a project name my_project',
  'az_ctrl.py create my_project "My project description here"',
  'Upload a project with a zipfile',
  'az_ctrl.py upload my_project /home/zhdeng/project.zip',
  'List the wokflows in a project',
  'az_ctrl.py flows my_project',
  'List the jobs under main flow',
  'az_ctrl.py jobs my_project main',
  'Run a flow',
  'az_ctrl.py run my_project main',
  'Run a single job under a flow',
  'az_ctrl.py runJob my_project main single_job_name',
  'Cancel a runing excution',
  'az_ctrl.py cancel my_project $execId',
  'Fetch executions of a flow',
  'az_ctrl.py fetch my_project $execId',
  '...'
]

TEE_TMP = AZ_STORE_PATH + 'tee'
SID_TMP = AZ_STORE_PATH + 'sid'

def infoPrint(msg):
  if not options.mute:
    print msg

def toReadableTime(millis):
  if millis == -1:
    return '-- --'
  else:
    return datetime.fromtimestamp(millis/1000.0).strftime("%a, %d %b %Y %H:%M:%S +0000")

def printRun(cmd):
  infoPrint(cmd)
  assert os.system(cmd) == 0

def teeRun(cmd, muteOut=False, loadJson=False, mutePrint=False):
  if options.mute:
    muteOut = True
  if not muteOut:
    cmd = cmd + '| tee %s' % TEE_TMP
  else:
    cmd = cmd + '> %s 2>/tmp/az_ctrl_stderr' % TEE_TMP
    infoPrint('output too long, store in %s' % TEE_TMP)

  if mutePrint:
    os.system(cmd)
  else:
    printRun(cmd)
    infoPrint('\n')

  result = open(TEE_TMP).read()

  if loadJson:
    return json.loads(result)
  else:
    return result


def pipeRun(cmd):
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE)
  output, error = p.communicate()
  print output
  print error

def prepareAzTmp():
  printRun('mkdir -p %s' % AZ_STORE_PATH)

def sidLocate(host):
  return SID_TMP + '.%s' % base64.b64encode(host)

def writeSid(host, sid):
  printRun('echo %s > %s' % (sid, sidLocate(host)))

def cleanSid(host):
  printRun('rm %s' % (sidLocate(host)))

def readSid():
  host=getHost()
  sid = open(sidLocate(host)).read().strip()
  infoPrint('loading sid[%s]' % sid)
  return sid

def getHost():
  if options.host:
    return options.host
  return AZ_HOST[options.env]

def getHandler(handler):
  return '%s/%s' % (getHost(), handler)

def makeDataSection(dataDict, isForm=False):
  result = ''
  for key, value in dataDict.iteritems():
    if isForm:
      result += ' --form \'%s=%s\'' % (key, value)
    else:
      result += ' --data \'%s=%s\'' % (key, value)

  return result

def unauth():
  cleanSid(getHost())

def readConfig(configPath):
  if not os.path.exists(configPath):
    return {}
  from io import StringIO
  vfile = StringIO(u'[main]\n%s'  % open(options.config).read())
  configParser = ConfigParser.RawConfigParser()
  configParser.readfp(vfile)
  items = configParser.items('main')
  config = {}
  for (k, v) in items:
    config[k] = v
  return config

def authenticate():
  config = readConfig(options.config)

  username = ''
  password = ''
  if 'username' not in config:
    username = raw_input('Azkaban Username:')
  if 'password' not in config:
    password = getpass.getpass('Azkaban Password:')

  dataDict = {
    'action' : 'login',
    'username': config.get('username', username),
    'password': urllib.quote(config.get('password', password)),
  }
  cmd = 'curl -k -X POST %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_MANAGER))

  result = teeRun(cmd, loadJson=True, mutePrint=True)
  if result['status'] == 'success':
    sessionId = result['session.id']
    writeSid(getHost(), sessionId)
    print 'Auth successed. Sid[%s] recorded. Please run other commands' % sessionId
  else:
    print 'Error', result['error']


def authenticateForAction():
  sidFile = sidLocate(getHost())
  if (not os.path.exists(sidFile)) or (time.time() - os.path.getmtime(sidFile) > options.expire):
    print 'Sid not exist or expire'
    authenticate()

def createProject(name, description):
  authenticateForAction()
  sid = readSid()
  dataDict = {
    'session.id': sid,
    'name': name,
    'description': urllib.quote(description),
  }
  cmd = 'curl -k -X POST %s %s?action=create' % (makeDataSection(dataDict), getHandler(HANDLER_MANAGER))
  result = teeRun(cmd)


def deleteProject(project):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'delete': 'true',
    'project': project,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_MANAGER))
  teeRun(cmd)

def uploadProject(project, zipFile):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'upload',
    'project': project,
    'file': '@%s;type=application/zip' % zipFile,
  }
  cmd = 'curl -k -i -H "Content-Type: multipart/mixed" -X POST %s %s' % (makeDataSection(dataDict, True), getHandler(HANDLER_MANAGER))

  teeRun(cmd)

def fetchFlows(project):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'fetchprojectflows',
    'project': project,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_MANAGER))

  teeRun(cmd)

def fetchJobs(project, flow):
  authenticateForAction()
  sid = readSid()
  dataDict = {
    'session.id': sid,
    'ajax': 'fetchflowgraph',
    'project': project,
    'flow' : flow,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_MANAGER))

  return teeRun(cmd, loadJson=True)

def fetchExecutions(project, flow, start=0, length=10):
  authenticateForAction()
  sid = readSid()
  dataDict = {
    'session.id': sid,
    'ajax': 'fetchFlowExecutions',
    'project': project,
    'flow' : flow,
    'start': int(start),
    'length': int(length),
  }

  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_MANAGER))

  return teeRun(cmd, loadJson=True)

def fetchRunningExecutions(project, flow):
  authenticateForAction()
  sid = readSid()
  cmd = 'curl -k --get --data "session.id=%s&project=%s&flow=%s&ajax=%s" %s' % (sid, project, flow, 'getRunning', getHandler(HANDLER_EXECUTOR))

  result = teeRun(cmd, loadJson=True)
  for execId in result.get('execIds', []):
      showExecUrl(execId)

  return result

def showExecUrl(execid):
  if execid:
    host = getHost()
    print 'Check execution at:'
    print '%s/executor?execid=%d' % (host, execid)
  else:
    print 'No execid from in result josn'

def runFlow(project, flow):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'executeFlow',
    'project': project,
    'flow' : flow
  }
  if options.concurrentOption:
    dataDict['concurrentOption'] = options.concurrentOption

  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  result = teeRun(cmd, loadJson=True)
  showExecUrl(result.get('execid'))
  return result

def runJob(project, flow, task):
  jobsResult = fetchJobs(project, flow)
  ids = [ x['id'] for x in jobsResult['nodes'] if x['id'] != task ]

  return runJobWithDisabledTask(project, flow, ids)

def runJobWithDisabledTask(project, flow, disabledTaskList):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'executeFlow',
    'project': project,
    'flow' : flow,
    'disabled' : urllib.quote(json.dumps(disabledTaskList)),
  }
  if options.concurrentOption:
    dataDict['concurrentOption'] = options.concurrentOption

  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  result = teeRun(cmd, loadJson=True)
  showExecUrl(result.get('execid'))
  return result

def runLastFailed(project, flow, fetchCount=20):
  return runLastRunOfStatus(project, flow, 'FAILED', fetchCount)

def runLastKilled(project, flow, fetchCount=20):
  return runLastRunOfStatus(project, flow, 'KILLED', fetchCount)

def runLastRunOfStatus(project, flow, status, fetchCount=20):
  execs = fetchExecutions(project, flow, 0, fetchCount)
  failedExecId = None
  for x in execs['executions']:
    if x['status'] == status:
      failedExecId = x['execId']
      break

  if not failedExecId:
    print 'No failure in last %d run' % fetchCount
    exit(1)

  jobsResult = fetchAExec(project, failedExecId)
  ids = [ x['id'] for x in jobsResult['nodes'] if x['status'] == 'SUCCEEDED' or x['status'] == 'SKIPPED' ]
  return runJobWithDisabledTask(project, flow, ids)

def cancelFlow(project, execId):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'cancelFlow',
    'project': project,
    'execid': execId,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  teeRun(cmd)

def pauseFlow(project, execId):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'pauseFlow',
    'project': project,
    'execid': execId,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  teeRun(cmd)

def resumeFlow(project, execId):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'resumeFlow',
    'project': project,
    'execid': execId,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  teeRun(cmd)

def fetchAExec(project, execId):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'fetchexecflow',
    'project': project,
    'execid': execId,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  return teeRun(cmd, loadJson=True)

def fetchAExecLogs(project, execId, jobId, offset=0, length=1000):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'fetchExecJobLogs',
    'project': project,
    'execid': execId,
    'jobId' : jobId,
    'offset': offset,
    'length': length,
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  return teeRun(cmd, muteOut=True)

def fetchAExecUpdates(project, execId, lastUpdateTime=-1):
  authenticateForAction()
  sid = readSid()

  dataDict = {
    'session.id': sid,
    'ajax': 'fetchexecflowupdate',
    'project': project,
    'execid': execId,
    'lastUpdateTime': lastUpdateTime
  }
  cmd = 'curl -k --get %s %s' % (makeDataSection(dataDict), getHandler(HANDLER_EXECUTOR))
  teeRun(cmd)

def graspMrJobId(result):
  return re.findall('jobId job_[0-9_]*', result)

def trackFailed(project, execId, outputPath='~/trackfail'):
  if not os.path.exists(outputPath):
    print 'Output path does not exist: %s' % outputPath
    exit(1)

  result = fetchAExec(project, execId)
  nodes = result['nodes']
  for node in nodes:
    if node['status'] == 'FAILED':
      jobId = node['id']
      jobTrackPath = '%s/%s/%s' % (outputPath, execId, jobId)
      if os.path.exists(jobTrackPath):
        continue

      os.makedirs(jobTrackPath)
      logResult = fetchAExecLogs(project, execId, node['id'], 0, 10000000)
      os.system('cp %s %s/az.log' % (TEE_TMP, jobTrackPath))
      mrJobIds = graspMrJobId(logResult)
      mrJobIds = [ id.split()[1] for id in mrJobIds ]
      print myJobIds

def checkLastSuc(project, flow, fetchCount=20):
  execs = fetchExecutions(project, flow, 0, fetchCount)
  successedExecId = None
  for x in execs['executions']:
    if x['status'] == 'SUCCEEDED':
      successedExecId = x['execId']
      break

  if not successedExecId:
    print 'No successed run in last %d tries' % fetchCount
    exit(1)
  else:
    print x
    print 'Last Suc Started Time:', toReadableTime(x['startTime'])
    print 'Last Suc Finished Time:', toReadableTime(x['endTime'])

def checkLastRun(project, flow, fetchCount=1):
  execs = fetchExecutions(project, flow, 0, fetchCount)
  execId = None
  for x in execs['executions']:
    execId = x['execId']
    break

  if not execId:
    print 'No last run found'
    exit(1)
  else:
    print 'Last Run of %s : %s' % (project, flow)
    print 'Last Run Status:',x['status']
    print 'Last Run By:',x['submitUser']
    print 'Last Run Started Time:', toReadableTime(x['startTime'])
    print 'Last Run Finished Time:', toReadableTime(x['endTime'])
    print '------------------------------------------------------'

def main():
  from optparse import OptionParser
  parser = OptionParser()
  parser.add_option('--host', dest='host', default=None, help='Azkaban host address')
  parser.add_option('--config', dest='config', default=DEFAULT_CONFIG, help='config file')
  parser.add_option('-e', '--env', dest='env', default=ENV_NERTZ, help='Azkaban env')
  parser.add_option('-p', '--param', dest='param', default='', help='Job param')
  parser.add_option('--expire', dest='expire', type='int', default=DEFAULT_SESSION_EXPIRE, help='Session expire time in second')
  parser.add_option('--concurrentOption', dest='concurrentOption', default='', help='concurrentOption: [ingore | pipeline | queue]')
  parser.add_option('--mute', dest='mute', default=False, help='mute stdout except return text')

  global options
  global args
  (options,args) = parser.parse_args()

  if (len(args) == 0):
    parser.print_help()
    printHelp()
    exit()

  if not options.mute:
    print 'options:', options
    print 'args:', args
  prepareAzTmp()

  ALL_ACTION = {
             ACTION_AUTH: authenticate,
             ACTION_UNAUTH: unauth,
             ACTION_CREATE: createProject,
             ACTION_DELETE: deleteProject,
             ACTION_UPLOAD: uploadProject,
             ACTION_FETCH_FLOWS: fetchFlows,
             ACTION_FETCH_JOBS: fetchJobs,
             ACTION_FETCH_EXECS: fetchExecutions,
             ACTION_FETCH_RUNING_EXECS: fetchRunningExecutions,
             ACTION_RUN: runFlow,
             ACTION_RUN_SINGLE_JOB: runJob,
             ACTION_RUN_LAST_FAIL: runLastFailed,
             ACTION_RUN_LAST_KILL: runLastKilled,
             ACTION_CHECK_LAST_SUC: checkLastSuc,
             ACTION_CHECK_LAST_RUN: checkLastRun,
             ACTION_CANCEL: cancelFlow,
             ACTION_PAUSE: pauseFlow,
             ACTION_RESUME: resumeFlow,
             ACTION_FETCH_A_EXEC: fetchAExec,
             ACTION_FETCH_A_EXEC_LOGS: fetchAExecLogs,
             ACTION_FETCH_A_EXEC_UPDATES: fetchAExecUpdates,
             ACTION_TRACK_FAILED: trackFailed,
             ACTION_HELP: printHelp,
             ACTION_MORE_HELP: printMoreHelp
  }

  action = args[0]
  if action in ALL_ACTION:
    ALL_ACTION[action](*args[1:])

    print ('\n\n')
  else:
    printHelp()


def printHelp():
  print '\naz_ctrl.py [options] command [args...]\nAll commands:'
  for example in ACTION_EXAMPLE:
    print '\t\t', example

def printMoreHelp():
  printHelp()
  print '\n'
  for example in ACTION_EXAMPLE2:
    print '\t\t', example, '\n'

if __name__ == '__main__':
  main()
