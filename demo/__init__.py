"""
__init__.py for the Uptane demo package
"""
from __future__ import unicode_literals

import uptane
import os
import tuf.formats
import tuf.repository_tool as rt
import random, string # To generate random strings for Secondary directory names

from six.moves import range

DEMO_DIR = os.path.join(uptane.WORKING_DIR, 'demo')
DEMO_KEYS_DIR = os.path.join(DEMO_DIR, 'keys')
DEMO_PINNING_FNAME = os.path.join(DEMO_DIR, 'pinned.json')
DEMO_SECONDARY_PINNING_FNAME = os.path.join(DEMO_DIR, 'pinned_secondary_template.json')
DEMO_PRIMARY_PINNING_FNAME = os.path.join(DEMO_DIR, 'pinned_primary_template.json')

MAIN_REPO_HOST = 'localhost' #'http://192.168.1.124'
MAIN_REPO_PORT = 30301
MAIN_REPO_NAME = 'mainrepo'
MAIN_REPO_DIR = os.path.join(uptane.WORKING_DIR, MAIN_REPO_NAME)
MAIN_REPO_TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
MAIN_REPO_ROOT_FNAME = os.path.join(MAIN_REPO_DIR, 'metadata', 'root.json')

DIRECTOR_REPO_HOST = 'localhost' #'http://192.168.1.124'
DIRECTOR_REPO_PORT = 30401
DIRECTOR_REPO_NAME = 'director'
DIRECTOR_REPO_DIR = os.path.join(uptane.WORKING_DIR, DIRECTOR_REPO_NAME)

DIRECTOR_SERVER_HOST = '0.0.0.0' #'localhost'
DIRECTOR_SERVER_PORT = 30501

# These two are are being added solely to provide an interface to the demo web
# frontend.
MAIN_REPO_SERVICE_HOST = 'localhost'
MAIN_REPO_SERVICE_PORT = 30309

TIMESERVER_HOST = '0.0.0.0' #'localhost'
TIMESERVER_PORT = 30601

PRIMARY_SERVER_HOST = 'localhost'
PRIMARY_SERVER_DEFAULT_PORT = 30701
PRIMARY_SERVER_AVAILABLE_PORTS = [
    30701, 30702, 30703, 30704, 30705, 30706, 30707, 30708, 30709, 30710, 30711]

SECONDARY_SERVER_HOST = 'localhost'
SECONDARY_SERVER_PORT = 30801



def generate_key(keyname):
  """
  Generate a key pair according to the demo's current default key config.

    Passphrase: 'pw'
    Key type: ed25519
    Key location: DEMO_KEYS_DIR
  """
  rt.generate_and_write_ed25519_keypair(
      os.path.join(DEMO_KEYS_DIR, keyname), password='pw')



def import_public_key(keyname):
  """
  Import a public key according to the demo's current default key config.
  The keyname does not include '.pub'; it matches that used for the other
  functions here.

    Key type: ed25519
    Key location: DEMO_KEYS_DIR
  """
  return rt.import_ed25519_publickey_from_file(
      os.path.join(DEMO_KEYS_DIR, keyname + '.pub'))



def import_private_key(keyname):
  """
  Import a private key according to the demo's current default key config.

    Passphrase: 'pw'
    Key type: ed25519
    Key location: DEMO_KEYS_DIR
  """
  return rt.import_ed25519_privatekey_from_file(
      os.path.join(DEMO_KEYS_DIR, keyname), password='pw')



def get_random_string(length):
  """
  Returns a random alphanumeric string of length length. Not
  cryptographically reliable.
  """
  return ''.join(
      random.choice(string.ascii_uppercase + string.ascii_lowercase +
      string.digits) for i in range(length))

