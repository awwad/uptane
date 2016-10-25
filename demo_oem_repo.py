"""
demo_oem_repo.py

Demonstration code handling an OEM repository.
"""

import os
import sys, subprocess, time # For hosting and arguments
import tuf.repository_tool as rt
import shutil # for rmtree

WORKING_DIR = os.getcwd()

MAIN_REPO_NAME = 'repomain'
MAIN_REPO_DIR = os.path.join(WORKING_DIR, MAIN_REPO_NAME)
TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
MAIN_REPO_HOST = 'http://192.168.1.124'
MAIN_REPO_PORT = 30301

repo = None
server_process = None



def clean_slate(use_new_keys=False):
  
  global repo

  # Create target files: file1.txt and infotainment_firmware.txt

  if os.path.exists(TARGETS_DIR):
    shutil.rmtree(TARGETS_DIR)

  os.makedirs(TARGETS_DIR)

  fobj = open(os.path.join(TARGETS_DIR, 'file1.txt'), 'w')
  fobj.write('Contents of file1.txt')
  fobj.close()
  fobj = open(os.path.join(TARGETS_DIR, 'infotainment_firmware.txt'), 'w')
  fobj.write('Contents of infotainment_firmware.txt')
  fobj.close()


  # Create repo at './repomain'

  repo = rt.create_new_repository(MAIN_REPO_NAME)


  # Create keys and/or load keys into memory.

  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('mainroot', password='pw')
    rt.generate_and_write_ed25519_keypair('maintimestamp', password='pw')
    rt.generate_and_write_ed25519_keypair('mainsnapshot', password='pw')
    rt.generate_and_write_ed25519_keypair('maintargets', password='pw')
    rt.generate_and_write_ed25519_keypair('mainrole1', password='pw')

  key_root_pub = rt.import_ed25519_publickey_from_file('mainroot.pub')
  key_root_pri = rt.import_ed25519_privatekey_from_file('mainroot', password='pw')
  key_timestamp_pub = rt.import_ed25519_publickey_from_file('maintimestamp.pub')
  key_timestamp_pri = rt.import_ed25519_privatekey_from_file('maintimestamp', password='pw')
  key_snapshot_pub = rt.import_ed25519_publickey_from_file('mainsnapshot.pub')
  key_snapshot_pri = rt.import_ed25519_privatekey_from_file('mainsnapshot', password='pw')
  key_targets_pub = rt.import_ed25519_publickey_from_file('maintargets.pub')
  key_targets_pri = rt.import_ed25519_privatekey_from_file('maintargets', password='pw')
  key_role1_pub = rt.import_ed25519_publickey_from_file('mainrole1.pub')
  key_role1_pri = rt.import_ed25519_privatekey_from_file('mainrole1', password='pw')


  # Add top level keys to the main repository.

  repo.root.add_verification_key(key_root_pub)
  repo.timestamp.add_verification_key(key_timestamp_pub)
  repo.snapshot.add_verification_key(key_snapshot_pub)
  repo.targets.add_verification_key(key_targets_pub)
  repo.root.load_signing_key(key_root_pri)
  repo.timestamp.load_signing_key(key_timestamp_pri)
  repo.snapshot.load_signing_key(key_snapshot_pri)
  repo.targets.load_signing_key(key_targets_pri)


  # Perform delegation from mainrepo's targets role to mainrepo's role1 role.

  # Delegate to a new Supplier.
  repo.targets.delegate('role1', [key_role1_pub],
      [os.path.join(MAIN_REPO_NAME, 'targets/file1.txt'),
       os.path.join(MAIN_REPO_NAME, 'targets/infotainment_firmware.txt')],
      threshold=1, backtrack=True,
      restricted_paths=[os.path.join(TARGETS_DIR, '*')])


  # Add delegated role keys to repo

  repo.targets('role1').load_signing_key(key_role1_pri)





def write_to_live():

  global repo

  # Write the metadata files out to mainrepo's 'metadata.staged'
  repo.write()

  # Move staged metadata (from the write above) to live metadata directory.

  if os.path.exists(os.path.join(MAIN_REPO_DIR, 'metadata')):
    shutil.rmtree(os.path.join(MAIN_REPO_DIR, 'metadata'))

  shutil.copytree(
      os.path.join(MAIN_REPO_DIR, 'metadata.staged'),
      os.path.join(MAIN_REPO_DIR, 'metadata'))





def host():

  global server_process

  # Prepare to host the main repo contents

  os.chdir(MAIN_REPO_DIR)

  command = []
  if sys.version_info.major < 3:  # Python 2 compatibility
    command = ['python', '-m', 'SimpleHTTPServer', str(MAIN_REPO_PORT)]
  else:
    command = ['python', '-m', 'http.server', str(MAIN_REPO_PORT)]


  # Begin hosting mainrepo.

  server_process = subprocess.Popen(command, stderr=subprocess.PIPE)

  os.chdir(WORKING_DIR)

  print('Main Repo server process started, with pid ' + str(server_process.pid))
  print('Main Repo serving on port: ' + str(MAIN_REPO_PORT))
  url = MAIN_REPO_HOST + ':' + str(MAIN_REPO_PORT) + '/'
  print('Main Repo URL is: ' + url)

  # Wait / allow any exceptions to kill the server.
  #try:
  #  time.sleep(1000000) # Stop hosting after a while.
  #except:
  #  print('Exception caught')
  #  pass
  #finally:
  #  if server_process.returncode is None:
  #    print('Terminating Main Repo server process ' + str(server_process.pid))
  #    server_process.kill()





def kill_server():
  global server_process
  if server_process is None:
    print('No server to stop.')
    return

  else:
    print('Killing server process with pid: ' + str(server_process.pid))
    server_process.kill()
