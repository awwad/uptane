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
dd.write_to_live()
dd.host()
dd.listen()

    # Cleanup: (Note that this kills the metadata http hosting process, but does
    #           not stop the XMLRPC-serving thread.)
    demo_director.kill_server()

  Various attacks / manipulations can be performed before the server is killed.
  Some of these are discussed in uptane_test_instructions.py.

"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open

import demo
import uptane
import uptane.services.director as director
import tuf.formats

import threading # for the director services interface
import os # For paths and symlink
import shutil # For copying directory trees
import sys, subprocess, time # For hosting
import tuf.repository_tool as rt
import demo.demo_oem_repo as demo_oem_repo # for the main repo directory /:
from uptane import GREEN, RED, YELLOW, ENDCOLORS

from six.moves import xmlrpc_server # for the director services interface


# Dynamic global objects
repo = None
repo_server_process = None
director_service_instance = None
director_service_thread = None


def clean_slate(
  use_new_keys=False,
  additional_root_key=False,
  additional_targets_key=False):

  global repo
  global director_service_instance


  # ----------------
  # REPOSITORY SETUP:
  # ----------------

  # Create repo at './repodirector'

  repo = rt.create_new_repository(demo.DIRECTOR_REPO_NAME)


  # Create keys and/or load keys into memory.

  if use_new_keys:
    demo.generate_key('directorroot')
    demo.generate_key('directortimestamp')
    demo.generate_key('directorsnapshot')
    demo.generate_key('director') # targets
    if additional_root_key:
      demo.generate_key('directorroot2')
    if additional_targets_key:
      demo.generate_key('director2')

  key_dirroot_pub = demo.import_public_key('directorroot')
  key_dirroot_pri = demo.import_private_key('directorroot')
  key_dirtime_pub = demo.import_public_key('directortimestamp')
  key_dirtime_pri = demo.import_private_key('directortimestamp')
  key_dirsnap_pub = demo.import_public_key('directorsnapshot')
  key_dirsnap_pri = demo.import_private_key('directorsnapshot')
  key_dirtarg_pub = demo.import_public_key('director')
  key_dirtarg_pri = demo.import_private_key('director')
  key_dirroot2_pub = None
  key_dirroot2_pri = None
  if additional_root_key:
    key_dirroot2_pub = demo.import_public_key('directorroot2')
    key_dirroot2_pri = demo.import_private_key('directorroot2')
  if additional_targets_key:
    key_dirtarg2_pub = demo.import_public_key('director2')
    key_dirtarg2_pri = demo.import_private_key('director2')


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
  if os.path.exists(os.path.join(demo.DIRECTOR_REPO_TARGETS_DIR, 'infotainment_firmware.txt')):
    os.remove(os.path.join(demo.DIRECTOR_REPO_TARGETS_DIR, 'infotainment_firmware.txt'))

  os.symlink(os.path.join(demo.MAIN_REPO_TARGETS_DIR, 'infotainment_firmware.txt'),
      os.path.join(demo.DIRECTOR_REPO_TARGETS_DIR, 'infotainment_firmware.txt'))

  fobj = open(os.path.join(demo.DIRECTOR_REPO_TARGETS_DIR, 'additional_file.txt'), 'w')
  fobj.write('Contents of additional_file.txt')
  fobj.close()



  # --------------
  # SERVICES SETUP:
  # --------------

  # Create the demo Director instance.
  director_service_instance = director.Director(
      key_root=key_dirroot_pri,
      key_timestamp=key_dirtime_pri,
      key_snapshot=key_dirsnap_pri,
      key_targets=key_dirtarg_pri,
      ecu_public_keys=dict())

  # Start with a hard-coded key for a single ECU for now.
  test_ecu_public_key = demo.import_public_key('secondary')
  test_ecu_serial = 'ecu11111'
  director_service_instance.register_ecu_serial(
      test_ecu_serial, test_ecu_public_key)



  # Add a first target file, for use by Secondary ECU 22222
  add_target_to_director(
      os.path.join(demo.DIRECTOR_REPO_TARGETS_DIR, 'infotainment_firmware.txt'),
      '22222')



  write_to_live()

  host()

  listen()





def write_to_live():

  global repo

  # Write to director repo's metadata.staged.
  repo.write()


  # Move staged metadata (from the write) to live metadata directory.

  if os.path.exists(os.path.join(demo.DIRECTOR_REPO_DIR, 'metadata')):
    shutil.rmtree(os.path.join(demo.DIRECTOR_REPO_DIR, 'metadata'))

  shutil.copytree(
      os.path.join(demo.DIRECTOR_REPO_DIR, 'metadata.staged'),
      os.path.join(demo.DIRECTOR_REPO_DIR, 'metadata'))

  # TODO: <~> Call the encoders here to convert the metadata files into BER
  # versions and also host those!





def add_target_to_director(target_fname, ecu_serial):
  """
  For use in attacks and more specific demonstration.

  Given a filename pointing to a file in the targets directory, adds that file
  as a target file (calculating its cryptographic hash and length)

  <Arguments>
    target_fname
      The full filename of the file to be added as a target to the Director's
      targets role metadata. This file should be in the targets subdirectory of
      the repository directory.

    ecu_serial
      The ECU to assign this target to in the targets metadata.
      Complies with uptane.formats.ECU_SERIAL_SCHEMA

  """
  global repo

  tuf.formats.RELPATH_SCHEMA.check_match(target_fname)
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)

  print('Adding target ' + repr(target_fname) + ' for ECU ' + repr(ecu_serial))

  if ecu_serial not in director_service_instance.ecu_public_keys:
    print(YELLOW + 'Warning: ECU ' + repr(ecu_serial) + ' is not a known ecu. '
        'Adding target assignment in case the ECU is registered in the future, '
        'but make sure the serial was correct.' + ENDCOLORS)

  repo.targets.add_target(target_fname, custom={'ecu_serial': ecu_serial})





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
    command = ['python', '-m', 'http.server', str(demo.DIRECTOR_REPO_PORT)]


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
    - submit_ecu_manifest
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

  # In the longer term, this won't be exposed: it will only be reached via
  # register_vehicle_manifest. For now, during development, however, this is
  # exposed.
  server.register_function(
      director_service_instance.register_ecu_manifest, 'submit_ecu_manifest')

  server.register_function(
      director_service_instance.register_ecu_serial, 'register_ecu_serial')


  print(' Starting Director Services Thread: will now listen on port ' +
      str(demo.DIRECTOR_SERVER_PORT))
  director_service_thread = threading.Thread(target=server.serve_forever)
  director_service_thread.setDaemon(True)
  director_service_thread.start()





def kill_server():

  global repo_server_process

  if repo_server_process is None:
    print('No server to stop.')
    return

  else:
    print('Killing server process with pid: ' + str(repo_server_process.pid))
    repo_server_process.kill()
