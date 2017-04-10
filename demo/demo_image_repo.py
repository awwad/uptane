"""
demo_image_repo.py

Demonstration code handling an OEM repository.

Use:

import demo.demo_image_repo as di
di.clean_slate()
di.write_to_live()
di.host()

# Later:
di.kill_server()




<Demo Interface Provided Via XMLRPC>

  XMLRPC interface presented TO THE DEMO WEBSITE:
    add_target_to_supplier_repo(target_filepath, filepath_in_repo)  <--- add to staged supplier repository
    write_supplier_repo() <--- move staged to live / add newly added targets to live repo


"""
from __future__ import print_function
from __future__ import unicode_literals

import demo
import uptane
import uptane.formats
import tuf.formats

import threading # for the interface for the demo website
import os
import sys, subprocess, time # For hosting and arguments
import tuf.repository_tool as rt
import shutil # for rmtree
from uptane import GREEN, RED, YELLOW, ENDCOLORS

from six.moves import xmlrpc_server # for the director services interface

import atexit # to kill server process on exit()

repo = None
server_process = None
xmlrpc_service_thread = None


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

  # TODO: <~> Re-enable delegations below. Currently, ASN1 conversion fails
  # when there are delegations. This is, of course, untenable, but for now, it
  # is more important to experiment with ASN1 than to have a sample delegation.
  # Delegate to a new Supplier.
  # repo.targets.delegate('role1', [key_role1_pub],
  #     [os.path.join(demo.MAIN_REPO_NAME, 'targets/file1.txt'),
  #      os.path.join(demo.MAIN_REPO_NAME, 'targets/infotainment_firmware.txt')],
  #     threshold=1, backtrack=True,
  #     restricted_paths=[os.path.join(demo.MAIN_REPO_TARGETS_DIR, '*')])
  # Add delegated role keys to repo
  # repo.targets('role1').load_signing_key(key_role1_pri)


  write_to_live()

  host()

  listen()




def write_to_live():

  global repo

  # Write the metadata files out to mainrepo's 'metadata.staged'
  repo.mark_dirty(['timestamp', 'snapshot'])
  repo.write() # will be writeall() in most recent TUF branch

  # Move staged metadata (from the write above) to live metadata directory.

  if os.path.exists(os.path.join(demo.MAIN_REPO_DIR, 'metadata')):
    shutil.rmtree(os.path.join(demo.MAIN_REPO_DIR, 'metadata'))

  shutil.copytree(
      os.path.join(demo.MAIN_REPO_DIR, 'metadata.staged'),
      os.path.join(demo.MAIN_REPO_DIR, 'metadata'))





def add_target_to_imagerepo(target_fname, filepath_in_repo):
  """
  For use in attacks and more specific demonstration.

  Given a filename pointing to a file in the targets directory, adds that file
  as a target file (calculating its cryptographic hash and length)

  <Arguments>
    target_fname
      The full filename of the file to be added as a target to the image
      repository's targets role metadata. This file should be in the targets
      subdirectory of the repository directory.  This doesn't employ
      delegations, which would have to be done manually.
  """
  global repo

  tuf.formats.RELPATH_SCHEMA.check_match(target_fname)


  print('Copying target file into place.')
  repo_dir = repo._repository_directory
  destination_filepath = os.path.join(repo_dir, 'targets', filepath_in_repo)

  shutil.copy(target_fname, destination_filepath)

  repo.targets.add_target(destination_filepath)





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
    command = ['python3', '-m', 'http.server', str(demo.MAIN_REPO_PORT)]


  # Begin hosting mainrepo.

  server_process = subprocess.Popen(command, stderr=subprocess.PIPE)

  os.chdir(uptane.WORKING_DIR)

  print('Main Repo server process started, with pid ' + str(server_process.pid))
  print('Main Repo serving on port: ' + str(demo.MAIN_REPO_PORT))
  url = demo.MAIN_REPO_HOST + ':' + str(demo.MAIN_REPO_PORT) + '/'
  print('Main Repo URL is: ' + url)

  # Kill server process after calling exit().
  atexit.register(kill_server)

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





# Restrict xmlrpc requests - to the interface provided for the website's use -
# to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(xmlrpc_server.SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)


def listen():
  """
  This is exclusively for the use of the demo website frontend.

  Listens on MAIN_REPO_SERVICE_PORT for xml-rpc calls to functions:
    - add_target_to_supplier_repo
    - write_supplier_repo

  Note that you must also run host() in order to serve the metadata files via
  http.
  """

  global xmlrpc_service_thread

  if xmlrpc_service_thread is not None:
    print('Sorry - there is already a Director service thread listening.')
    return

  # Create server
  server = xmlrpc_server.SimpleXMLRPCServer(
      (demo.MAIN_REPO_SERVICE_HOST, demo.MAIN_REPO_SERVICE_PORT),
      requestHandler=RequestHandler, allow_none=True)
  #server.register_introspection_functions()

  # Register functions that can be called via XML-RPC, allowing users to add
  # target files to the image repository or to simulate attacks from a web
  # frontend.
  server.register_function(add_target_to_imagerepo, 'add_target_to_supplier_repo')
  server.register_function(write_to_live, 'write_supplier_repo')
  server.register_function(mitm_arbitrary_package_attack, 'mitm_arbitrary_package_attack')
  server.register_function(undo_mitm_arbitrary_package_attack,
      'undo_mitm_arbitrary_package_attack')

  print('Starting Supplier Repo Services Thread: will now listen on port ' +
      str(demo.MAIN_REPO_SERVICE_PORT))
  xmlrpc_service_thread = threading.Thread(target=server.serve_forever)
  xmlrpc_service_thread.setDaemon(True)
  xmlrpc_service_thread.start()




def mitm_arbitrary_package_attack(target_filepath):
  # Simulate an arbitrary package attack by a Man in the Middle, without
  # compromising keys.  Move evil target file into place on the image
  # repository, without updating metadata.
  full_target_filepath = os.path.join(demo.MAIN_REPO_TARGETS_DIR, target_filepath)

  # TODO: NOTE THAT THIS ATTACK SCRIPT BREAKS IF THE TARGET FILE IS IN A
  # SUBDIRECTORY IN THE REPOSITORY.
  backup_target_filepath = os.path.join(demo.MAIN_REPO_TARGETS_DIR,
      'backup_' + target_filepath)


  if not os.path.exists(full_target_filepath):
    raise Exception('The provided target file is not already in either the '
        'Director or Image repositories. This attack is intended to be run on '
        'an existing target that is already set to be delivered to a client.')

  elif os.path.exists(backup_target_filepath):
    raise Exception('The attack is already in progress, or was never recovered '
        'from. Not running twice. Please check state and if everything is '
        'otherwise okay, delete ' + repr(backup_target_filepath))

  # If the image file exists already on the image repository (not necessary),
  # then back it up.
  if os.path.exists(full_target_filepath):
    shutil.copy(full_target_filepath, backup_target_filepath)

  with open(full_target_filepath, 'w') as fobj:
    fobj.write('EVIL UPDATE: ARBITRARY PACKAGE ATTACK TO BE DELIVERED FROM '
        'MITM / bad mirror (no keys compromised).')

  # Delete the arbitrary image file from any of the Director repositories, if
  # it exists.  If the evil file is found in the Director repo by the
  # secondary, a banner is not printed because the evil file provided by the
  # image repository is rejected but not from the director repo.
  for root_directory, subdirectories, files in os.walk(demo.DIRECTOR_REPO_DIR):
    for subdirectory in subdirectories:
      repo_directory = os.path.join(root_directory, subdirectory)
      evil_file_in_director_repo = os.path.join(repo_directory, target_filepath)

      if os.path.exists(evil_file_in_director_repo):
        os.remove(evil_file_in_director_repo)



def undo_mitm_arbitrary_package_attack(target_filepath):
  # Undo the arbitrary package attack simulated by mitm_arbitrary_package_attack().
  # Move the evil target file out and normal target file back in.
  full_target_filepath = os.path.join(demo.MAIN_REPO_TARGETS_DIR, target_filepath)

  # TODO: NOTE THAT THIS ATTACK SCRIPT BREAKS IF THE TARGET FILE IS IN A
  # SUBDIRECTORY IN THE REPOSITORY.
  backup_target_filepath = os.path.join(demo.MAIN_REPO_TARGETS_DIR,
      'backup_' + target_filepath)

  if not os.path.exists(full_target_filepath) or not os.path.exists(backup_target_filepath):
    raise Exception('The expected backup or attacked files do not exist. No '
        'attack is in progress to undo, or manual manipulation has '
        'broken the expected state.')

  # In the case of the Director repo, we expect there to be a file replaced,
  # so we restore the backup over it.
  os.rename(backup_target_filepath, full_target_filepath)





def add_target_and_write_to_live(filename, file_content):
  """
  High-level version of add_target_to_imagerepo() that creates the target
  file, and writes the changes to the live repository.
  """

  # Create 'filename' in the current working directory, but it should
  # ideally be to a temporary destination.  The demo code will eventually
  # be modified to use temporary directories (which will cleaned up after
  # running demo code).
  with open(filename, 'w') as file_object:
    file_object.write(file_content)

  filepath_in_repo = filename
  add_target_to_imagerepo(filename, filepath_in_repo)
  write_to_live()





def revoke_and_add_new_keys_and_write_to_live():
  """
  <Purpose>
    Revoke the current Timestamp, Snapshot, and Targets keys, and add a new keys
    for each role.  This is a high-level version of the common function to
    update a role key.

  <Arguments>
    None.

  <Exceptions>
    None.

  <Side Effecs>
    None.

  <Returns>
    None.
  """

  global repo

  # Grab the old public keys.
  old_targets_public_key = demo.import_public_key('maintargets')
  old_timestamp_public_key = demo.import_public_key('maintimestamp')
  old_snapshot_public_key = demo.import_public_key('mainsnapshot')


  # Disassociate the old public keys from the roles.
  repo.targets.remove_verification_key(old_targets_public_key)
  repo.timestamp.remove_verification_key(old_timestamp_public_key)
  repo.snapshot.remove_verification_key(old_snapshot_public_key)


  # Generate new public and private keys and import them.
  demo.generate_key('maintargets')
  new_targets_public_key = demo.import_public_key('maintargets')
  new_targets_private_key = demo.import_private_key('maintargets')

  demo.generate_key('maintimestamp')
  new_timestamp_public_key = demo.import_public_key('maintimestamp')
  new_timestamp_private_key = demo.import_private_key('maintimestamp')

  demo.generate_key('mainsnapshot')
  new_snapshot_public_key = demo.import_public_key('mainsnapshot')
  new_snapshot_private_key = demo.import_private_key('mainsnapshot')


  # Associate the new public keys with the roles.
  repo.targets.add_verification_key(new_targets_public_key)
  repo.timestamp.add_verification_key(new_timestamp_public_key)
  repo.snapshot.add_verification_key(new_snapshot_public_key)

  # Load the new signing keys to write metadata. The root key is unchanged,
  # and in the demo it is already loaded.
  repo.targets.load_signing_key(new_targets_private_key)
  repo.snapshot.load_signing_key(new_snapshot_private_key)
  repo.timestamp.load_signing_key(new_timestamp_private_key)

  # Write all the metadata changes to disk.  Note: write() will be writeall()
  # in the latest version of the TUF codebase.
  repo.write()





def kill_server():
  global server_process
  if server_process is None:
    print('No server to stop.')
    return

  else:
    print('Killing server process with pid: ' + str(server_process.pid))
    server_process.kill()
    server_process = None
