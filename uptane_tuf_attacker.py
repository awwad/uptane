"""
<Program Name>
  uptane_tuf_attacker.py

<Purpose>
  Attack an UPTANE server/client.

"""

import tuf
import tuf.repository_tool as repotool
import tuf.client.updater
import os # for chdir
import shutil # for copying
import subprocess # for hosting
import time # for sleep
import sys # for python version
import datetime # for metadata expiration times




import uptane_tuf_server as uts

from uptane_tuf_server import ROOT_PATH, REPO_NAME, REPO_PATH, SERVER_PORT
from uptane_tuf_server import METADATA_STAGED_PATH, METADATA_LIVE_PATH
from uptane_tuf_server import IMAGES_DIR


# Constants
ATTACK_DIR = ROOT_PATH + '/attack_data'
EVIL_REPO_NAME = 'temp_evilrepo'
EVIL_REPO_PATH = ROOT_PATH + '/' + EVIL_REPO_NAME
EVIL_METADATA_STAGED_PATH = EVIL_REPO_PATH + '/metadata.staged'
#EVIL_METADATA_LIVE_PATH = EVIL_REPO_PATH + '/metadata'
EVIL_KEYS_DIR = EVIL_REPO_PATH + '/keys/'
EVIL_IMAGES_DIR = EVIL_REPO_PATH + '/targets/images/'
#EVIL_SERVER_PORT = 33331

CLEAN_EVIL_REPO_NAME = 'clean_evilrepo'
CLEAN_EVIL_REPO_PATH = ROOT_PATH + '/' + CLEAN_EVIL_REPO_NAME
CLEAN_EVIL_METADATA_PATH = CLEAN_EVIL_REPO_PATH + '/metadata'
CLEAN_EVIL_KEYS_DIR = CLEAN_EVIL_REPO_PATH + '/keys/'
CLEAN_EVIL_IMAGES_DIR = CLEAN_EVIL_REPO_PATH + '/targets/images/'



# Globals
repo = None # The attacker's version of the repository.
#url = 'http://localhost:'+str(EVIL_SERVER_PORT) + '/'
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



def attack_invalid_target():
  """
  Attacker compromises server and simply replaces a target file.

  'flobinator/acme/firmware.py' is replaced with an exploit-carrying version.
  """

  # Replace a target with a modified vesion.
  shutil.copyfile(ATTACK_DIR + '/firmware_backdoor.py',
      IMAGES_DIR + '/brakes/firmware.py')


def attack_director_arbitrary_new():
  # Use a compromised director key to instruct a vehicle to install an
  # arbitrary target.

  # shutil.copyfile(ATTACK_DIR + '/director_arbitrary_new.json',
  #     METADATA_LIVE_PATH + '/targets/director.json')

  shutil.copyfile(EVIL_METADATA_STAGED_PATH + '/targets/director.json',
      METADATA_LIVE_PATH + '/targets/director.json')


  # Bleh. Have attacker pretend that the version of the director role
  # metadata hasn't changed, to get around the below.
  # # This is not really part of the attack, but it is currently required because
  # # the director role metadata is part of snapshot at the moment.
  # # That's not in the long-term design.
  # # Consequently, since snapshot has to be updated, timestamp also has to be
  # # updated. /:
  # # So the scenario we'll deal with will be Director + Timestamp + Snapshot.
  # shutil.copyfile(EVIL_METADATA_STAGED_PATH + '/snapshot.json',
  #     METADATA_LIVE_PATH + '/snapshot.json')
  # shutil.copyfile(EVIL_METADATA_STAGED_PATH + '/timestamp.json',
  #     METADATA_LIVE_PATH + '/timestamp.json')



#########################################
##### REPOSITORY CORE FUNCTIONALITY #####
#########################################

def clean_slate():
  """
  Delete current repository at REPO_PATH and replace it with a fresh copy of
  the clean original repository.
  """
  if os.path.exists(EVIL_REPO_PATH):
    shutil.rmtree(EVIL_REPO_PATH)

  shutil.copytree(CLEAN_EVIL_REPO_PATH, EVIL_REPO_PATH)

  # Unload any repository currently loaded.
  global repo
  repo = None





def clean_slate():
  """
  Delete current repository at REPO_PATH and replace it with a fresh copy of
  the clean original repository.
  """
  if os.path.exists(EVIL_REPO_PATH):
    shutil.rmtree(EVIL_REPO_PATH)

  shutil.copytree(CLEAN_EVIL_REPO_PATH, EVIL_REPO_PATH)

  # Unload any repository currently loaded.
  global repo
  repo = None






def load_repo():
  """
  Loads the repo last written to REPO_PATH.
  """
  global repo

  os.chdir(ROOT_PATH)

  repo = repotool.load_repository(EVIL_REPO_NAME)

  import_online_keys()
  add_online_keys_to_repo()

  return repo





def add_online_keys_to_repo():

  global repo

  # Add public keys to repo.
  repo.root.add_verification_key(public_root_key)
  repo.timestamp.add_verification_key(public_time_key)
  repo.snapshot.add_verification_key(public_snap_key)
  repo.targets.add_verification_key(public_targets_key)

  # Add private keys to repo.
  repo.timestamp.load_signing_key(private_time_key)
  repo.snapshot.load_signing_key(private_snap_key)

  repo.targets('director').load_signing_key(private_director_key)



def import_online_keys(online_only=True):

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
  public_root_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'root.pub')
  public_time_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'time.pub')
  public_snap_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'snap.pub')
  public_targets_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'targets.pub')
  private_time_key = repotool.import_rsa_privatekey_from_file(EVIL_KEYS_DIR +
      'time', password='pw')
  private_snap_key = repotool.import_rsa_privatekey_from_file(EVIL_KEYS_DIR +
      'snap', password='pw')
  if not online_only:
    private_root_key = repotool.import_rsa_privatekey_from_file(
        KEYS_OFFLINE_DIR + 'root', password='pw')
    private_targets_key = repotool.import_rsa_privatekey_from_file(
        KEYS_OFFLINE_DIR + 'targets', password='pw')

  # Import delegated keys.
  public_images_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'images.pub')
  public_director_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'director.pub')
  public_brakes_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'brakes.pub')
  public_acme_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'acme.pub')
  public_cell_key = repotool.import_rsa_publickey_from_file(EVIL_KEYS_DIR +
      'cell.pub')
  private_director_key = repotool.import_rsa_privatekey_from_file(EVIL_KEYS_DIR +
      'director', password='pw')
  if not online_only:
    private_images_key = repotool.import_rsa_privatekey_from_file(
        KEYS_OFFLINE_DIR + 'images', password='pw')
    private_brakes_key = repotool.import_rsa_privatekey_from_file(
        KEYS_OFFLINE_DIR + 'brakes', password='pw')
    private_acme_key = repotool.import_rsa_privatekey_from_file(
        KEYS_OFFLINE_DIR + 'acme', password='pw')
    private_cell_key = repotool.import_rsa_privatekey_from_file(
        KEYS_OFFLINE_DIR + 'cell', password='pw')
