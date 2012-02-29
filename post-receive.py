from fabric.api import env, run, sudo, local, put, settings
from time import localtime, strftime
import os
import random
import hashlib
import redis 

#Comments:
#
# Why all of the globals?  you can make those module level variables
# as an extension to ^, take advantage of the built in python logging support
# Right now redis only supports localhost.  That is fine for an initial pass, but we should support a configurable redis
# Move Redis to a more abstract data store definition. Let's support pure in memory (dict) for now as well  
# Definitely cannot assume that everythign will work in ~.  Find for now, but definitely abstract
# Right now, this will get confused if we have more than 1 repository that we are working with (It's using a single, hard coded virtualenv.
# don't assume that sourcing the activate file is going to do the right thing.  Instead explicitly specify the path of the script you want. . . i.e., for python do: "{0}/bin/python".format(virtualenvdir)
# For the location of the union mount, you can create some temporary directory.  So, you create a hash of some variety, then create a temp dir named after that hash somewhere (/mnt, or somewhere else is totally fine.  really make it configurable.  So the ephemeral storage should be generated using tempfile.mkdtemp, probably and then use the version/app hash for the aufs mount dir.  
# Definitely move the test code out of here and in to a test module of some kind.  Look at unittest and nose for a way of automating the tests.  
# I've added a setup.py and requirements.txt (might as well eat our own dog food :) ).


# Things TODO
# Integrate with SSH Keys
# Better Logging and Error Checking
# Store data in redis 
# Create and simple ruby app that will view the logged data

push_logger = redis.Redis()
# Please enter the ssh password ... :|
env.password = ''
userhome = os.path.expanduser("~")
def move_to_deploy():             
      local("cp -r ~/python_code ~/deploy")

# I assume you are on the git server in the hooks folder. Paths hard coded for testing reasons. 

def extract_latest_push (archive_name):
      """ Extract just the git archive. Used later to check for requirments.txt"""
      local("mkdir ~/python_code")
      local("mkdir ~/python_code_archives")
      saving_location = "~/python_code_archives/"+archive_name
      local("git archive HEAD | bzip2 > %s.tar.bz2" % saving_location)
      local("git archive master | tar -x -C ~/python_code")


def create_sqsh(sqsh_name): 
      """ Make the squash file system """
      global push_logger
      global userhome
      sqsh_file = str(sqsh_name) +".fs"
      loc_sqsh = userhome + "/" + sqsh_file
      local("mksquashfs ~/deploy %s" % loc_sqsh)   
      push_logger.hmset(sqsh_name, dict(push_time='', commit_time='',commited_by='', file_size='', sha256='', hosts='', requirments=''))
      return sqsh_file

def get_file_size(filename):
      global push_logger
      global userhome
      sqsh_file = userhome + "/" + filename
      size = os.path.getsize(sqsh_file)
      push_logger.hmset('filename', dict(file_size=size))                 
      return size

 
def create_sha256(filename):
      global logger
      global userhome
      sqsh_file = userhome + "/" + filename
      sha256 = hashlib.sha256()
      with open(sqsh_file,'rb') as f: 
            for chunk in iter(lambda: f.read(128*sha256.block_size), ''): 
                  sha256.update(chunk)
      push_logger.hmset('filename', dict(sha256=sha256.digest()))
      return sha256.digest()


def pip_install():
      local("cd ~/ && pip install -E deploy -r ~/deploy/python_code/requirements.txt")
      
def deactivate_virtualenv():
      local("deactivate") 
      
def create_and_lauch_virtualenv():
      local("virtualenv ~/deploy")
      local(". ~/deploy/bin/activate")
      
def get_requirments(directory):
      requirements = "requirements.txt"
      if check_file_exists(requirments,directory):
            directory = open(directory+requirments,"r")
            contents = directory.read()
            push_logger.hmset('filename', dict(requirments=contents))
      else:
            print "%s not found" % requirments
            
            
def check_file_exists(filename,directory):
      dir_list = os.listdir(directory)
      if(filename in dir_list):
            return 1
      else:
            return 0

# Pass in the file with the list of machines to install the squashfs 
def get_machine_list():
      machines = "remote_hosts.txt"
      userhome = os.path.expanduser("~")
      path_to_code = "/deploy/python_code/"
      total_path = userhome + path_to_code
      if (check_file_exists(machines,total_path)):
            machine_file = open(total_path+machines,"r")
            return machine_file
      else:
            print "%s not found" % machines
      
def create_host_list(machines):
      hosts = []
      for host in machines:
            hosts.append(host.rstrip())
      return hosts


def push_file_to_hosts(filename,remote_hosts):
      global push_logger
      global userhome
      sqsh_file = userhome + "/" + filename

      for host in remote_hosts:
            with settings(host_string=host):
                  put(sqsh_file, '~/')                  
                  time = strftime("%a, %d %b %Y %H:%M:%S +0000", localtime())
                  push_logger.hmset(sqsh_file, dict(push_time=time))
                  new_hosts = push_logger.hmget(filename,["hosts"]).append(host)
                  push_logger.hmset(sqsh_file, dict(hosts=new_hosts))


def mount_file(filename,hosts):
      for host in hosts:
            with settings(host_string=host):
                  remotehome = run("echo $HOME")
                  sqsh_file = remotehome + "/" + filename
                  sudo("mkdir -p /mnt/dir")
                  run("mkdir -p ~/btest1")
                  sudo("mount %s /mnt/dir -t squashfs -o loop" % sqsh_file)
                  sudo("mount -t aufs -o dirs=/mnt/dir=/mnt/dir:/mnt=%s aufs btest1" % sqsh_file)

def excute_bottle(hosts):
      for host in hosts:
            with settings(host_string=host):
                  run("nohup python ~/btest1/python_code/hello.py &")


def test_bottle(hosts):
      for host in hosts:
            print host
            with settings(host_string=host):
                  output = run("telnet localhost 8080")
                  print 'output:', output
                  
def create_id():
      return random.randint(1, 90000)
                  
def local_actions():
      local_state = {} 
      x = create_id()
      extract_latest_push(str(x))   
      create_and_lauch_virtualenv()
      move_to_deploy()
      pip_install()
      local_state["sqsh"] = create_sqsh(x)
      local_state["hosts"] = create_host_list(get_machine_list())
      create_sha256(local_state["sqsh"])
      get_file_size(local_state["sqsh"])
      return local_state
def remote_actions(local_state):
      remote_state = {} 
      push_file_to_hosts(local_state["sqsh"], local_state["hosts"])
      print local_state["hosts"] 
      mount_file(local_state["sqsh"], local_state["hosts"])
      excute_bottle(local_state["hosts"])
      test_bottle(local_state["hosts"])

def process_push():
      local_state = local_actions()
      remote_state = remote_actions(local_state)





process_push()

