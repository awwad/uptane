"""
demo_director_repo.py

Demonstration code handling a Director repository.
"""

import os # For paths and symlink
import shutil # For copying directory trees
import sys, subprocess, time # For hosting
import tuf.repository_tool as rt
import demo_oem_repo

WORKING_DIR = os.getcwd()

MAIN_REPO_DIR = demo_oem_repo.MAIN_REPO_DIR
DIRECTOR_REPO_NAME = 'repodirector'
DIRECTOR_REPO_DIR = os.path.join(WORKING_DIR, DIRECTOR_REPO_NAME)
TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
DIRECTOR_REPO_HOST = 'http://localhost'
DIRECTOR_REPO_PORT = 30401

repo = None
server_process = None



def clean_slate(
  use_new_keys=False,
  additional_root_key=False,
  additional_targets_key=False):

  global repo

  # Create repo at './repodirector'

  repo = rt.create_new_repository(DIRECTOR_REPO_NAME)


  # Create keys and/or load keys into memory.

  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('directorroot', password='pw')
    rt.generate_and_write_ed25519_keypair('directortimestamp', password='pw')
    rt.generate_and_write_ed25519_keypair('directorsnapshot', password='pw')
    rt.generate_and_write_ed25519_keypair('director', password='pw') # targets
    if additional_root_key:
      rt.generate_and_write_ed25519_keypair('directorroot2', password='pw')
    if additional_targets_key:
      rt.generate_and_write_ed25519_keypair('director2', password='pw')

  key_dirroot_pub = rt.import_ed25519_publickey_from_file('directorroot.pub')
  key_dirroot_pri = rt.import_ed25519_privatekey_from_file('directorroot', password='pw')
  key_dirtime_pub = rt.import_ed25519_publickey_from_file('directortimestamp.pub')
  key_dirtime_pri = rt.import_ed25519_privatekey_from_file('directortimestamp', password='pw')
  key_dirsnap_pub = rt.import_ed25519_publickey_from_file('directorsnapshot.pub')
  key_dirsnap_pri = rt.import_ed25519_privatekey_from_file('directorsnapshot', password='pw')
  key_dirtarg_pub = rt.import_ed25519_publickey_from_file('director.pub')
  key_dirtarg_pri = rt.import_ed25519_privatekey_from_file('director', password='pw')
  key_dirroot2_pub = None
  key_dirroot2_pri = None
  if additional_root_key:
    key_dirroot2_pub = rt.import_ed25519_publickey_from_file('directorroot2.pub')
    key_dirroot2_pri = rt.import_ed25519_privatekey_from_file('directorroot2', password='pw')
  if additional_targets_key:
    key_dirtarg2_pub = rt.import_ed25519_publickey_from_file('director2.pub')
    key_dirtarg2_pri = rt.import_ed25519_privatekey_from_file('director2', password='pw')


  # Add top level keys to the main repository.

  repo.root.add_verification_key(key_dirroot_pub)
  repo.timestamp.add_verification_key(key_dirtime_pub)
  repo.snapshot.add_verification_key(key_dirsnap_pub)
  repo.targets.add_verification_key(key_dirtarg_pub)
  repo.root.load_signing_key(key_dirroot_pri)
  repo.timestamp.load_signing_key(key_dirtime_pri)
  repo.snapshot.load_signing_key(key_dirsnap_pri)
  repo.targets.load_signing_key(key_dirtarg_pri)
  if additional_targets_key:
    repo.targets.add_verification_key(key_dirtarg2_pub)
    repo.targets.load_signing_key(key_dirtarg2_pri)
  if additional_root_key:
    repo.root.add_verification_key(key_dirroot2_pub)
    repo.root.load_signing_key(key_dirroot2_pri)


  # Add target to director.
  # FOR NOW, we symlink the targets files on the director.
  # In the future, we probably have to have the repository tools add a function
  # like targets.add_target_from_metadata that doesn't require an actual target
  # file to exist, but instead provides metadata on some hypothetical file that
  # the director may not physically hold.
  if os.path.exists(os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt')):
    os.remove(os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt'))

  os.symlink(os.path.join(TARGETS_DIR, 'file2.txt'),
      os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt'))

  repo.targets.add_target(
      os.path.join(DIRECTOR_REPO_DIR, 'targets', 'file2.txt'),
      custom={"ecu-serial-number": "some_ecu_serial", "type": "application"})





def write_to_live():

  global repo

  # Write to director repo's metadata.staged.
  repo.write()


  # Move staged metadata (from the write) to live metadata directory.

  if os.path.exists(os.path.join(DIRECTOR_REPO_DIR, 'metadata')):
    shutil.rmtree(os.path.join(DIRECTOR_REPO_DIR, 'metadata'))

  shutil.copytree(
      os.path.join(DIRECTOR_REPO_DIR, 'metadata.staged'),
      os.path.join(DIRECTOR_REPO_DIR, 'metadata'))

  # TODO: <~> Call the encoders here to convert the metadata files into BER
  # versions and also host those!





def host():

  global server_process

  # Prepare to host the director repo contents.

  os.chdir(DIRECTOR_REPO_DIR)

  command = []
  if sys.version_info.major < 3: # Python 2 compatibility
    command = ['python', '-m', 'SimpleHTTPServer', str(DIRECTOR_REPO_PORT)]
  else:
    command = ['python', '-m', 'http.server', str(DIRECTOR_REPO_PORT)]


  # Begin hosting the director's repository.

  server_process = subprocess.Popen(command, stderr=subprocess.PIPE)

  os.chdir(WORKING_DIR)

  print('Director repo server process started, with pid ' + str(server_process.pid))
  print('Director repo serving on port: ' + str(DIRECTOR_REPO_PORT))
  url = DIRECTOR_REPO_HOST + ':' + str(DIRECTOR_REPO_PORT) + '/'
  print('Director repo URL is: ' + url)

  # Wait / allow any exceptions to kill the server.
  # try:
  #   time.sleep(1000000) # Stop hosting after a while.
  # except:
  #   print('Exception caught')
  #   pass
  # finally:
  #   if server_process.returncode is None:
  #     print('Terminating Director repo server process ' + str(server_process.pid))
  #     server_process.kill()





def kill_server():

  global server_process

  if server_process is None:
    print('No server to stop.')
    return

  else:
    print('Killing server process with pid: ' + str(server_process.pid))
    server_process.kill()
