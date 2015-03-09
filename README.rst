A Python Azkaban Command Line Wrapper
=======================
A command line wrapper to access azkaban.
It provides funciton such as: create&delete project; upload project zips; list project flows, tasks and excutions; run flow and run single task ...


Example
Create a project name 'my_project'
az_ctrl.py create my_project 'My project description here' 
Upload a project with a zipfile
az_ctrl.py upload my_project /home/zhdeng/project.zip
List the wokflows in a project
az_ctrl.py flows my_project
List the jobs under main flow
az_ctrl.py jobs my_project main
Run a flow
az_ctrl.py run my_project main
Run a single job under a flow
az_ctrl.py runJob my_project main single_job_name
Cancel a runing excution
az_ctrl.py cancel my_project $execId
Fetch executions of a flow
az_ctrl.py fetch my_project $execId
...
Full Usage
Just run az_ctrl.py
Usage: az_ctrl.py [options] cmd args...
Options:
   -h, --help show this help message and exit
  --host=HOST Azkaban host address
  --config=CONFIG config file
  --env=ENV Azkaban env
  --expire=EXPIRE Session expire time in second
az_ctrl.py [options] command [args...]
All commands:
auth -- authenticate
unauth -- clean authenticate
create name description -- create a project
delete project -- delete a project
upload project zipfile -- upload a project
flows project -- fetch project flows
jobs project flow -- fetch flow jobs
execs porjcet flow start length -- fetch flow executions
runningX porjcet flow -- fetch currect running executions
run project flow -- run flow
runJob project flow job -- run a specifed job under a flow
cancel project execId -- cancel running execution
pause project execId -- pause a execution
resume project execId -- resume a execution
fetch project execId -- fetch a execution
logs project execId jobId [offset=0] [length=1000] -- fetch a log for an execution
updates project execId [lastUpdateTime=-1] -- fetch a updates for an execution
help
Azkaban Env
The default environment is magic for this release. We can switch to different environment by --env flag: [magic, canasta, nertz, nertz2].
We can specify azkaban host directly by using --host flag.
Session login and login cofig
This command line wraper will ask the username and password of your azkaban account on the first time a session begin. It will cache the loged in session for 4 hours. (User --expire flag to modify it)
After loged in, the session id is re-used. If your want to use another account please run az_ctrl.py unauth to unlogin and remove the login cache.
If you want to explict type username and password to login your account.
Please place a config file under $HOME/.az_ctrl/config
The context of config file is 
username = xxxx
password = xxx
