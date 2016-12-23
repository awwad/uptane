"""
demo_oem_repo.py

Demonstration code handling an OEM repository.

Use:

import demo.demo_oem_repo as do
do.clean_slate()
do.write_to_live()
do.host()

# Later:
do.kill_server()

"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open

import demo
import uptane
import uptane.formats
import tuf.formats
import os
import sys, subprocess, time # For hosting and arguments
import tuf.repository_tool as rt
import shutil # for rmtree
from uptane import GREEN, RED, YELLOW, ENDCOLORS


repo = None
server_process = None


def clean_slate(use_new_keys=False):

  global repo

  # Create target files: file1.txt and infotainment_firmware.txt

  if os.path.exists(demo.MAIN_REPO_TARGETS_DIR):
    shutil.rmtree(demo.MAIN_REPO_TARGETS_DIR)

  os.makedirs(demo.MAIN_REPO_TARGETS_DIR)

  fobj = open(os.path.join(demo.MAIN_REPO_TARGETS_DIR, 'file1.txt'), 'w')
  fobj.write('Contents of file1.txt')
  fobj.close()
  fobj = open(os.path.join(demo.MAIN_REPO_TARGETS_DIR, 'infotainment_firmware.txt'), 'w')
  fobj.write('Contents of infotainment_firmware.txt')
  fobj.close()


  # Create repo at './repomain'

  repo = rt.create_new_repository(demo.MAIN_REPO_NAME)


  # Create keys and/or load keys into memory.

  if use_new_keys:
    demo.generate_key('mainroot')
    demo.generate_key('maintimestamp')
    demo.generate_key('mainsnapshot')
    demo.generate_key('maintargets')
    demo.generate_key('mainrole1')

  key_root_pub = demo.import_public_key('mainroot')
  key_root_pri = demo.import_private_key('mainroot')
  key_timestamp_pub = demo.import_public_key('maintimestamp')
  key_timestamp_pri = demo.import_private_key('maintimestamp')
  key_snapshot_pub = demo.import_public_key('mainsnapshot')
  key_snapshot_pri = demo.import_private_key('mainsnapshot')
  key_targets_pub = demo.import_public_key('maintargets')
  key_targets_pri = demo.import_private_key('maintargets')
  key_role1_pub = demo.import_public_key('mainrole1')
  key_role1_pri = demo.import_private_key('mainrole1')


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
      [os.path.join(demo.MAIN_REPO_NAME, 'targets/file1.txt'),
       os.path.join(demo.MAIN_REPO_NAME, 'targets/infotainment_firmware.txt')],
      threshold=1, backtrack=True,
      restricted_paths=[os.path.join(demo.MAIN_REPO_TARGETS_DIR, '*')])


  # Add delegated role keys to repo

  repo.targets('role1').load_signing_key(key_role1_pri)


  host()
  write_to_live()





def write_to_live():

  global repo

  # Write the metadata files out to mainrepo's 'metadata.staged'
  repo.write()

  # Move staged metadata (from the write above) to live metadata directory.

  if os.path.exists(os.path.join(demo.MAIN_REPO_DIR, 'metadata')):
    shutil.rmtree(os.path.join(demo.MAIN_REPO_DIR, 'metadata'))

  shutil.copytree(
      os.path.join(demo.MAIN_REPO_DIR, 'metadata.staged'),
      os.path.join(demo.MAIN_REPO_DIR, 'metadata'))





def add_target_to_oemrepo(target_fname):
  """
  For use in attacks and more specific demonstration.

  Given a filename pointing to a file in the targets directory, adds that file
  as a target file (calculating its cryptographic hash and length)

  <Arguments>
    target_fname
      The full filename of the file to be added as a target to the OEM's
      targets role metadata. This file should be in the targets subdirectory of
      the repository directory.
      This doesn't employ delegations, which would have to be done manually.
  """
  global repo

  tuf.formats.RELPATH_SCHEMA.check_match(target_fname)

  repo.targets.add_target(target_fname)





def host():

  global server_process

  if server_process is not None:
    print('Sorry, there is already a server process running.')
    return

  # Prepare to host the main repo contents

  os.chdir(demo.MAIN_REPO_DIR)

  command = []
  if sys.version_info.major < 3:  # Python 2 compatibility
    command = ['python', '-m', 'SimpleHTTPServer', str(demo.MAIN_REPO_PORT)]
  else:
    command = ['python', '-m', 'http.server', str(demo.MAIN_REPO_PORT)]


  # Begin hosting mainrepo.

  server_process = subprocess.Popen(command, stderr=subprocess.PIPE)

  os.chdir(uptane.WORKING_DIR)

  print('Main Repo server process started, with pid ' + str(server_process.pid))
  print('Main Repo serving on port: ' + str(demo.MAIN_REPO_PORT))
  url = demo.MAIN_REPO_HOST + ':' + str(demo.MAIN_REPO_PORT) + '/'
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
    repo_server_process = None
