"""
demo_secondary.py

Demonstration code handling a full verification secondary client.


Use:

import demo.demo_secondary as ds
ds.clean_slate() # Director and Primary should be listening first
ds.listen()
ds.generate_signed_ecu_manifest()   # saved as ds.most_recent_signed_manifest
ds.submit_ecu_manifest_to_primary() # optionally takes different signed manifest


(Behind the scenes, that results in a few interactions, ultimately leading to:
      primary_ecu.register_ecu_manifest(
        ds.secondary_ecu.vin,
        ds.secondary_ecu.ecu_serial,
        nonce,
        manifest)



"""

import demo
import uptane
import uptane.common # for canonical key construction and signing
import uptane.clients.secondary as secondary
from uptane import GREEN, RED, YELLOW, ENDCOLORS
import tuf.keys
import tuf.repository_tool as rt
#import tuf.client.updater

import os # For paths and makedirs
import shutil # For copyfile
import threading # for the demo listener
import time
import copy # for copying manifests before corrupting them during attacks
import json # for customizing the Secondary's pinnings file.

from six.moves import xmlrpc_client
from six.moves import xmlrpc_server

# Globals
CLIENT_DIRECTORY_PREFIX = 'temp_secondary' # name for this secondary's directory
client_directory = None
_vin = '111'
_ecu_serial = '22222'
firmware_filename = 'secondary_firmware.txt'
current_firmware_fileinfo = {}
secondary_ecu = None
ecu_key = None
nonce = None

listener_thread = None

most_recent_signed_ecu_manifest = None


def clean_slate(
    use_new_keys=False,
    #client_directory_name=None,
    vin=_vin,
    ecu_serial=_ecu_serial):
  """
  """

  global secondary_ecu
  global _vin
  global _ecu_serial
  global nonce
  global listener_thread
  global client_directory

  _vin = vin
  _ecu_serial = ecu_serial

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

  CLIENT_METADATA_DIR_MAINREPO_CURRENT = os.path.join(client_directory, 'metadata', 'mainrepo', 'current')
  CLIENT_METADATA_DIR_MAINREPO_PREVIOUS = os.path.join(client_directory, 'metadata', 'mainrepo', 'previous')
  CLIENT_METADATA_DIR_DIRECTOR_CURRENT = os.path.join(client_directory, 'metadata', 'director', 'current')
  CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS = os.path.join(client_directory, 'metadata', 'director', 'previous')

  # Note that the hosts and ports for the repositories are drawn from
  # pinned.json now. The services (timeserver and the director's
  # submit-manifest service) are still addressed here, though, currently
  # by pulling the constants from their modules directly
  # e.g. timeserver.TIMESERVER_PORT and director.DIRECTOR_SERVER_PORT).
  # Note that despite the vague name, the latter is not the director
  # repository, but a service that receives manifests.


  # Set up the TUF client directories for the two repositories.
  if os.path.exists(client_directory):
    shutil.rmtree(client_directory)

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

  # Add a pinned.json to this client (softlink it from a saved copy).
  os.symlink(
      create_secondary_pinning_file(),
      os.path.join(client_directory, 'metadata', 'pinned.json'))

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

  pinnings = json.load(open(demo.DEMO_SECONDARY_PINNING_FNAME, 'r'))

  fname_to_create = os.path.join(
      demo.DEMO_DIR, 'pinned.json_' + demo.get_random_string(5))

  for repo_name in pinnings['repositories']:

    assert 1 == len(pinnings['repositories'][repo_name]['mirrors']), 'Config error.'

    mirror = pinnings['repositories'][repo_name]['mirrors'][0]

    mirror = mirror.replace('<full_client_dir>', client_directory)

    pinnings['repositories'][repo_name]['mirrors'][0] = mirror


  with open(fname_to_create, 'w') as fobj:
    json.dump(pinnings, fobj)

  return fname_to_create






# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(xmlrpc_server.SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)



def listen():
  """
  Listens on SECONDARY_SERVER_PORT for xml-rpc calls to functions

  NOTE: At the time of this writing, Secondaries in the demo don't need to
  listen for asynchronous messages from Primaries, as Secondaries do the
  pulling and pushing themselves whenever they will.
  """

  global listener_thread

  # Create server
  server = xmlrpc_server.SimpleXMLRPCServer(
      (demo.SECONDARY_SERVER_HOST, demo.SECONDARY_SERVER_PORT),
      requestHandler=RequestHandler, allow_none=True)
  #server.register_introspection_functions()

  # Register function that can be called via XML-RPC, allowing a Primary to
  # send metadata and images to the Secondary.
  server.register_function(
      secondary_ecu.receive_msg_from_primary, 'receive_msg_from_primary')

  print(' Secondary will now listen on port ' + str(demo.SECONDARY_SERVER_PORT))

  if listener_thread is not None:
    print('Sorry - there is already a Secondary thread listening.')
    return
  else:
    print(' Starting Secondary Listener Thread: will now listen on port ' +
        str(demo.SECONDARY_SERVER_PORT))
    listener_thread = threading.Thread(target=server.serve_forever)
    listener_thread.setDaemon(True)
    listener_thread.start()





def submit_ecu_manifest_to_primary(signed_ecu_manifest=None):

  global most_recent_signed_ecu_manifest
  if signed_ecu_manifest is None:
    signed_ecu_manifest = most_recent_signed_ecu_manifest


  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
      signed_ecu_manifest)
  # TODO: <~> Be sure to update the previous line to indicate an ASN.1
  # version of the ecu_manifest after encoders have been implemented.


  server = xmlrpc_client.ServerProxy(
      'http://' + str(demo.PRIMARY_SERVER_HOST) + ':' +
      str(demo.PRIMARY_SERVER_PORT))
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

  # Connect to the Primary
  pserver = xmlrpc_client.ServerProxy(
    'http://' + str(demo.PRIMARY_SERVER_HOST) + ':' +
    str(demo.PRIMARY_SERVER_PORT))

  # Download the time attestation from the Primary.
  time_attestation = pserver.get_last_timeserver_attestation()

  # Download the metadata from the Primary in the form of an archive. This
  # returns the binary data that we need to write to file.
  metadata_archive = pserver.get_metadata(secondary_ecu.ecu_serial)

  # Validate the time attestation and internalize the time. Continue
  # regardless.
  try:
    secondary_ecu.validate_time_attestation(time_attestation)
  except uptane.BadTimeAttestation as e:
    print(RED + "Timeserver attestation from Primary did not check out! This "
        "Secondary's nonce was not found. Not updating this Secondary's time." +
        ENDCOLORS)
  except tuf.BadSignatureError as e:
    print(RED + "Timeserver attestation from Primary did not check out! Bad "
        "signature. Not updating this Secondary's time." + ENDCOLORS)
  #else:
  #  print(GREEN + 'Official time has been updated successfully.' + ENDCOLORS)


  # Not doing this anymore:
  # # Write the metadata to files to use as a local TUF repository.
  # # We'll use a directory in the client's directory, "unverified", with
  # # subdirectories for each repository:
  # #  client_directory/unverified/<reponame>/metadata
  # # This function will do some minimal checks to make sure that the Primary
  # # hasn't sent us a "repository name" that results in us writing files to
  # # inappropriate places in our filesystem.
  # # We'll use a directory in the client's directory, "unverified", with
  # # subdirectories for each repository:
  # #  client_directory/unverified/<reponame>/metadata
  # # This has to match the pinned.json this Secondary client uses, which is
  # # created from template demo/pinned_secondary_template.json by call
  # # create_secondary_pinning_file above.
  # write_multirepo_tuf_metadata_to_files(
  #     metadata=metadata,
  #     metadata_directory=os.path.join(client_directory, 'unverified'))

  # Instead, dump the archive file to disk.
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
    print(YELLOW + 'No validated targets were found. Either the Director '
        'did not instruct this ECU to install anything, or the target info '
        'the Director provided could not be validated.' + ENDCOLORS)
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return


  elif len(secondary_ecu.validated_targets_for_this_ecu) > 1:
    assert False, 'Multiple targets for an ECU not supported in this demo.'


  expected_target_info = secondary_ecu.validated_targets_for_this_ecu[0]

  expected_image_fname = expected_target_info['filepath']
  if expected_image_fname[0] == '/':
    expected_image_fname = expected_image_fname[1:]


  # Since metadata validation worked out, check if the Primary says we have an
  # image to download and then download it.
  # TODO: <~> Cross-check this: we have the metadata now, so we and the Primary
  # should agree on whether or not there is an image to download.
  if not pserver.update_exists_for_ecu(secondary_ecu.ecu_serial):
    print(YELLOW + 'Primary reports that there is no update for this ECU.')
    (image_fname, image) = pserver.get_image(secondary_ecu.ecu_serial)
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()

  # Download the image for this ECU from the Primary.
  (image_fname, image) = pserver.get_image(secondary_ecu.ecu_serial)

  if image is None:
    print(YELLOW + 'Requested image from Primary but received none. Update '
        'terminated.' + ENDCOLORS)
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return

  elif not secondary_ecu.validated_targets_for_this_ecu:
    print(RED + 'Requested and received image from Primary, but metadata '
        'indicates no valid targets from the Director intended for this ECU. '
        'Update terminated.' + ENDCOLORS)
    generate_signed_ecu_manifest()
    submit_ecu_manifest_to_primary()
    return

  elif image_fname != expected_image_fname:
    # Make sure that the image name provided by the Primary actually matches
    # the name of a validated target for this ECU, otherwise we don't need it.
    print(RED + 'Requested and received image from Primary, but this '
        'Secondary has not validated any target info that matches the given ' +
        'filename. Aborting "install".' + ENDCOLORS)
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
  secondary_ecu.validate_image(image_fname)


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


  print(GREEN + 'Installed firmware received from Primary that was fully '
      'validated by the Director and OEM Repo.' + ENDCOLORS)

  if expected_target_info['filepath'].endswith('.txt'):
    print('The contents of the newly-installed firmware with filename ' +
        repr(expected_target_info['filepath']) + ' are:')
    print('---------------------------------------------------------')
    print(open(os.path.join(client_directory, image_fname)).read())
    print('---------------------------------------------------------')


  # Submit info on what is currently installed back to the Primary.
  generate_signed_ecu_manifest()
  submit_ecu_manifest_to_primary()



# No longer doing this:
# def write_multirepo_tuf_metadata_to_files(metadata, metadata_directory):
#   """
#   Writes TUF metadata from several repositories into a directory to serve as
#   a set of local repositories for metadata.

#   Since the repository name provided may not be trustworthy from the Primary, we make sure it doesn't
#   contain slashes, say, and try to get us to create files somewhere bizarre.


#   <Arguments>

#     metadata
#       Metadata from any number of repsitories, in a dictionary indexed by
#       repository name, with each value being a dict of metadata of the form that
#       is returned by tuf.updater.Updater.get_metadata.
#       Example:
#         {
#           'repo1':
#             'root': {'_type': 'Root',
#               'compression_algorithms': ['gz'],
#               'consistent_snapshot': False,
#               ...
#             'targets': {'_type': 'Targets',
#               'delegations': {'keys': {}, 'roles': []},
#               'expires': '2017-02-15T02:55:05Z',
#               ...
#             ...
#           'repo2':
#             'root': {...},
#             ...
#         }

#     metadata_directory
#       The directory into which we will put the metadata, with subdirectories
#       for each repository:
#         <metadata_directory>/<repo_name>/metadata

#   """
#   for repo_name in metadata:

#     safer_repo_metadata_directory = enforce_jail(
#         os.path.join(metadata_directory, repo_name, 'metadata'),
#         client_directory)

#     os.makedirs(safer_repo_metadata_directory)

#     # TODO: Mind this. This will have to change if the structure of TUF
#     # repositories changes (as it probably has in a branch we have to merge
#     # shortly for TAP 5 that might put delegated roles in a different
#     # directory).
#     for role_name in metadata[repo_name]:

#       safer_role_fname = enforce_jail(
#           os.path.join(safer_repo_metadata_directory, role_name + '.json'),
#           safer_repo_metadata_directory)

#       json.dump(metadata[repo_name][role_name], open(safer_role_fname, 'w'))



def generate_signed_ecu_manifest():

  global secondary_ecu
  global most_recent_signed_ecu_manifest

  # Generate and sign a manifest indicating that this ECU has a particular
  # version/hash/size of file2.txt as its firmware.
  most_recent_signed_ecu_manifest = secondary_ecu.generate_signed_ecu_manifest()





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




def ATTACK_send_manifest_with_wrong_sig_to_primary():
  """
  Attack: MITM w/o key modifies ECU manifest and signs with a different ECU's
  key.
  """
  # Discard the signatures and copy the signed contents of the most recent
  # signed ecu manifest.
  import copy
  corrupt_manifest = copy.copy(most_recent_signed_ecu_manifest['signed'])

  corrupt_manifest['attacks_detected'] += 'Everything is great; PLEASE BELIEVE ME THIS TIME!'

  signable_corrupt_manifest = tuf.formats.make_signable(corrupt_manifest)
  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
      signable_corrupt_manifest)

  # Attacker loads a key she may have (perhaps some other ECU's key)
  key2_pub = demo.import_public_key('secondary2')
  key2_pri = demo.import_private_key('secondary2')
  ecu2_key = uptane.common.canonical_key_from_pub_and_pri(key2_pub, key2_pri)
  keys = [ecu2_key]

  # Attacker signs the modified manifest with that other key.
  signed_corrupt_manifest = uptane.common.sign_signable(
      signable_corrupt_manifest, keys)
  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
      signed_corrupt_manifest)

  try:
    submit_ecu_manifest_to_primary(signed_corrupt_manifest)
  except xmlrpc_client.Fault as e:
    print('Primary REJECTED the fraudulent ECU manifest.')
  else:
    print('Primary ACCEPTED the fraudulent ECU manifest!')
  # (Next, on the Primary, one would generate the vehicle manifest and submit
  # that to the Director. The Director, in its window, should then indicate that
  # it has received this manifest and rejected it because the signature doesn't
  # match what is expected.)





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
  server.register_ecu_serial(secondary_ecu.ecu_serial, secondary_ecu.ecu_key)
  print(GREEN + 'Secondary has been registered with the Director.' + ENDCOLORS)





def register_self_with_primary():
  """
  Send the Primary a message to register our ECU serial number.
  In practice, this would probably be done out of band, when the ECU is put
  into the vehicle during assembly, not by the Secondary itself.
  """
  # Connect to the Primary
  server = xmlrpc_client.ServerProxy(
    'http://' + str(demo.PRIMARY_SERVER_HOST) + ':' +
    str(demo.PRIMARY_SERVER_PORT))

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
