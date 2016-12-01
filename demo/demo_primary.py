"""
demo_primary.py

Demonstration code handling a Primary client.


Use:

import demo.demo_primary as dp
dp.clean_slate() # also listens, xmlrpc
  At this point, separately, you will need to initialize at least one secondary.
  See demo_secondary use instructions.
dp.generate_signed_vehicle_manifest()
dp.submit_vehicle_manifest_to_director()




"""

import demo
import uptane
import uptane.common # for canonical key construction and signing
import uptane.clients.primary as primary
from uptane import GREEN, RED, YELLOW, ENDCOLORS
import tuf.keys
import tuf.repository_tool as rt
import tuf.client.updater

import os # For paths and makedirs
import shutil # For copyfile
import threading # for the demo listener
import time
import xmlrpc.client
import xmlrpc.server
import six

# Import a CAN communications module for partial-verification Secondaries
import ctypes
libuptane_lib = None # will be loaded later if we are communicating via CAN
# You can ignore this unless you're communicating via CAN
LIBUPTANE_LIBRARY_FNAME = os.path.join(
    uptane.WORKING_DIR, '..', 'libuptane', 'libuptane.so')



# Globals
_client_directory_name = 'temp_primary' # name for this Primary's directory
_vin = '111'
_ecu_serial = '11111'
# firmware_filename = 'infotainment_firmware.txt'


# If True, we will employ the C interface for CAN communications.
use_can_interface = False
# This will be used for the Partial Verification Secondaries that are
# communicating via the CAN bus and running in C.
# Any PV Secondary running in C and communicating across CAN must be listed
# here, or it will be assumed to be a FV Secondary running in Python across IP.
partial_verification_secondaries = {
  # A map of ECU Serial to Secondary ID for Sam's CAN code.
  # This must map correctly to the config file settings on the Primary in Sam's
  # CAN code that specify how to contact the c-Secondaries.
  '30000': 1, # Sam's first PV C Secondary
  '30001': 2  # Sam's second PV C Secondary
}
DATATYPE_IMAGE = 0
DATATYPE_METADATA = 1

# Dynamic globals
current_firmware_fileinfo = {}
primary_ecu = None
ecu_key = None
director_proxy = None
listener_thread = None
most_recent_signed_vehicle_manifest = None


def clean_slate(
    use_new_keys=False,
    client_directory_name=_client_directory_name,
    vin=_vin,
    ecu_serial=_ecu_serial,
    c_interface=False):
  """
  """

  global primary_ecu
  global _client_directory_name
  global _vin
  global _ecu_serial
  global listener_thread
  global use_can_interface

  _client_directory_name = client_directory_name
  _vin = vin
  _ecu_serial = ecu_serial
  use_can_interface = c_interface


  # Load the public timeserver key.
  key_timeserver_pub = demo.import_public_key('timeserver')

  # Generate a trusted initial time for the Primary.
  clock = tuf.formats.unix_timestamp_to_datetime(int(time.time()))
  clock = clock.isoformat() + 'Z'
  tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(clock)

  # Load the private key for this Primary ECU.
  load_or_generate_key(use_new_keys)





  # TODO: <~> Remove old hack assumption about number and name of
  # repositories. Use pinned.json, if anything even still has to be done here.
  CLIENT_DIR = _client_directory_name
  CLIENT_METADATA_DIR_MAINREPO_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'current')
  CLIENT_METADATA_DIR_MAINREPO_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'previous')
  CLIENT_METADATA_DIR_DIRECTOR_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'director', 'current')
  CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'director', 'previous')

  # Note that the hosts and ports for the repositories are drawn from
  # pinned.json now. The services (timeserver and the director's
  # submit-manifest service) are still addressed here, though, currently
  # by pulling the constants from their modules directly
  # e.g. timeserver.TIMESERVER_PORT and director.DIRECTOR_SERVER_PORT).
  # Note that despite the vague name, the latter is not the director
  # repository, but a service that receives manifests.

  # Set up the TUF client directories for each repository.
  if os.path.exists(CLIENT_DIR):
    shutil.rmtree(CLIENT_DIR)

  # TODO: <~> Remove assumption about number of repositories. Use pinned.json?
  for d in [
      CLIENT_METADATA_DIR_MAINREPO_CURRENT,
      CLIENT_METADATA_DIR_MAINREPO_PREVIOUS,
      CLIENT_METADATA_DIR_DIRECTOR_CURRENT,
      CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS]:
    os.makedirs(d)

  # Get the root.json file from the mainrepo (would come with this client).
  shutil.copyfile(
      demo.MAIN_REPO_ROOT_FNAME,
      os.path.join(CLIENT_METADATA_DIR_MAINREPO_CURRENT, 'root.json'))

  # Get the root.json file from the director repo (would come with this client).
  shutil.copyfile(
      demo.DIRECTOR_REPO_ROOT_FNAME,
      os.path.join(CLIENT_METADATA_DIR_DIRECTOR_CURRENT, 'root.json'))

  # Add a pinned.json to this client (softlink it from the indicated copy).
  os.symlink(
      demo.DEMO_PINNING_FNAME, #os.path.join(WORKING_DIR, 'pinned.json'),
      os.path.join(CLIENT_DIR, 'metadata', 'pinned.json'))

  # Configure tuf with the client's metadata directories (where it stores the
  # metadata it has collected from each repository, in subdirectories).
  tuf.conf.repository_directory = CLIENT_DIR # TODO for TUF: This setting should probably be called client_directory instead, post-TAP4.









  # Initialize a Primary ECU, making a client directory and copying the root
  # file from the repositories.
  primary_ecu = primary.Primary(
      full_client_dir=os.path.join(uptane.WORKING_DIR, _client_directory_name),
      # pinning_filename=demo.DEMO_PINNING_FNAME,
      director_repo_name=demo.DIRECTOR_REPO_NAME,
      vin=_vin,
      ecu_serial=_ecu_serial,
      # fname_root_from_mainrepo=demo.MAIN_REPO_ROOT_FNAME,
      # fname_root_from_directorrepo=demo.DIRECTOR_REPO_ROOT_FNAME,
      primary_key=ecu_key,
      time=clock,
      timeserver_public_key=key_timeserver_pub)


  if listener_thread is None:
    listener_thread = threading.Thread(target=listen)
    listener_thread.setDaemon(True)
    listener_thread.start()
  print('\n' + GREEN + 'Primary is now listening for messages from ' +
      'Secondaries.' + ENDCOLORS)


  try:
    register_self_with_director()
  except xmlrpc.client.Fault:
    print('Registration with Director failed. Now assuming this Primary is '
        'already registered.')


  if use_can_interface:
    # If we're on a device with a CAN interface that we're going to be using
    # to communicate with Secondaries, then load Sam's libuptane C module.
    # (We use this on the Raspberry Pis with a PiCAN card.)

    global libuptane_lib

    libuptane_lib = ctypes.cdll.LoadLibrary('LIBUPTANE_ROOT_DIR/libuptane.so')

    # Start up the CAN communications client for the Primary.
    libuptane_lib.uptane_init_wrapper()

    status = libuptane_lib.check_status_wrapper()
    print('After initialization, status of c-uptane PV Secondary client is: ' +
        repr(status))


  print(GREEN + '\n Now simulating a Primary that rolled off the assembly line'
      '\n and has never seen an update.' + ENDCOLORS)

  print("Generating this Primary's first Vehicle Version Manifest and sending "
      "it to the Director.")

  generate_signed_vehicle_manifest()
  submit_vehicle_manifest_to_director()





def close_can_primary():
  """Only necessary if use_can_interface is True."""
  assert use_can_interface, 'This is only of use if use_can_interface is True.'
  assert libuptane_lib is not None, 'Have not yet loaded libuptane_lib. ' + \
      'Run clean_slate().'

  import libuptane_lib

  libuptane_lib.uptane_finish_wrapper()
  print('C CAN module for Primary has shut down.')





def load_or_generate_key(use_new_keys=False):
  """Load or generate an ECU's private key."""

  global ecu_key

  if use_new_keys:
    demo.generate_key('primary')

  # Load in from the generated files.
  key_pub = demo.import_public_key('primary')
  key_pri = demo.import_private_key('primary')

  ecu_key = uptane.common.canonical_key_from_pub_and_pri(key_pub, key_pri)





def update_cycle():
  """
  """

  global primary_ecu


  #
  # FIRST: TIME
  #

  # First, we'll send the Timeserver a request for a signed time, with the
  # nonces Secondaries have sent us since last time. (This also saves these
  # nonces as "sent" and empties the Primary's list of nonces to send.)
  nonces_to_send = primary_ecu.get_nonces_to_send_and_rotate()

  tserver = xmlrpc.client.ServerProxy(
      'http://' + str(demo.TIMESERVER_HOST) + ':' + str(demo.TIMESERVER_PORT))
  #if not server.system.listMethods():
  #  raise Exception('Unable to connect to server.')

  print('Submitting a request for a signed time to the Timeserver.')

  time_attestation = tserver.get_signed_time(nonces_to_send)

  # This validates the attestation and also saves the time therein (if the
  # attestation was valid). Secondaries can request this from the Primary at
  # will.
  primary_ecu.validate_time_attestation(time_attestation)

  print('Time attestation validated. New time registered.')



  #
  # SECOND: VEHICLE VERSION MANIFEST
  #

  # Generate and send.
  vehicle_manifest = generate_signed_vehicle_manifest()
  submit_vehicle_manifest_to_director(vehicle_manifest)




  #
  # THIRD: DOWNLOAD METADATA AND IMAGES
  #

  # Starting with just the root.json files for the director and mainrepo, and
  # pinned.json, the client will now use TUF to connect to each repository and
  # download/update top-level metadata. This call updates metadata from both
  # repositories.
  # upd.refresh()
  print(GREEN + '\n')
  print(' Now updating top-level metadata from the Director and OEM Repositories'
      '\n    (timestamp, snapshot, root, targets)')
  print('\n' + ENDCOLORS)



  # This will update the Primary's metadata and download images from the
  # Director and OEM Repositories, and create a mapping of assignments from
  # each Secondary ECU to its Director-intended target.
  primary_ecu.primary_update_cycle()

  # All targets have now been downloaded.


  # Generate and submit vehicle manifest.
  generate_signed_vehicle_manifest()
  submit_vehicle_manifest_to_director()






def generate_signed_vehicle_manifest():

  global primary_ecu
  global most_recent_signed_vehicle_manifest

  # Generate and sign a manifest indicating that this ECU has a particular
  # version/hash/size of file2.txt as its firmware.
  most_recent_signed_vehicle_manifest = \
      primary_ecu.generate_signed_vehicle_manifest()





def submit_vehicle_manifest_to_director(signed_vehicle_manifest=None):

  global most_recent_signed_vehicle_manifest

  if signed_vehicle_manifest is None:
    signed_vehicle_manifest = most_recent_signed_vehicle_manifest


  uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
      signed_vehicle_manifest)
  # TODO: <~> Be sure to update the previous line to indicate an ASN.1
  # version of the ecu_manifest after encoders have been implemented.


  server = xmlrpc.client.ServerProxy(
      'http://' + str(demo.DIRECTOR_SERVER_HOST) + ':' +
      str(demo.DIRECTOR_SERVER_PORT))
  #if not server.system.listMethods():
  #  raise Exception('Unable to connect to server.')

  print("Submitting the Primary's manifest to the Director.")

  server.submit_vehicle_manifest(
      primary_ecu.vin,
      primary_ecu.ecu_serial,
      signed_vehicle_manifest)


  print(GREEN + 'Submission of Vehicle Manifest complete.' + ENDCOLORS)





def register_self_with_director():
  """
  Send the Director a message to register our ECU serial number and Public Key.
  """
  # Connect to the Director
  server = xmlrpc.client.ServerProxy(
    'http://' + str(demo.DIRECTOR_SERVER_HOST) + ':' +
    str(demo.DIRECTOR_SERVER_PORT))

  print('Registering Primary ECU Serial and Key with Director.')
  server.register_ecu_serial(primary_ecu.ecu_serial, primary_ecu.primary_key)
  print(GREEN + 'Primary has been registered with the Director.' + ENDCOLORS)



# This wouldn't be how we'd do it in practice. ECUs would probably be registered
# when put into a vehicle, directly rather than through the Primary.
# def register_secondaries_with_director():
#   """
#   For each of the Secondaries that this Primary is in charge of, send the
#   Director a message registering that Secondary's ECU Serial and public key.
#   """




# def ATTACK_send_corrupt_manifest_to_director():
#   """
#   Attack: MITM w/o key modifies ECU manifest.
#   Modify the ECU manifest without updating the signature.
#   """
#   # Copy the most recent signed ecu manifest.
#   corrupt_signed_manifest = {k:v for (k,v) in most_recent_signed_ecu_manifest.items()}

#   corrupt_signed_manifest['signed']['attacks_detected'] += 'Everything is great, I PROMISE!'
#   #corrupt_signed_manifest['signed']['ecu_serial'] = 'ecu22222'

#   print(YELLOW + 'ATTACK: Corrupted Manifest (bad signature):' + ENDCOLORS)
#   print('   Modified the signed manifest as a MITM, simply changing a value:')
#   print('   The attacks_detected field now reads ' + RED + '"Everything is great, I PROMISE!' + ENDCOLORS)

#   #import xmlrpc.client # for xmlrpc.client.Fault

#   try:
#     primary_ecu.submit_ecu_manifest_to_director(corrupt_signed_manifest)
#   except xmlrpc.client.Fault:
#     print(GREEN + 'Director service REJECTED the fraudulent ECU manifest.' + ENDCOLORS)
#   else:
#     print(RED + 'Director service ACCEPTED the fraudulent ECU manifest!' + ENDCOLORS)
#   # (The Director, in its window, should now indicate that it has received this
#   # manifest. If signature checking for manifests is on, then the manifest is
#   # rejected. Otherwise, it is simply accepted.)




# def ATTACK_send_manifest_with_wrong_sig_to_director():
#   """
#   Attack: MITM w/o key modifies ECU manifest and signs with a different ECU's
#   key.
#   """
#   # Discard the signatures and copy the signed contents of the most recent
#   # signed ecu manifest.
#   corrupt_manifest = {k:v for (k,v) in most_recent_signed_ecu_manifest['signed'].items()}

#   corrupt_manifest['attacks_detected'] += 'Everything is great; PLEASE BELIEVE ME THIS TIME!'

#   signable_corrupt_manifest = tuf.formats.make_signable(corrupt_manifest)
#   uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
#       signable_corrupt_manifest)

#   # Attacker loads a key she may have (perhaps some other ECU's key)
#   key2_pub = demo.import_public_key('secondary2')
#   key2_pri = demo.import_private_key('secondary2')
#   ecu2_key = uptane.common.canonical_key_from_pub_and_pri(key2_pub, key2_pri)
#   keys = [ecu2_key]

#   # Attacker signs the modified manifest with that other key.
#   signed_corrupt_manifest = uptane.common.sign_signable(
#       signable_corrupt_manifest, keys)
#   uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
#       signed_corrupt_manifest)

#   #import xmlrpc.client # for xmlrpc.client.Fault

#   try:
#     primary_ecu.submit_ecu_manifest_to_director(signed_corrupt_manifest)
#   except xmlrpc.client.Fault as e:
#     print('Director service REJECTED the fraudulent ECU manifest.')
#   else:
#     print('Director service ACCEPTED the fraudulent ECU manifest!')
#   # (The Director, in its window, should now indicate that it has received this
#   # manifest. If signature checking for manifests is on, then the manifest is
#   # rejected. Otherwise, it is simply accepted.)





def enforce_jail(fname, expected_containing_dir):
  """
  DO NOT ASSUME THAT THIS TEMPORARY FUNCTION IS SECURE.
  """
  # Make sure it's in the expected directory.
  #print('provided arguments: ' + repr(fname) + ' and ' + repr(expected_containing_dir))
  abs_fname = os.path.abspath(os.path.join(expected_containing_dir, fname))
  if not abs_fname.startswith(os.path.abspath(expected_containing_dir)):
    raise ValueError('Expected a filename in directory ' +
        repr(expected_containing_dir) + '. When appending ' + repr(fname) +
        ' to the given directory, the result was not in the given directory.')

  else:
    return abs_fname




def get_image_for_ecu(ecu_serial):
  """
  Behaves differently for partial-verification Secondaries communicating across
  CAN and full-verification Secondaries communicating via xmlrpc.

  For PV Secondaries on CAN:
    Employs C-based libuptane library to send the image binary data to the
    CAN ID noted in configuration as matching the given ECU Serial.

  For FV Secondaries via XMLRPC:
    Returns:
     - filename of the image, relative to the targets directory
     - binary image data in xmlrpc.Binary format
  """

  # Ensure serial is correct format & registered
  primary_ecu.check_ecu_serial(ecu_serial)

  image_fname = primary_ecu.get_image_fname_for_ecu(ecu_serial)

  if image_fname is None:
    print('ECU Serial ' + repr(ecu_serial) + ' requested an image, but this '
        'Primary has no update for that ECU.')
    return None

  # If the given ECU is a Partial Verification Secondary operating across a
  # CAN bus, we send the image via an external C CAN library, libuptane.
  if use_can_interface and ecu_serial in SECONDARY_ID_ENUM:

    assert libuptane_lib is not None, 'Have not yet loaded libuptane_lib. ' + \
        'Run clean_slate().'

    can_id = SECONDARY_ID_ENUM[ecu_serial]

    print('Treating requester as partial-verification Secondary. ECU Serial '
        '(' + repr(ecu_serial) + ') appears in mapping of ECUs to CAN IDs. '
        'Corresponding CAN ID is ' + repr(can_id) + '.')

    status = None
    for i in range(3): # Try checking CAN status a few times.
      status = libuptane_lib.check_status_wrapper()
      if status == 1:
        break

    if status != 1:
      raise uptane.Error('Unable to connect via CAN interface after several '
          'tries. Status is ' + repr(status))

    print('Status is ' + repr(status) + '. Sending file.')

    libuptane_lib.send_isotp_file_wrapper(
        can_id, # enum
        DATATYPE_IMAGE,
        image_fname)

    return


  else:
    print('Treating requester as full-verification Secondary without a CAN '
        'interface because the C CAN interface is off or the ECU Serial (' +
        repr(ecu_serial) + ') does not appear in the mapping of ECU Serials '
        'to CAN IDs.')

    assert os.path.exists(image_fname), 'File ' + repr(image_fname) + \
        ' does not exist....'
    binary_data = xmlrpc.client.Binary(open(image_fname, 'rb').read())

    print('Distributing image to ECU ' + repr(ecu_serial))

    # Get relative filename (relative to the client targets directory) so that
    # it can be used as a TUF-style filepath within the targets namespace by
    # the Secondary.
    relative_fname = os.path.relpath(
        image_fname, os.path.join(primary_ecu.full_client_dir, 'targets'))
    return (relative_fname, binary_data)





def get_metadata_for_ecu(ecu_serial, force_partial_verification=False):
  """
  Send a zip archive of the most recent consistent set of the Primary's client
  metadata directory, containing the current, consistent metadata from all
  repositories used.

  If force_partial_verification is True, then even if the request is coming
  from a client that is not on a CAN interface and configured to communicate
  with this Primary via CAN, we will still send partial verification data (just
  the Director's targets.json file).

  <Exceptions>
    uptane.Error
      - if we are set to communicate via CAN interface, but CAN interface is
        not ready

    ... fill in more
  """
  # Ensure serial is correct format & registered
  primary_ecu.check_ecu_serial(ecu_serial)

  # The filename of the file to return.
  fname = None

  # TODO: <~> NO: We can't do it this way. The updater's metadata stored in
  # this fashion is post-validation and without signatures.
  # I may have to just transfer files. Is there not somewhere where I can grab
  # the signed metadata from TUF?
  # See updater.py _update_metadata 2189-2192?
  # The more I look at this, the more it looks like I just need to copy all
  # the files....
  # I'll use zipfile. In Python 2.7.4 and later, it should prevent files from
  # being created outside of the target extraction directory.



  # If we're responding with the file via this XMLRPC call, not across a CAN:
  if not use_can_interface or ecu_serial not in SECONDARY_ID_ENUM:

    if force_partial_verification:
      print('Treating request as a partial-verification Secondary because '
          'force_partial_verification is True, even though the client is not '
          'on a CAN interface.')
      fname = primary_ecu.get_partial_metadata_fname()
    else:
      # If this is a Full Verification Secondary not running on a CAN network,
      # select the full metadata archive.
      print('Treating requester as full-verification Secondary without a CAN '
          'interface because the C CAN interface is off or the ECU Serial (' +
          repr(ecu_serial) + ') does not appear in the mapping of ECU Serials '
          'to CAN IDs.')
      fname = primary_ecu.get_full_metadata_archive_fname()

    if not os.path.exists(fname):
      raise uptane.Error('This Primary does not have a collection of metadata '
          'to distribute to Secondaries.')

    print('Distributing metadata to ECU ' + repr(ecu_serial))

    binary_data = xmlrpc.client.Binary(open(fname, 'rb').read())

    print('Distributing image to ECU ' + repr(ecu_serial))
    return binary_data




  # Otherwise, we're dealing with a Partial Verification Secondary that is
  # running on a CAN network, so it's time to get messy.
  assert use_can_interface and ecu_serial in SECONDARY_ID_ENUM, 'Programming error.'
  assert libuptane_lib is not None, 'Have not yet loaded libuptane_lib. ' + \
      'Run clean_slate().'

  can_id = SECONDARY_ID_ENUM[ecu_serial]

  print('Treating requester as partial-verification Secondary. ECU Serial '
      '(' + repr(ecu_serial) + ') appears in mapping of ECUs to CAN IDs. '
      'Corresponding CAN ID is ' + repr(can_id) + '.')

  fname = primary_ecu.get_partial_metadata_fname()

  print('Trying to send ' + repr(fname) + ' to Secondary with CAN ID ' +
      repr(can_id) + ' and ECU Serial ' + repr(ecu_serial) + ' via CAN '
      'interface.')

  status = None
  for i in range(3): # Try checking CAN status a few times.
    status = libuptane_lib.check_status_wrapper()
    if status == 1:
      break

  if status != 1:
    raise uptane.Error('Unable to connect via CAN interface after several '
        'tries: check_status has not returned 1. Status is ' + repr(status))

  print('Status is ' + repr(status) + '. Sending file.')
  libuptane_lib.send_isotp_file_wrapper(
      can_id, # enum
      DATATYPE_IMAGE,
      fname)
  status = libuptane_lib.check_status_wrapper()
  print('After sending file ' + repr(fname) + ', status of c-uptane PV '
      'Secondary client (' + repr(ecu_serial) + ') is: ' + repr(status))

  return





def get_time_attestation_for_ecu(ecu_serial):
  """
  """
  # Ensure serial is correct format & registered
  primary_ecu.check_ecu_serial(ecu_serial)

  attestation = primary_ecu.get_last_timeserver_attestation()

  if use_can_interface and ecu_serial in SECONDARY_ID_ENUM:

    assert libuptane_lib is not None, 'Have not yet loaded libuptane_lib. ' + \
        'Run clean_slate() to load library and initialize CAN interface.'

    can_id = SECONDARY_ID_ENUM[ecu_serial]

    print('Treating requester as partial-verification Secondary. ECU Serial '
        '(' + repr(ecu_serial) + ') appears in mapping of ECUs to CAN IDs. '
        'Corresponding CAN ID is ' + repr(can_id) + '.')

    #
    #
    # TODO: <~> Right now, the partial verification demo client in C that uses
    # the CAN interface, libuptane, doesn't support sending timeserver
    # attestations over CAN, so we'll skip this until it does.
    #
    #

    print('Skipping send of timeserver attestation via CAN interface because '
        'the CAN code does not support it.')


  else:
    print('Treating requester as full-verification Secondary without a CAN '
        'interface because the C CAN interface is off or the ECU Serial (' +
        repr(ecu_serial) + ') does not appear in the mapping of ECU Serials '
        'to CAN IDs. Sending time attestation back.')

    print('Distributing metadata to ECU ' + repr(ecu_serial))
    return attestation





# Restrict Primary requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(xmlrpc.server.SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)





def listen():
  """
  Listens on PRIMARY_SERVER_PORT for xml-rpc calls to functions
  """

  # Create server
  server = xmlrpc.server.SimpleXMLRPCServer(
      (demo.PRIMARY_SERVER_HOST, demo.PRIMARY_SERVER_PORT),
      requestHandler=RequestHandler, allow_none=True)
  #server.register_introspection_functions()

  # Register functions that can be called via XML-RPC, allowing Secondaries to
  # submit ECU Version Manifests, requests timeserver attestations, etc.

  server.register_function(
      primary_ecu.register_ecu_manifest, 'submit_ecu_manifest')

  server.register_function(
      primary_ecu.register_new_secondary, 'register_new_secondary')

  server.register_function(
      primary_ecu.get_last_timeserver_attestation,
      'get_last_timeserver_attestation')

  server.register_function(get_image_for_ecu, 'get_image')

  server.register_function(get_metadata_for_ecu, 'get_metadata')


  print('Primary will now listen on port ' + str(demo.PRIMARY_SERVER_PORT))
  server.serve_forever()

