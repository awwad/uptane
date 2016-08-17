"""
<Program Name>
  uptane_tuf_server.py

<Purpose>
  Create, load, manipulate, and host Uptane's TUF repo.

  Running this as a script creates a repo with name REPO_NAME at directory
  REPO_PATH.

  In order to load a repository with name REPO_NAME at path ROOT_PATH, import
  this module and run load_repo().

  Sample use:

  import uptane_tuf_server as uts
  uts.clean_slate()
  uts.host_repo()


  The file is dividied into REPOSITORY CORE FUNCTIONALITY and ATTACK CODE.

"""

import tuf
import tuf.repository_tool as repotool
import tuf.client.updater as updater
import os # for chdir
import shutil # for copying
import subprocess # for hosting
import time # for sleep
import sys # for python version
import datetime # for metadata expiration times


# Constants
ROOT_PATH = '/Users/s/w/uptanedemo'
REPO_NAME = 'temp_tufrepo'
REPO_PATH = ROOT_PATH + '/' + REPO_NAME
METADATA_STAGED_PATH = REPO_PATH + '/metadata.staged'
METADATA_LIVE_PATH = REPO_PATH + '/metadata'
KEYS_DIR = REPO_PATH + '/keys/'
IMAGES_DIR = REPO_PATH + '/targets/images/'
SERVER_PORT = 33331

CLEAN_REPO_NAME = 'clean_tufrepo'
CLEAN_REPO_PATH = ROOT_PATH + '/' + CLEAN_REPO_NAME
CLEAN_METADATA_PATH = CLEAN_REPO_PATH + '/metadata'
CLEAN_KEYS_DIR = CLEAN_REPO_PATH + '/keys/'
CLEAN_IMAGES_DIR = CLEAN_REPO_PATH + '/targets/images/'

ATTACK_DIR = ROOT_PATH + '/attack_data'


# Globals
repo = None
url = 'http://localhost:'+str(SERVER_PORT) + '/'
public_root_key = None
public_time_key = None
public_snap_key = None
public_targets_key = None
public_images_key = None
public_director_key = None
public_brakes_key = None
public_acme_key = None
public_cell_key = None
private_root_key = None
private_time_key = None
private_snap_key = None
private_targets_key = None
private_images_key = None
private_director_key = None
private_brakes_key = None
private_acme_key = None
private_cell_key = None



#########################################
##### REPOSITORY CORE FUNCTIONALITY #####
#########################################

def host_repo():
  """
  Loads the current repository at REPO_PATH and hosts it via http on port
  SERVER_PORT for 10,000 seconds, or until any exception is raised.

  Uses python's standard simple http server, and should be Python 2/3
  compatible.
  """
  global repo
  global url

  os.chdir(ROOT_PATH)

  repo = load_repo()

  # Copy staging metadata to live metadata path, where it will be used as a TUF
  # repo. Clear any old live metadata.
  if os.path.exists(METADATA_LIVE_PATH):
    shutil.rmtree(METADATA_LIVE_PATH)
  shutil.copytree(METADATA_STAGED_PATH, METADATA_LIVE_PATH)

  os.chdir(REPO_PATH)

  # Python 2/3 compatibility.
  command = []
  if sys.version_info.major < 3:
    command = ['python', '-m', 'SimpleHTTPServer', str(SERVER_PORT)]
  else:
    command = ['python', '-m', 'http.server', str(SERVER_PORT)]

  server_process = subprocess.Popen(command, stderr=subprocess.PIPE)
  print('Server process started.')
  print('Server process id: '+str(server_process.pid))
  print('Serving on port: '+str(SERVER_PORT))
  url = 'http://localhost:'+str(SERVER_PORT) + '/'
  print('Repo URL is: ' + url)

  # Host and wait.
  try:
    time.sleep(10000)

  except:
    print('Exception caught')
    pass

  finally:
    if server_process.returncode is None:
      print('Terminating server process '+str(server_process.pid))
      server_process.kill()





def clean_slate():
  """
  Delete current repository at REPO_PATH and replace it with a fresh copy of
  the clean original repository.
  """
  if os.path.exists(REPO_PATH):
    shutil.rmtree(REPO_PATH)

  shutil.copytree(CLEAN_REPO_PATH, REPO_PATH)

  # Unload any repository currently loaded.
  global repo
  repo = None





def load_repo():
  """
  Loads the repo last written to REPO_PATH.
  """
  global repo

  os.chdir(ROOT_PATH)

  repo = repotool.load_repository(REPO_NAME)

  import_all_keys()
  add_top_level_keys_to_repo()
  add_delegated_keys_to_repo()

  return repo





def create_new_repo():
  """
  Creates a fresh TUF repo for uptane, with new keys for all roles, using the
  role structure defined below, and with targets files copied from the clean
  repo.
  """
  global repo
  repo = None

  # Delete current repo if it exists.
  if os.path.exists(REPO_PATH):
    shutil.rmtree(REPO_PATH)

  os.chdir(ROOT_PATH)

  repo = repotool.create_new_repository(REPO_NAME)

  # Create key pairs for all roles.
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'root', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'time', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'snap', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'targets', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'images', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'director', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'brakes', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'acme', password="pw")
  repotool.generate_and_write_rsa_keypair(KEYS_DIR + 'cell', password="pw")

  import_all_keys()

  add_top_level_keys_to_repo()

  # Perform some delegations.
  repo.targets.delegate('images', [public_images_key],
      [], restricted_paths=[])
  repo.targets.delegate('director', [public_director_key],
      [], restricted_paths=[])
  repo.targets('images').delegate('brakes', [public_brakes_key],
      [], restricted_paths=[IMAGES_DIR + 'brakes/'])
  repo.targets('images').delegate('acme', [public_acme_key],
      [], restricted_paths=[IMAGES_DIR + 'flobinator/acme/'])
  repo.targets('images').delegate('cell', [public_cell_key],
      [], restricted_paths=[IMAGES_DIR + 'cellfw/'])

  # Perform the multi-role delegation giving Director + Images control of images.
  restricted_paths = [IMAGES_DIR]
  required_roles = ['targets/images', 'targets/director']
  repo.targets.multi_role_delegate(restricted_paths, required_roles)

  add_delegated_keys_to_repo()

  # Now we add targets, first copying the target files themselves from the
  # clean targets directory, then adding their file info to the repository.
  if os.path.exists(IMAGES_DIR):
    shutil.rmtree(IMAGES_DIR)
  shutil.copytree(CLEAN_IMAGES_DIR, IMAGES_DIR)
  repo.targets('images')('brakes').add_targets([
      IMAGES_DIR + 'brakes/E859A50_9613.zip',
      IMAGES_DIR + 'brakes/config/someconfig.cfg'])
  repo.targets('images')('cell').add_targets([
      IMAGES_DIR + 'cellfw/infotainment_adjacent_fw.zip'])
  repo.targets('images')('acme').add_targets([
      IMAGES_DIR + 'flobinator/acme/1111111.txt',
      IMAGES_DIR + 'flobinator/acme/firmware.py',
      IMAGES_DIR + 'flobinator/acme/b20.zip'])

  # Add two of those targets to the director role as well.
  repo.targets('director').add_targets([
      IMAGES_DIR + 'brakes/E859A50_9613.zip',
      IMAGES_DIR + 'flobinator/acme/firmware.py'])

  # For demo and github convenience (only!), have all metadata expire in a year.
  expiry = datetime.datetime(2017, 8, 15, 0, 0, 0)
  for role in [repo.timestamp, repo.snapshot, repo.root, repo.targets,
      repo.targets('director'), repo.targets('images'),
      repo.targets('images')('cell'), repo.targets('images')('brakes'),
      repo.targets('images')('acme')]:
    role.expiration = expiry

  # Save the repo's metadata to files.
  repo.write()

  return repo





def import_all_keys():

  global public_root_key
  global public_time_key
  global public_snap_key
  global public_targets_key
  global public_images_key
  global public_director_key
  global public_brakes_key
  global public_acme_key
  global public_cell_key
  global private_root_key
  global private_time_key
  global private_snap_key
  global private_targets_key
  global private_images_key
  global private_director_key
  global private_brakes_key
  global private_acme_key
  global private_cell_key

  # Import public and private keys from the generated files.
  public_root_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'root.pub')
  public_time_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'time.pub')
  public_snap_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'snap.pub')
  public_targets_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'targets.pub')
  private_root_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'root', password='pw')
  private_time_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'time', password='pw')
  private_snap_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'snap', password='pw')
  private_targets_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'targets', password='pw')

  # Import delegated keys.
  public_images_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'images.pub')
  public_director_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'director.pub')
  public_brakes_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'brakes.pub')
  public_acme_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'acme.pub')
  public_cell_key = repotool.import_rsa_publickey_from_file(KEYS_DIR +
      'cell.pub')
  private_images_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'images', password='pw')
  private_director_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'director', password='pw')
  private_brakes_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'brakes', password='pw')
  private_acme_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'acme', password='pw')
  private_cell_key = repotool.import_rsa_privatekey_from_file(KEYS_DIR +
      'cell', password='pw')





def add_top_level_keys_to_repo():

  global repo

  # Add public keys to repo.
  repo.root.add_verification_key(public_root_key)
  repo.timestamp.add_verification_key(public_time_key)
  repo.snapshot.add_verification_key(public_snap_key)
  repo.targets.add_verification_key(public_targets_key)

  # Add private keys to repo.
  repo.root.load_signing_key(private_root_key)
  repo.timestamp.load_signing_key(private_time_key)
  repo.snapshot.load_signing_key(private_snap_key)
  repo.targets.load_signing_key(private_targets_key)





def add_delegated_keys_to_repo():

  global repo

  # The delegation itself already added the new roles' public keys. We still have
  # to add their private keys.
  repo.targets('images').load_signing_key(private_images_key)
  repo.targets('director').load_signing_key(private_director_key)
  repo.targets('images')('brakes').load_signing_key(private_brakes_key)
  repo.targets('images')('acme').load_signing_key(private_acme_key)
  repo.targets('images')('cell').load_signing_key(private_cell_key)





#########################################
############## ATTACK CODE ##############
#########################################

def attack_invalid_target():
  """
  Attacker compromises server and simply replaces a target file.

  'flobinator/acme/firmware.py' is replaced with an exploit-carrying version.
  """

  # Replace a target with a modified vesion.
  shutil.copyfile(ATTACK_DIR + '/invalid_target_firmware.py',
      IMAGES_DIR + '/flobinator/acme/firmware.py')















def main():
  # Create a new repository of name REPO_NAME at path ROOT_PATH.

  global repo

  os.chdir(ROOT_PATH)

  clean_slate()
  host_repo()




if __name__ == '__main__':
  main()
