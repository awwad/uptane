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

Please see README.md for further instructions.

"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open

import demo
import uptane # Import before TUF modules; may change tuf.conf values.
import uptane.common # for canonical key construction and signing
import uptane.clients.primary as primary
import uptane.encoding.asn1_codec as asn1_codec
from uptane import GREEN, RED, YELLOW, ENDCOLORS
from demo.uptane_banners import *
import tuf.keys
import tuf.repository_tool as rt
import tuf.client.updater
import json
import canonicaljson

import os # For paths and makedirs
import shutil # For copyfile
import threading # for the demo listener
import time

from six.moves import xmlrpc_client
from six.moves import xmlrpc_server
from six.moves import range
import socket # to catch listening failures from six's xmlrpc server

# Import a CAN communications module for partial-verification Secondaries
import ctypes
libuptane_lib = None # will be loaded later if we are communicating via CAN
# You can ignore this unless you're communicating via CAN
LIBUPTANE_LIBRARY_FNAME = os.path.join(
    uptane.WORKING_DIR, '..', 'libuptane', 'libuptane.so')



# Globals
CLIENT_DIRECTORY_PREFIX = 'temp_primary'
client_directory = None
#_client_directory_name = 'temp_primary' # name for this Primary's directory
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
    # client_directory_name=None,
    vin=_vin,
    ecu_serial=_ecu_serial,
    c_interface=False):
  """
  """

  global primary_ecu
  global client_directory
  global _vin
  global _ecu_serial
  global listener_thread
  global use_can_interface

  _vin = vin
  _ecu_serial = ecu_serial
  use_can_interface = c_interface

  # if client_directory_name is not None:
  #   client_directory = client_directory_name
  # else:
  client_directory = os.path.join(
      uptane.WORKING_DIR, CLIENT_DIRECTORY_PREFIX + demo.get_random_string(5))

  # Load the public timeserver key.
  key_timeserver_pub = demo.import_public_key('timeserver')

  # Generate a trusted initial time for the Primary.
  clock = tuf.formats.unix_timestamp_to_datetime(int(time.time()))
  clock = clock.isoformat() + 'Z'
  tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(clock)

  # Load the private key for this Primary ECU.
  load_or_generate_key(use_new_keys)


  # Craft the directory structure for the client directory, including the
  # creation of repository metadata directories, current and previous, putting
  # the pinning.json file in place, etc.
  try:
    uptane.common.create_directory_structure_for_client(
        client_directory, create_primary_pinning_file(),
        {demo.IMAGE_REPO_NAME: demo.IMAGE_REPO_ROOT_FNAME,
        demo.DIRECTOR_REPO_NAME: os.path.join(demo.DIRECTOR_REPO_DIR, vin,
        'metadata', 'root' + demo.METADATA_EXTENSION)})
  except IOError:
    raise Exception(RED + 'Unable to create Primary client directory '
        'structure. Does the Director Repo for the vehicle exist yet?' +
        ENDCOLORS)

  # Configure tuf with the client's metadata directories (where it stores the
  # metadata it has collected from each repository, in subdirectories).
  tuf.conf.repository_directory = client_directory



  # Initialize a Primary ECU, making a client directory and copying the root
  # file from the repositories.
  primary_ecu = primary.Primary(
      full_client_dir=os.path.join(uptane.WORKING_DIR, client_directory),
      director_repo_name=demo.DIRECTOR_REPO_NAME,
      vin=_vin,
      ecu_serial=_ecu_serial,
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
  except xmlrpc_client.Fault:
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





def create_primary_pinning_file():
  """
  Load the template pinned.json file and save a filled in version that, for the
  Director repository, points to a subdirectory intended for this specific
  vehicle.

  Returns the filename of the created file.
  """

  pinnings = json.load(open(demo.DEMO_PRIMARY_PINNING_FNAME, 'r'))

  fname_to_create = os.path.join(
      demo.DEMO_DIR, 'pinned.json_primary_' + demo.get_random_string(5))

  assert 1 == len(pinnings['repositories'][demo.DIRECTOR_REPO_NAME]['mirrors']), 'Config error.'

  mirror = pinnings['repositories'][demo.DIRECTOR_REPO_NAME]['mirrors'][0]
  mirror = mirror.replace('<VIN>', _vin)

  pinnings['repositories'][demo.DIRECTOR_REPO_NAME]['mirrors'][0] = mirror


  with open(fname_to_create, 'wb') as fobj:
    fobj.write(canonicaljson.encode_canonical_json(pinnings))

  return fname_to_create





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

  tserver = xmlrpc_client.ServerProxy(
      'http://' + str(demo.TIMESERVER_HOST) + ':' + str(demo.TIMESERVER_PORT))
  #if not server.system.listMethods():
  #  raise Exception('Unable to connect to server.')

  print('Submitting a request for a signed time to the Timeserver.')


  if tuf.conf.METADATA_FORMAT == 'der': # TODO: Should check setting in Uptane.
    time_attestation = tserver.get_signed_time_der(nonces_to_send).data

  else:
    time_attestation = tserver.get_signed_time(nonces_to_send)

  # At this point, time_attestation might be a simple Python dictionary or
  # a DER-encoded ASN.1 representation of one.

  # This validates the attestation and also saves the time therein (if the
  # attestation was valid). Secondaries can request this from the Primary at
  # will.
  primary_ecu.validate_time_attestation(time_attestation)

  print('Time attestation validated. New time registered.')



  #
  # SECOND: DOWNLOAD METADATA AND IMAGES
  #

  # Starting with just the root.json files for the Director and Image Repos, and
  # pinned.json, the client will now use TUF to connect to each repository and
  # download/update top-level metadata. This call updates metadata from both
  # repositories.
  # upd.refresh()
  print(GREEN + '\n')
  print(' Now updating top-level metadata from the Director and Image '
      'Repositories\n    (timestamp, snapshot, root, targets)\n' + ENDCOLORS)



  # This will update the Primary's metadata and download images from the
  # Director and Image Repositories, and create a mapping of assignments from
  # each Secondary ECU to its Director-intended target.
  try:
    primary_ecu.primary_update_cycle()

  # Print a REPLAY or DEFENDED banner if ReplayedMetadataError or
  # BadSignatureError is raised by primary_update_cycle().  These banners are
  # only triggered for bad Timestamp metadata, and all other exception are
  # re-raised.
  except tuf.NoWorkingMirrorError as exception:
    director_file = os.path.join(_vin, 'metadata', 'timestamp' + demo.METADATA_EXTENSION)
    for mirror_url in exception.mirror_errors:
      if mirror_url.endswith(director_file):
        if isinstance(exception.mirror_errors[mirror_url], tuf.ReplayedMetadataError):
          print_banner(BANNER_REPLAY, color=WHITE+BLACK_BG,
              text='The Director has instructed us to download a Timestamp'
              ' that is older than the currently trusted version. This'
              ' instruction has been rejected.', sound=TADA)

        elif isinstance(exception.mirror_errors[mirror_url], tuf.BadSignatureError):
          print_banner(BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
              text='The Director has instructed us to download a Timestamp'
              ' that is signed with keys that are untrusted.  This metadata has'
              ' been rejected.', sound=TADA)

        else:
          raise

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

  if tuf.conf.METADATA_FORMAT == 'der':
    # If we're working with DER ECU Manifests, check that the manifest to send
    # is a byte array, and encapsulate it in a Binary() object for XMLRPC
    # transmission.
    uptane.formats.DER_DATA_SCHEMA.check_match(signed_vehicle_manifest)
    signed_vehicle_manifest = xmlrpc_client.Binary(signed_vehicle_manifest)

  else:
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        signed_vehicle_manifest)


  server = xmlrpc_client.ServerProxy(
      'http://' + str(demo.DIRECTOR_SERVER_HOST) + ':' +
      str(demo.DIRECTOR_SERVER_PORT))

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
  server = xmlrpc_client.ServerProxy(
    'http://' + str(demo.DIRECTOR_SERVER_HOST) + ':' +
    str(demo.DIRECTOR_SERVER_PORT))

  print('Registering Primary ECU Serial and Key with Director.')
  server.register_ecu_serial(
      primary_ecu.ecu_serial, primary_ecu.primary_key, _vin, True)
  print(GREEN + 'Primary has been registered with the Director.' + ENDCOLORS)



# This wouldn't be how we'd do it in practice. ECUs would probably be registered
# when put into a vehicle, directly rather than through the Primary.
# def register_secondaries_with_director():
#   """
#   For each of the Secondaries that this Primary is in charge of, send the
#   Director a message registering that Secondary's ECU Serial and public key.
#   """





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
  primary_ecu._check_ecu_serial(ecu_serial)

  image_fname = primary_ecu.get_image_fname_for_ecu(ecu_serial)

  if image_fname is None:
    print('ECU Serial ' + repr(ecu_serial) + ' requested an image, but this '
        'Primary has no update for that ECU.')
    return None, None

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
    #print('Treating requester as full-verification Secondary without a CAN '
    #    'interface because the C CAN interface is off or the ECU Serial (' +
    #    repr(ecu_serial) + ') does not appear in the mapping of ECU Serials '
    #    'to CAN IDs.')

    assert os.path.exists(image_fname), 'File ' + repr(image_fname) + \
        ' does not exist....'
    binary_data = xmlrpc_client.Binary(open(image_fname, 'rb').read())

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
  primary_ecu._check_ecu_serial(ecu_serial)

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
      # print('Treating requester as full-verification Secondary without a CAN '
      #     'interface because the C CAN interface is off or the ECU Serial (' +
      #     repr(ecu_serial) + ') does not appear in the mapping of ECU Serials '
      #     'to CAN IDs.')
      fname = primary_ecu.get_full_metadata_archive_fname()

    if not os.path.exists(fname):
      raise uptane.Error('This Primary does not have a collection of metadata '
          'to distribute to Secondaries.')

    print('Distributing metadata to ECU ' + repr(ecu_serial))

    binary_data = xmlrpc_client.Binary(open(fname, 'rb').read())

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
  primary_ecu._check_ecu_serial(ecu_serial)

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
    # print('Treating requester as full-verification Secondary without a CAN '
    #     'interface because the C CAN interface is off or the ECU Serial (' +
    #     repr(ecu_serial) + ') does not appear in the mapping of ECU Serials '
    #     'to CAN IDs. Sending time attestation back.')

    attestation = primary_ecu.get_last_timeserver_attestation()

    # If we're using ASN.1/DER, then the attestation is binary data we're about
    # to transmit via XMLRPC, so we should wrap it appropriately:
    if tuf.conf.METADATA_FORMAT == 'der':
      attestation = xmlrpc_client.Binary(attestation)

    return attestation





# Restrict Primary requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(xmlrpc_server.SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)





def register_ecu_manifest_wrapper(vin, ecu_serial, nonce, signed_ecu_manifest):
  """
  This function is a wrapper for primary.Primary::register_ecu_manifest().

  This wrapper is now necessary because of ASN.1/DER combined with XMLRPC:
  XMLRPC has to wrap binary data in a Binary() object, and the raw data has to
  be extracted before it is passed to the underlying primary.py (in the
  reference implementation), which doesn't know anything about XMLRPC.
  """
  if tuf.conf.METADATA_FORMAT == 'der':
    primary_ecu.register_ecu_manifest(
        vin, ecu_serial, nonce, signed_ecu_manifest.data)
  else:
    primary_ecu.register_ecu_manifest(
        vin, ecu_serial, nonce, signed_ecu_manifest)





def listen():
  """
  Listens on an available port from list PRIMARY_SERVER_AVAILABLE_PORTS, for
  XML-RPC calls from demo Secondaries for Primary interface calls.
  """

  # Create server to listen for messages from Secondaries. In this
  # demonstration, an XMLRPC server is used and communications are sent in the
  # clear. While this cannot affect the validity of ECU Manifests or violate
  # the validity of images or metadata due to the protections of Uptane,
  # whatever mechanism of transit an OEM employs should nonetheless be
  # secured per the Uptane Deployment Considerations document.
  # The server code employed should be hardened against buffer overflows and
  # the like.
  server = None
  successful_port = None
  last_error = None
  for port in demo.PRIMARY_SERVER_AVAILABLE_PORTS:
    try:
      server = xmlrpc_server.SimpleXMLRPCServer(
          (demo.PRIMARY_SERVER_HOST, port),
          requestHandler=RequestHandler, allow_none=True)
    except socket.error as e:
      print('Failed to bind Primary XMLRPC Listener to port ' + repr(port) +
          '. Trying next port.')
      last_error = e

    else:
      successful_port = port
      break

  if server is None: # All ports failed.
    assert last_error is not None, 'Programming error'
    raise last_error

  #server.register_introspection_functions()

  # Register functions that can be called via XML-RPC, allowing Secondaries to
  # submit ECU Version Manifests, requests timeserver attestations, etc.
  # Implementers should carefully consider what protocol to use for sending
  # ECU manifests. They may not want them sent in the clear, for example.
  # In general, the interface below is not expected to be secure in this
  # demonstration.

  server.register_function(
      # This wrapper is now necessary because of ASN.1/DER combined with XMLRPC:
      # XMLRPC has to wrap binary data in a Binary() object, and the raw data
      # has to be extracted before it is passed to the underlying primary.py
      # (in the reference implementation), which doesn't know anything about
      # XMLRPC.
      register_ecu_manifest_wrapper, 'submit_ecu_manifest')
      # The previous line used to be this:
      #primary_ecu.register_ecu_manifest, 'submit_ecu_manifest')

  # Please note that registrations here are NOT secure, and intended for
  # convenience of the demonstration. An OEM will have their own mechanisms for
  # adding ECUs to their inventory server.
  server.register_function(
      primary_ecu.register_new_secondary, 'register_new_secondary')

  server.register_function(
      primary_ecu.get_last_timeserver_attestation,
      'get_last_timeserver_attestation')

  # Distributing images this way is not ideal: there is no method here (as
  # there IS in TUF in general) of detecting endless data attacks or slow
  # retrieval attacks. OEMs will have their own mechanisms for distribution
  # from Primary to Secondary, and these should follow advice in the Uptane
  # Deployment Considerations document.
  server.register_function(get_image_for_ecu, 'get_image')

  server.register_function(get_metadata_for_ecu, 'get_metadata')

  # This again is for convenience in the demo. While I don't see an obvious
  # security issue, it should be considered whether or not checking such a bit
  # before trying to update foils reporting or otherwise creates a security
  # issue.
  server.register_function(
      primary_ecu.update_exists_for_ecu, 'update_exists_for_ecu')

  # server.register_function(compromise_primary_and_deliver_arbitrary,
  #     'compromise_primary_and_deliver_arbitrary')


  print('Primary will now listen on port ' + str(successful_port))
  server.serve_forever()



def try_banners():
  preview_all_banners()



def looping_update():
  while True:
    try:
      update_cycle()
    except Exception as e:
      print(repr(e))
    time.sleep(1)
