"""
demo_secondary.py

Demonstration code handling a full verification secondary client.


Use:

import demo.demo_secondary as ds
ds.clean_slate() # Director and Primary should be listening first
ds.generate_signed_ecu_manifest()   # saved as ds.most_recent_signed_manifest
ds.submit_ecu_manifest_to_primary() # optionally takes different signed manifest


(Behind the scenes, that results in a few interactions, ultimately leading to:
      primary_ecu.register_ecu_manifest(
        ds.secondary_ecu.vin,
        ds.secondary_ecu.ecu_serial,
        nonce,
        manifest)



"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open

import demo
import uptane # Import before TUF modules; may change tuf.conf values.
import uptane.common # for canonical key construction and signing
import uptane.clients.secondary as secondary
from uptane import GREEN, RED, YELLOW, ENDCOLORS
from demo.uptane_banners import *
import tuf.keys
import tuf.repository_tool as rt
#import tuf.client.updater

import os # For paths and makedirs
import shutil # For copyfile
import time
import copy # for copying manifests before corrupting them during attacks
import json # for customizing the Secondary's pinnings file.
import canonicaljson

from six.moves import xmlrpc_client

# Globals
CLIENT_DIRECTORY_PREFIX = 'temp_secondary' # name for this secondary's directory
client_directory = None
_vin = '111'
_ecu_serial = '22222'
_primary_host = demo.PRIMARY_SERVER_HOST
_primary_port = demo.PRIMARY_SERVER_DEFAULT_PORT
firmware_filename = 'secondary_firmware.txt'
current_firmware_fileinfo = {}
secondary_ecu = None
ecu_key = None
nonce = None
attacks_detected = ''

most_recent_signed_ecu_manifest = None


def clean_slate(
    use_new_keys=False,
    #client_directory_name=None,
    vin=_vin,
    ecu_serial=_ecu_serial,
    primary_host=None,
    primary_port=None):
  """
  """

  global secondary_ecu
  global _vin
  global _ecu_serial
  global _primary_host
  global _primary_port
  global nonce
  global client_directory
  global attacks_detected

  _vin = vin
  _ecu_serial = ecu_serial

  if primary_host is not None:
    _primary_host = primary_host

  if primary_port is not None:
    _primary_port = primary_port

  client_directory = os.path.join(
      uptane.WORKING_DIR, CLIENT_DIRECTORY_PREFIX + demo.get_random_string(5))

  # Load the public timeserver key.
  key_timeserver_pub = demo.import_public_key('timeserver')

  # Set starting firmware fileinfo (that this ECU had coming from the factory)
  factory_firmware_fileinfo = {
      'filepath': '/secondary_firmware.txt',
      'fileinfo': {
          'hashes': {
              'sha512': '706c283972c5ae69864b199e1cdd9b4b8babc14f5a454d0fd4d3b35396a04ca0b40af731671b74020a738b5108a78deb032332c36d6ae9f31fae2f8a70f7e1ce',
              'sha256': '6b9f987226610bfed08b824c93bf8b2f59521fce9a2adef80c495f363c1c9c44'},
          'length': 37}}

  # Prepare this ECU's key.
  load_or_generate_key(use_new_keys)

  # Generate a trusted initial time for the Secondary.
  clock = tuf.formats.unix_timestamp_to_datetime(int(time.time()))
  clock = clock.isoformat() + 'Z'
  tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(clock)




  # Create directory structure for the client and copy the root files from the
  # repositories.
  uptane.common.create_directory_structure_for_client(
      client_directory, create_secondary_pinning_file(),
      {demo.IMAGE_REPO_NAME: demo.IMAGE_REPO_ROOT_FNAME,
      demo.DIRECTOR_REPO_NAME: os.path.join(demo.DIRECTOR_REPO_DIR, vin,
      'metadata', 'root' + demo.METADATA_EXTENSION)})

  # Configure tuf with the client's metadata directories (where it stores the
  # metadata it has collected from each repository, in subdirectories).
  tuf.conf.repository_directory = client_directory # This setting should probably be called client_directory instead, post-TAP4.



  # Initialize a full verification Secondary ECU.
  # This also generates a nonce to use in the next time query, sets the initial
  # firmware fileinfo, etc.
  secondary_ecu = secondary.Secondary(
      full_client_dir=client_directory,
      director_repo_name=demo.DIRECTOR_REPO_NAME,
      vin=_vin,
      ecu_serial=_ecu_serial,
      ecu_key=ecu_key,
      time=clock,
      firmware_fileinfo=factory_firmware_fileinfo,
      timeserver_public_key=key_timeserver_pub)



  try:
    register_self_with_director()
  except xmlrpc_client.Fault:
    print('Registration with Director failed. Now assuming this Secondary is '
        'already registered.')

  try:
    register_self_with_primary()
  except xmlrpc_client.Fault:
    print('Registration with Primary failed. Now assuming this Secondary is '
        'already registered.')


  print('\n' + GREEN + ' Now simulating a Secondary that rolled off the '
      'assembly line\n and has never seen an update.' + ENDCOLORS)
  print("Generating this Secondary's first ECU Version Manifest and sending "
      "it to the Primary.")

  generate_signed_ecu_manifest()
  submit_ecu_manifest_to_primary()





def create_secondary_pinning_file():
  """
  Load the template pinned.json file and save a filled in version that points
  to the client's own directory. (The TUF repository that a Secondary points
  to is local, retrieved from the Primary and placed in the Secondary itself
  to validate the file internally.)

  Returns the filename of the created file.
  """

  pinnings = json.load(
      open(demo.DEMO_SECONDARY_PINNING_FNAME, 'r', encoding='utf-8'))

  fname_to_create = os.path.join(
      demo.DEMO_DIR, 'pinned.json_secondary_' + demo.get_random_string(5))

  for repo_name in pinnings['repositories']:

    assert 1 == len(pinnings['repositories'][repo_name]['mirrors']), 'Config error.'

    mirror = pinnings['repositories'][repo_name]['mirrors'][0]

    mirror = mirror.replace('<full_client_dir>', client_directory)

    pinnings['repositories'][repo_name]['mirrors'][0] = mirror

  with open(fname_to_create, 'wb') as fobj:
    fobj.write(canonicaljson.encode_canonical_json(pinnings))

  return fname_to_create





def submit_ecu_manifest_to_primary(signed_ecu_manifest=None):

  global most_recent_signed_ecu_manifest
  if signed_ecu_manifest is None:
    signed_ecu_manifest = most_recent_signed_ecu_manifest


  if tuf.conf.METADATA_FORMAT == 'der':
    # TODO: Consider validation of DER manifests as well here. (Harder)

    # If we're using ASN.1/DER data, then we have to transmit this slightly
    # differently via XMLRPC, wrapped in a Binary object.
    signed_ecu_manifest = xmlrpc_client.Binary(signed_ecu_manifest)

  else:
    # Otherwise, we're working with standard Python dictionary data as
    # specified in uptane.formats. Validate and keep as-is.
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)


  server = xmlrpc_client.ServerProxy(
      'http://' + str(_primary_host) + ':' + str(_primary_port))
  #if not server.system.listMethods():
  #  raise Exception('Unable to connect to server.')

  server.submit_ecu_manifest(
      secondary_ecu.vin,
      secondary_ecu.ecu_serial,
      secondary_ecu.nonce_next,
      signed_ecu_manifest)

  # We don't switch to a new nonce for next time yet. That only happens when a
  # time attestation using that nonce is validated.
  # "Nonces" may be sent multiple times, but only validated once.
  secondary_ecu.set_nonce_as_sent()





def load_or_generate_key(use_new_keys=False):
  """Load or generate an ECU's private key."""

  global ecu_key

  if use_new_keys:
    demo.generate_key('secondary')

  # Load in from the generated files.
  key_pub = demo.import_public_key('secondary')
  key_pri = demo.import_private_key('secondary')

  ecu_key = uptane.common.canonical_key_from_pub_and_pri(key_pub, key_pri)




def update_cycle():
  """
  Updates our metadata and images from the Primary. Raises the appropriate
  tuf and uptane errors if metadata or the image don't validate.
  """

  global secondary_ecu
  global current_firmware_fileinfo
  global attacks_detected

  # Connect to the Primary
  pserver = xmlrpc_client.ServerProxy(
    'http://' + str(_primary_host) + ':' + str(_primary_port))

  # Download the time attestation from the Primary.
  time_attestation = pserver.get_last_timeserver_attestation()
  if tuf.conf.METADATA_FORMAT == 'der':
    # Binary data transfered via XMLRPC has to be wrapped in an xmlrpc Binary
    # object. The data itself is contained in attribute 'data'.
    # When running the demo using ASN.1/DER mode, metadata is in binary, and
    # so this xmlrpc Binary object is used and the data should be extracted
    # from it like so:
    time_attestation = time_attestation.data

  # Download the metadata from the Primary in the form of an archive. This
  # returns the binary data that we need to write to file.
  metadata_archive = pserver.get_metadata(secondary_ecu.ecu_serial)

  # Validate the time attestation and internalize the time. Continue
  # regardless.
  try:
    secondary_ecu.validate_time_attestation(time_attestation)
  except uptane.BadTimeAttestation as e:
    print("Timeserver attestation from Primary does not check out: "
        "This Secondary's nonce was not found. Not updating this Secondary's "
        "time this cycle.")
  except tuf.BadSignatureError as e:
    print(RED + "Timeserver attestation from Primary did not check out. Bad "
        "signature. Not updating this Secondary's time." + ENDCOLORS)
    attacks_detected += 'Timeserver attestation had bad signature.\n'

  #else:
  #  print(GREEN + 'Official time has been updated successfully.' + ENDCOLORS)

  # Dump the archive file to disk.
  archive_fname = os.path.join(
      secondary_ecu.full_client_dir, 'metadata_archive.zip')

  with open(archive_fname, 'wb') as fobj:
    fobj.write(metadata_archive.data)

  # Now tell the Secondary reference implementation code where the archive file
  # is and let it expand and validate the metadata.
  secondary_ecu.process_metadata(archive_fname)


  # As part of the process_metadata call, the secondary will have saved
  # validated target info for targets intended for it in
  # secondary_ecu.validated_targets_for_this_ecu.

  # For now, expect no more than 1 target for an ECU. I suspect that the
  # reference implementation will eventually support more. For now, I've kept
  # things flexible in a number of parts of the reference implementation, in
  # this regard. The demo, though, doesn't have use for that tentative
  # flexibility.

  if len(secondary_ecu.validated_targets_for_this_ecu) == 0:
    print_banner(BANNER_NO_UPDATE, color=WHITE+BLACK_BG,
        text='No validated targets were found. Either the Director '
        'did not instruct this ECU to install anything, or the target info '
        'the Director provided could not be validated.')
    # print(YELLOW + 'No validated targets were found. Either the Director '
    #     'did not instruct this ECU to install anything, or the target info '
    #     'the Director provided could not be validated.' + ENDCOLORS)
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return


  #elif len(secondary_ecu.validated_targets_for_this_ecu) > 1:
  #  assert False, 'Multiple targets for an ECU not supported in this demo.'


  expected_target_info = secondary_ecu.validated_targets_for_this_ecu[-1]

  expected_image_fname = expected_target_info['filepath']
  if expected_image_fname[0] == '/':
    expected_image_fname = expected_image_fname[1:]


  # Since metadata validation worked out, check if the Primary says we have an
  # image to download and then download it.
  # TODO: <~> Cross-check this: we have the metadata now, so we and the Primary
  # should agree on whether or not there is an image to download.
  if not pserver.update_exists_for_ecu(secondary_ecu.ecu_serial):

    print_banner(BANNER_NO_UPDATE, color=WHITE+BLACK_BG,
        text='Primary reports that there is no update for this ECU.')
    # print(YELLOW + 'Primary reports that there is no update for this ECU.')
    (image_fname, image) = pserver.get_image(secondary_ecu.ecu_serial)
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return

  # Download the image for this ECU from the Primary.
  (image_fname, image) = pserver.get_image(secondary_ecu.ecu_serial)

  if image is None:
    print(YELLOW + 'Requested image from Primary but received none. Update '
        'terminated.' + ENDCOLORS)
    attacks_detected += 'Requested image from Primary but received none.\n'
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return

  elif not secondary_ecu.validated_targets_for_this_ecu:
    print(RED + 'Requested and received image from Primary, but metadata '
        'indicates no valid targets from the Director intended for this ECU. '
        'Update terminated.' + ENDCOLORS)
    # TODO: Determine if something should be added to attacks_detected here.
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return

  elif image_fname != expected_image_fname:
    # Make sure that the image name provided by the Primary actually matches
    # the name of a validated target for this ECU, otherwise we don't need it.
    print(RED + 'Requested and received image from Primary, but this '
        'Secondary has not validated any target info that matches the given ' +
        'filename. Expected: ' + repr(expected_image_fname) + '; received: ' +
        repr(image_fname) + '; aborting "install".' + ENDCOLORS)
    # print_banner(
    #     BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
    #     text='Image from Primary is not listed in trusted metadata. Possible '
    #     'attack from Primary averted. Image: ' +
    #     repr(image_fname))#, sound=TADA)
    attacks_detected += 'Received unexpected image from Primary with ' + \
        'unexpected filename.\n'
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return

  # Write the downloaded image binary data to disk.
  unverified_targets_dir = os.path.join(client_directory, 'unverified_targets')
  if not os.path.exists(unverified_targets_dir):
    os.mkdir(unverified_targets_dir)
  with open(os.path.join(unverified_targets_dir, image_fname), 'wb') as fobj:
    fobj.write(image.data)


  # Validate the image against the metadata.
  try:
    secondary_ecu.validate_image(image_fname)
  except tuf.DownloadLengthMismatchError:
    print_banner(
        BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
        text='Image from Primary failed to validate: length mismatch. Image: ' +
        repr(image_fname), sound=TADA)
    # TODO: Add length comparison instead, from error.
    attacks_detected += 'Image from Primary failed to validate: length ' + \
        'mismatch.\n'
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return
  except tuf.BadHashError:
    print_banner(
        BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
        text='Image from Primary failed to validate: hash mismatch. Image: ' +
        repr(image_fname), sound=TADA)
    # TODO: Add hash comparison instead, from error.
    attacks_detected += 'Image from Primary failed to validate: hash ' + \
        'mismatch.\n'
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return



  if secondary_ecu.firmware_fileinfo == expected_target_info:
    print_banner(
      BANNER_NO_UPDATE_NEEDED, color=WHITE+BLACK_BG,
      text='We already have installed the firmware that the Director wants us '
          'to install. Image: ' + repr(image_fname))
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return

  # Inspect the contents of 'image_fname' and search for the string: "evil
  # content".  If this single string is found in any of the images downloaded,
  # print a BANNER_COMPROMISED banner.
  image_filepath = os.path.join(client_directory, 'unverified_targets', image_fname)

  with open(image_filepath, 'rb') as file_object:
    if file_object.read() == b'evil content':
      # If every safeguard is defeated and a compromised update is delivered, a
      # real Secondary can't necessarily know it has been compromised, as every
      # check has passed. For the purposes of the demo, of course, we know when
      # a compromise has been delivered, and we'll flash a Compromised screen
      # to indicate a successful attack. We know this has happened because the
      # demo should include 'evil content' in the file.  This requires,
      # generally, a compromise of both Image Repo and Director keys.
      print_banner(BANNER_COMPROMISED, color=WHITE+RED_BG,
          text='A malicious update has been installed! Arbitrary package attack '
          'successful: this Secondary has been compromised! Image: ' +
          repr(expected_image_fname), sound=WITCH)
      generate_signed_ecu_manifest()
      submit_ecu_manifest_to_primary()
      return

  # Simulate installation. (If the demo eventually uses pictures to move into
  # place or something, here is where to do it.)
  # 1. Move the downloaded image from the unverified targets subdirectory to
  #    the root of the client directory.
  if os.path.exists(os.path.join(client_directory, image_fname)):
    os.remove(os.path.join(client_directory, image_fname))
  os.rename(
      os.path.join(client_directory, 'unverified_targets', image_fname),
      os.path.join(client_directory, image_fname))

  # 2. Set the fileinfo in the secondary_ecu object to the target info for the
  #    new firmware.
  secondary_ecu.firmware_fileinfo = expected_target_info


  print_banner(
      BANNER_UPDATED, color=WHITE+GREEN_BG,
      text='Installed firmware received from Primary that was fully '
      'validated by the Director and Image Repo. Image: ' + repr(image_fname),
      sound=WON)

  if expected_target_info['filepath'].endswith('.txt'):
    print('The contents of the newly-installed firmware with filename ' +
        repr(expected_target_info['filepath']) + ' are:')
    print('---------------------------------------------------------')
    print(open(os.path.join(client_directory, image_fname)).read())
    print('---------------------------------------------------------')


  # Submit info on what is currently installed back to the Primary.
  generate_signed_ecu_manifest()
  submit_ecu_manifest_to_primary()





def generate_signed_ecu_manifest():

  global secondary_ecu
  global most_recent_signed_ecu_manifest
  global attacks_detected

  # Generate and sign a manifest indicating that this ECU has a particular
  # version/hash/size of file2.txt as its firmware.
  most_recent_signed_ecu_manifest = secondary_ecu.generate_signed_ecu_manifest(
      attacks_detected)

  attacks_detected = ''





def ATTACK_send_corrupt_manifest_to_primary():
  """
  Attack: MITM w/o key modifies ECU manifest.
  Modify the ECU manifest without updating the signature.
  """
  # Copy the most recent signed ecu manifest.
  import copy
  corrupt_signed_manifest = copy.copy(most_recent_signed_ecu_manifest)

  corrupt_signed_manifest['signed']['attacks_detected'] += 'Everything is great, I PROMISE!'

  print(YELLOW + 'ATTACK: Corrupted Manifest (bad signature):' + ENDCOLORS)
  print('   Modified the signed manifest as a MITM, simply changing a value:')
  print('   The attacks_detected field now reads "' + RED +
      repr(corrupt_signed_manifest['signed']['attacks_detected']) + ENDCOLORS)

  try:
    submit_ecu_manifest_to_primary(corrupt_signed_manifest)
  except xmlrpc_client.Fault:
    print(GREEN + 'Primary REJECTED the fraudulent ECU manifest.' + ENDCOLORS)
  else:
    print(RED + 'Primary ACCEPTED the fraudulent ECU manifest!' + ENDCOLORS)
  # (Next, on the Primary, one would generate the vehicle manifest and submit
  # that to the Director. The Director, in its window, should then indicate that
  # it has received this manifest and rejected it because the signature isn't
  # a valid signature over the changed ECU manifest.)





def register_self_with_director():
  """
  Send the Director a message to register our ECU serial number and Public Key.
  In practice, this would probably be done out of band, when the ECU is put
  into the vehicle during assembly, not through the Secondary or Primary
  themselves.
  """
  # Connect to the Director
  server = xmlrpc_client.ServerProxy(
    'http://' + str(demo.DIRECTOR_SERVER_HOST) + ':' +
    str(demo.DIRECTOR_SERVER_PORT))

  print('Registering Secondary ECU Serial and Key with Director.')
  server.register_ecu_serial(
      secondary_ecu.ecu_serial,
      uptane.common.public_key_from_canonical(secondary_ecu.ecu_key), _vin,
      False)
  print(GREEN + 'Secondary has been registered with the Director.' + ENDCOLORS)





def register_self_with_primary():
  """
  Send the Primary a message to register our ECU serial number.
  In practice, this would probably be done out of band, when the ECU is put
  into the vehicle during assembly, not by the Secondary itself.
  """
  # Connect to the Primary
  server = xmlrpc_client.ServerProxy(
    'http://' + str(_primary_host) + ':' + str(_primary_port))

  print('Registering Secondary ECU Serial and Key with Primary.')
  server.register_new_secondary(secondary_ecu.ecu_serial)
  print(GREEN + 'Secondary has been registered with the Primary.' + ENDCOLORS)





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




def try_banners():
  preview_all_banners()


def looping_update():
  while True:
    try:
      update_cycle()
    except Exception as e:
      print(repr(e))
      pass
    time.sleep(1)
