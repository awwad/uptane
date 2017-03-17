"""
<Program Name>
  demo_director_repo.py

<Purpose>
  Demonstration code handling a Director repository and services.

  Runs an Uptane-compliant demonstration Director.
  This accepts and validates ECU and Vehicle Manifests and writes and hosts
  metadata.

  Use:
import demo.demo_director as dd
dd.clean_slate()

  Cleanup: (Note that this kills the metadata http hosting process, but does
            not stop the XMLRPC-serving thread.)
demo_director.kill_server()

  Various attacks / manipulations can be performed before the server is killed.
  Some of these are discussed in uptane_test_instructions.py.


<Demo Interfaces Provided Via XMLRPC>

  XMLRPC interface presented TO PRIMARIES:
    register_ecu_serial(ecu_serial, ecu_public_key, vin, is_primary=False)
    submit_vehicle_manifest(vin, ecu_serial, signed_ecu_manifest)

  XMLRPC interface presented TO THE DEMO WEBSITE:
    add_new_vehicle(vin)
    add_target_to_director(target_filepath, filepath_in_repo, vin, ecu_serial) <--- assign to vehicle
    write_director_repo() <--- move staged to live / add newly added targets to live repo
    get_last_vehicle_manifest(vin)
    get_last_ecu_manifest(ecu_serial)
    register_ecu_serial(ecu_serial, ecu_key, vin, is_primary=False)


"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open

import demo
import uptane
import uptane.services.director as director
import uptane.services.inventorydb as inventory
import tuf.formats

import tuf.asn1_codec as asn1_codec

import threading # for the director services interface
import os # For paths and symlink
import shutil # For copying directory trees
import sys, subprocess, time # For hosting
import tuf.repository_tool as rt
import demo.demo_oem_repo as demo_oem_repo # for the main repo directory /:
from uptane import GREEN, RED, YELLOW, ENDCOLORS

from six.moves import xmlrpc_server # for the director services interface
import six

KNOWN_VINS = ['111', '112', '113']

# Dynamic global objects
#repo = None
repo_server_process = None
director_service_instance = None
director_service_thread = None


def clean_slate(use_new_keys=False):

  global director_service_instance


  director_dir = os.path.join(uptane.WORKING_DIR, 'director')

  # Create a directory for the Director's files.
  if os.path.exists(director_dir):
    shutil.rmtree(director_dir)
  os.makedirs(director_dir)


  # Create keys and/or load keys into memory.

  if use_new_keys:
    demo.generate_key('directorroot')
    demo.generate_key('directortimestamp')
    demo.generate_key('directorsnapshot')
    demo.generate_key('director') # targets


  key_dirroot_pub = demo.import_public_key('directorroot')
  key_dirroot_pri = demo.import_private_key('directorroot')
  key_dirtime_pub = demo.import_public_key('directortimestamp')
  key_dirtime_pri = demo.import_private_key('directortimestamp')
  key_dirsnap_pub = demo.import_public_key('directorsnapshot')
  key_dirsnap_pri = demo.import_private_key('directorsnapshot')
  key_dirtarg_pub = demo.import_public_key('director')
  key_dirtarg_pri = demo.import_private_key('director')


  # Create the demo Director instance.
  director_service_instance = director.Director(
      director_repos_dir=director_dir,
      key_root_pri=key_dirroot_pri,
      key_root_pub=key_dirroot_pub,
      key_timestamp_pri=key_dirtime_pri,
      key_timestamp_pub=key_dirtime_pub,
      key_snapshot_pri=key_dirsnap_pri,
      key_snapshot_pub=key_dirsnap_pub,
      key_targets_pri=key_dirtarg_pri,
      key_targets_pub=key_dirtarg_pub)

  for vin in KNOWN_VINS:
    director_service_instance.add_new_vehicle(vin)

  # You can tell the Director about ECUs this way:
  # test_ecu_public_key = demo.import_public_key('secondary')
  # test_ecu_serial = 'ecu11111'
  # director_service_instance.register_ecu_serial(
  #     test_ecu_serial, test_ecu_public_key, vin='111')



  # Add a first target file, for use by every ECU in every vehicle in that the
  # Director starts off with. (Currently 3)
  # This copies the file to each repository's targets directory from the
  # main repository.
  for vin in inventory.ecus_by_vin:
    for ecu in inventory.ecus_by_vin[vin]:
      add_target_to_director(
          os.path.join(demo.MAIN_REPO_TARGETS_DIR, 'infotainment_firmware.txt'),
          'infotainment_firmware.txt',
          vin,
          ecu)

  write_to_live()

  host()

  listen()





def write_to_live(vin_to_update=None):
  # Release updated metadata.

  global director_service_instance

  # For each vehicle repository:
  #   - write metadata.staged
  #   - copy metadata.staged to the live metadata directory
  for vin in director_service_instance.vehicle_repositories:
    if vin_to_update is not None and vin != vin_to_update:
      continue
    repo = director_service_instance.vehicle_repositories[vin]
    repo_dir = repo._repository_directory

    repo.mark_dirty(['timestamp', 'snapshot'])
    repo.write() # will be writeall() in most recent TUF branch

    assert(os.path.exists(os.path.join(repo_dir, 'metadata.staged'))), \
        'Programming error: a repository write just occurred; why is ' + \
        'there no metadata.staged directory where it is expected?'

    # This shouldn't exist, but just in case something was interrupted,
    # warn and remove it.
    if os.path.exists(os.path.join(repo_dir, 'metadata.livetemp')):
      print(YELLOW + 'Warning: metadata.livetemp existed already. '
          'Some previous process was interrupted, or there is a programming '
          'error.' + ENDCOLORS)
      shutil.rmtree(os.path.join(repo_dir, 'metadata.livetemp'))

    # Copy the staged metadata to a temp directory we'll move into place
    # atomically in a moment.
    shutil.copytree(
        os.path.join(repo_dir, 'metadata.staged'),
        os.path.join(repo_dir, 'metadata.livetemp'))

    # Empty the existing (old) live metadata directory (relatively fast).
    if os.path.exists(os.path.join(repo_dir, 'metadata')):
      shutil.rmtree(os.path.join(repo_dir, 'metadata'))

    # Atomically move the new metadata into place.
    os.rename(
        os.path.join(repo_dir, 'metadata.livetemp'),
        os.path.join(repo_dir, 'metadata'))




def revoke_and_add_new_key_and_write_to_live():
  """
  <Purpose>
    Revoke the current Targets verification key (all roles currently have one
    verification key), and add a new key for it.  This is a high-level version
    of the common function to update a role key. The director service instance
    is also updated with the key changes.

  <Arguments>
    None.

  <Exceptions>
    None.

  <Side Effecs>
    None.

  <Returns>
    None.
  """

  global director_service_instance

  # Generate a new key for the Targets role.  Make sure that the director
  # service instance is updated to use the new key.  'director' argument to
  # generate_key() actually references the targets role.
  demo.generate_key('director')
  new_targets_public_key = demo.import_public_key('director')
  new_targets_private_key = demo.import_private_key('director')
  old_targets_public_key = director_service_instance.key_dirtarg_pub
  old_targets_private_key = director_service_instance.key_dirtarg_pri

  # Set the new public and private Targets keys in the director service.
  # These keys are shared between all vehicle repositories.
  director_service_instance.key_dirtarg_pub = new_targets_public_key
  director_service_instance.key_dirtarg_pri = new_targets_private_key

  for vin, repository in director_service_instance.vehicle_repositories.iteritems():
    repository.targets.remove_verification_key(old_targets_public_key)
    repository.targets.add_verification_key(new_targets_public_key)

    root_private_key = director_service_instance.key_dirroot_pri
    snapshot_private_key = director_service_instance.key_dirsnap_pri
    timestamp_private_key = director_service_instance.key_dirtime_pri

    # We need to re-sign root because it revoked the Targets key.  Snapshot
    # must be written to make a new release.
    repository.root.load_signing_key(root_private_key)
    repository.targets.load_signing_key(new_targets_private_key)
    repository.snapshot.load_signing_key(snapshot_private_key)
    repository.timestamp.load_signing_key(timestamp_private_key)

    # Write all the metadata changes to disk.  Note: write() will be writeall()
    # in the latest version of the TUF codebase.
    repository.write()







def add_target_to_director(target_fname, filepath_in_repo, vin, ecu_serial):
  """
  For use in attacks and more specific demonstration.

  Given the filename of the file to add, the path relative to the repository
  root to which to copy it, the VIN of the vehicle whose repository it should
  be added to, and the ECU's serial directory, adds that file
  as a target file (calculating its cryptographic hash and length) to the
  appropriate repository for the given VIN.

  <Arguments>
    target_fname
      The full filename of the file to be added as a target to the Director's
      targets role metadata. This file doesn't have to be in any particular
      place; it will be copied into the repository directory structure.

    filepath_in_repo
      The path relative to the root of the repository's targets directory
      where this file will be kept and accessed by clients. (e.g. 'file1.txt'
      or 'brakes/firmware.tar.gz')

    ecu_serial
      The ECU to assign this target to in the targets metadata.
      Complies with uptane.formats.ECU_SERIAL_SCHEMA

  """
  global director_service_instance

  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
  tuf.formats.RELPATH_SCHEMA.check_match(target_fname)
  tuf.formats.RELPATH_SCHEMA.check_match(filepath_in_repo)

  if vin not in director_service_instance.vehicle_repositories:
    raise uptane.UnknownVehicle('The VIN provided, ' + repr(vin) + ' is not '
        'that of a vehicle known to this Director.')

  repo = director_service_instance.vehicle_repositories[vin]
  repo_dir = repo._repository_directory

  print('Copying target file into place.')
  destination_filepath = os.path.join(repo_dir, 'targets', filepath_in_repo)

  # TODO: This should probably place the file into a common targets directory
  # that is then softlinked to all repositories.
  shutil.copy(target_fname, destination_filepath)

  print('Adding target ' + repr(target_fname) + ' for ECU ' + repr(ecu_serial))

  # This calls the appropriate vehicle repository.
  director_service_instance.add_target_for_ecu(
      vin, ecu_serial, destination_filepath)





def host():
  """
  Hosts the Director repository (http serving metadata files) as a separate
  process. Should be stopped with kill_server().

  Note that you must also run listen() to start the Director services (run on
  xmlrpc).

  If this module already started a server process to host the repo, nothing will
  be done.
  """


  global repo_server_process

  if repo_server_process is not None:
    print('Sorry, there is already a server process running.')
    return

  # Prepare to host the director repo contents.

  os.chdir(demo.DIRECTOR_REPO_DIR)

  command = []
  if sys.version_info.major < 3: # Python 2 compatibility
    command = ['python', '-m', 'SimpleHTTPServer', str(demo.DIRECTOR_REPO_PORT)]
  else:
    command = ['python3', '-m', 'http.server', str(demo.DIRECTOR_REPO_PORT)]


  # Begin hosting the director's repository.

  repo_server_process = subprocess.Popen(command, stderr=subprocess.PIPE)

  os.chdir(uptane.WORKING_DIR)

  print('Director repo server process started, with pid ' + str(repo_server_process.pid))
  print('Director repo serving on port: ' + str(demo.DIRECTOR_REPO_PORT))
  url = demo.DIRECTOR_REPO_HOST + ':' + str(demo.DIRECTOR_REPO_PORT) + '/'
  print('Director repo URL is: ' + url)

  # Wait / allow any exceptions to kill the server.
  # try:
  #   time.sleep(1000000) # Stop hosting after a while.
  # except:
  #   print('Exception caught')
  #   pass
  # finally:
  #   if repo_server_process.returncode is None:
  #     print('Terminating Director repo server process ' + str(repo_server_process.pid))
  #     repo_server_process.kill()


# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(xmlrpc_server.SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)


def listen():
  """
  Listens on DIRECTOR_SERVER_PORT for xml-rpc calls to functions:
    - submit_vehicle_manifest
    - register_ecu_serial

  Note that you must also run host() in order to serve the metadata files via
  http.
  """

  global director_service_thread

  if director_service_thread is not None:
    print('Sorry - there is already a Director service thread listening.')
    return

  # Create server
  server = xmlrpc_server.SimpleXMLRPCServer(
      (demo.DIRECTOR_SERVER_HOST, demo.DIRECTOR_SERVER_PORT),
      requestHandler=RequestHandler, allow_none=True)
  #server.register_introspection_functions()

  # Register function that can be called via XML-RPC, allowing a Primary to
  # submit a vehicle version manifest.
  server.register_function(
      director_service_instance.register_vehicle_manifest,
      'submit_vehicle_manifest')

  server.register_function(
      director_service_instance.register_ecu_serial, 'register_ecu_serial')


  # Interface available for the demo website frontend.
  server.register_function(
      director_service_instance.add_new_vehicle, 'add_new_vehicle')
  # Have decided that a function to add an ecu is unnecessary.
  # Just add targets for it. It'll be registered when that ecu registers itself.
  # Eventually, we'll want there to be an add ecu function here that takes
  # an ECU's public key, but that's not reasonable right now.

  # Provide absolute path for this, or path relative to the Director's repo
  # directory.
  server.register_function(add_target_to_director, 'add_target_to_director')
  server.register_function(write_to_live, 'write_director_repo')

  server.register_function(
      inventory.get_last_vehicle_manifest, 'get_last_vehicle_manifest')
  server.register_function(
      inventory.get_last_ecu_manifest, 'get_last_ecu_manifest')

  server.register_function(
      director_service_instance.register_ecu_serial, 'register_ecu_serial')

  server.register_function(clear_vehicle_targets, 'clear_vehicle_targets')

  server.register_function(attack_mitm, 'attack_mitm')
  server.register_function(recover_mitm, 'recover_mitm')

  print(' Starting Director Services Thread: will now listen on port ' +
      str(demo.DIRECTOR_SERVER_PORT))
  director_service_thread = threading.Thread(target=server.serve_forever)
  director_service_thread.setDaemon(True)
  director_service_thread.start()




def attack_mitm(vin, target_filepath):
  # Arbitrary package attack, no compromised keys.
  # Move evil target file into place on Director without updating metadata
  # (simulate bad mirror).
  full_fname = os.path.join(
      demo.DIRECTOR_REPO_DIR, vin, 'targets', target_filepath)
  # TODO: NOTE THAT THIS ATTACK SCRIPT BREAKS IF THE TARGET FILE IS IN A
  # SUBDIRECTORY IN THE REPOSITORY.
  backup_fname = os.path.join(
      demo.DIRECTOR_REPO_DIR, vin, 'targets', '_backup__' + target_filepath)

  full_mr_fname = os.path.join(
      demo.MAIN_REPO_TARGETS_DIR, target_filepath)
  backup_mr_fname = os.path.join(
      demo.MAIN_REPO_TARGETS_DIR, '_backup__' + target_filepath)


  if not os.path.exists(full_fname) and not os.path.exists(full_mr_fname):
    raise Exception('The provided target file is not already in either the '
        'Director or Image repositories. This attack is intended to be run on '
        'an existing target that is already set to be delivered to a client.')
  elif os.path.exists(backup_fname):
    raise Exception('The attack is already in progress, or was never recovered '
        'from. Not running twice. Please check state and if everything is '
        'otherwise okay, delete ' + repr(backup_fname))

  # If the image file exists already on the Director (not necessary), then
  # back it up.
  if os.path.exists(full_fname):
    shutil.copy(full_fname, backup_fname)

  # Hide file on Main Repo so that client doesn't just grab an intact file from
  # there, making the attack moot.
  if os.path.exists(full_mr_fname):
    os.rename(full_mr_fname, backup_mr_fname)

  fobj = open(full_fname, 'w')
  fobj.write('EVIL UPDATE: ARBITRARY PACKAGE ATTACK TO BE DELIVERED FROM '
      'MITM / bad mirror (no keys compromised).')
  fobj.close()
  shutil.copy(full_fname, full_mr_fname)



def recover_mitm(vin, target_filepath):
  # Arbitrary package attack recovery.
  # Move evil target file out and normal target file back in.
  full_fname = os.path.join(
      demo.DIRECTOR_REPO_DIR, vin, 'targets', target_filepath)
  # TODO: NOTE THAT THIS ATTACK SCRIPT BREAKS IF THE TARGET FILE IS IN A
  # SUBDIRECTORY IN THE REPOSITORY.
  backup_fname = os.path.join(
      demo.DIRECTOR_REPO_DIR, vin, 'targets', '_backup__' + target_filepath)

  full_mr_fname = os.path.join(
      demo.MAIN_REPO_TARGETS_DIR, target_filepath)
  backup_mr_fname = os.path.join(
      demo.MAIN_REPO_TARGETS_DIR, '_backup__' + target_filepath)

  if not os.path.exists(backup_fname) or not os.path.exists(full_fname):
    raise Exception('The expected backup or attacked files do not exist. No '
        'attack is in progress to recover from, or manual manipulation has '
        'broken the expected state.')

  # In the case of the Director repo, we expect there to be a file replaced,
  # so we restore the backup over it.
  os.rename(backup_fname, full_fname)

  # If the file existed on the Main Repo, was backed up and hidden by the
  # attack, and hasn't since been replaced (by some other attack or manual
  # manipulation), restore that file to its place. Either way, delete the
  # backup so that it's not there the next time to potentially confuse this.
  if os.path.exists(backup_mr_fname) and not os.path.exists(full_mr_fname):
    os.rename(full_mr_fname, backup_mr_fname)
  elif os.path.exists(backup_mr_fname):
    os.remove(backup_mr_fname)





def clear_vehicle_targets(vin):
  director_service_instance.vehicle_repositories[vin].targets.clear_targets()





def kill_server():

  global repo_server_process

  if repo_server_process is None:
    print('No server to stop.')
    return

  else:
    print('Killing server process with pid: ' + str(repo_server_process.pid))
    repo_server_process.kill()
    repo_server_process = None
