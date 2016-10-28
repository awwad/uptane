"""
demo_oem_repo.py

Demonstration code handling a full verification secondary client.
"""

import os # For paths and makedirs
import shutil # For copyfile
import tuf.client.updater
import tuf.repository_tool as rt
import tuf.keys
import uptane.clients.secondary as secondary
import uptane.common # for canonical key construction and signing
import uptane.director.timeserver as timeserver # for the port

# Colorful printing for demo.
RED = '\033[41m\033[30m' # black on red
GREEN = '\033[42m\033[30m' # black on green
YELLOW = '\033[93m' # yellow on black
ENDCOLORS = '\033[0m'


# Globals
client_directory_name = 'clientane' # name for this secondary's directory
vin = 'vin1111'
# ecu_serial = None
firmware_filename = 'file2.txt'
current_firmware_fileinfo = {}
secondary_ecu = None
ecu_key = None

def clean_slate(
    use_new_keys=False, client_directory_name='clientane', vin='111',
    ecu_serial='ecu11111'):
  """
  """

  global secondary_ecu

  # Load the public timeserver key.
  key_timeserver_pub = rt.import_ed25519_publickey_from_file('timeserver.pub')

  # Create a full metadata verification secondary, using directory 'clientane',
  # making a client directory and copying the root file from the repository.
  secondary_ecu = secondary.Secondary(
      client_directory_name, ecu_serial,
      timeserver_public_key=key_timeserver_pub)

  # Generate a nonce and get the time from the timeserver.
  nonce = secondary_ecu._create_nonce()
  secondary_ecu.update_time_from_timeserver(nonce)

  # Repeat, so that the secondary has both most recent and previous times.
  # It will use both when generating a manifest to send to the Director later.
  nonce = secondary_ecu._create_nonce()
  secondary_ecu.update_time_from_timeserver(nonce)

  #print('After two calls to the timeserver, Secondary has these times: ')
  #print('  Latest:' + repr(secondary_ecu.most_recent_timeserver_time))
  #print('  Previous:' + repr(secondary_ecu.previous_timeserver_time))

  load_or_generate_key(use_new_keys)


  print(GREEN + '\n Now simulating a Primary that rolled off the assembly line'
      '\n and has never seen an update.\n' + ENDCOLORS)



def load_or_generate_key(use_new_keys=False):
  """Load or generate an ECU's private key."""

  global ecu_key

  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('secondary', password='pw')

  # Load in from the generated files.
  key_pub = rt.import_ed25519_publickey_from_file('secondary.pub')
  key_pri = rt.import_ed25519_privatekey_from_file('secondary', password='pw')

  ecu_key = uptane.common.canonical_key_from_pub_and_pri(key_pub, key_pri)




def update_cycle():
  """
  """

  global secondary_ecu
  global current_firmware_fileinfo

  # Starting with just the root.json files for the director and mainrepo, and
  # pinned.json, the client will now use TUF to connect to each repository and
  # download/update top-level metadata. This call updates metadata from both
  # repositories.
  # upd.refresh()
  print(GREEN + '\n')
  print(' Now updating top-level metadata from the Director and OEM Repositories'
      '\n    (timestamp, snapshot, root, targets)')
  print('\n' + ENDCOLORS)
  secondary_ecu.refresh_toplevel_metadata_from_repositories()


  # Get the list of targets the director expects us to download and update to.
  # Note that at this line, this target info is not yet validated with the
  # supplier repo: that is done a few lines down.
  directed_targets = secondary_ecu.get_target_list_from_director()

  print()
  print(YELLOW + ' A correctly signed statement from the Director indicates that')

  if not directed_targets:
    print(' we have no updates to install.\n' + ENDCOLORS)
    return

  else:
    print(' that we should install these files:\n')
    for targ in directed_targets:
      print('    ' + targ['filepath'])
    print(ENDCOLORS)

  # This call determines what the right fileinfo (hash, length, etc) for
  # target file file2.txt is. This begins by matching paths/patterns in
  # pinned.json to determine which repository to connect to. Since pinned.json
  # in this case assigns all targets to a multi-repository delegation requiring
  # consensus between the two repos "director" and "mainrepo", this call will
  # retrieve metadata from both repositories and compare it to each other, and
  # only return fileinfo if it can be retrieved from both repositories and is
  # identical (the metadata in the "custom" fileinfo field need not match, and
  # should not, since the Director will include ECU IDs in this field, and the
  # mainrepo cannot.
  # In this particular case, fileinfo will match and be stored, since both
  # repositories list file2.txt as a target, and they both have matching metadata
  # for it.
  print(' Retrieving validated image file metadata from Director and OEM '
      'Repositories.')
  verified_targets = []
  for targetinfo in directed_targets:
    target_filepath = targetinfo['filepath']
    try:
      verified_targets.append(
        secondary_ecu.get_validated_target_info(target_filepath))
    except tuf.UnknownTargetError:
      print(RED + 'Director has instructed us to download a target (' +
          target_filepath + ') that is not validated by the combination of '
          'Director + Supplier repositories. Such an unvalidated file MUST NOT'
          ' and WILL NOT be downloaded, so IT IS BEING SKIPPED. It may be that'
          ' files have changed in the last few moments on the repositories. '
          'Try again, but if this happens often, you may be connecting to an '
          'untrustworthy Director, or the Director and Supplier may be out of '
          'sync.' + ENDCOLORS)


  verified_target_filepaths = [targ['filepath'] for targ in verified_targets]

  print(GREEN + '\n')
  print('Metadata for the following Targets has been validated by both '
      'the Director and the OEM repository.\nThey will now be downloaded:')
  for vtf in verified_target_filepaths:
    print('    ' + vtf)
  print(ENDCOLORS)

  # # Insist that file2.txt is one of the verified targets.
  # assert True in [targ['filepath'] == '/file2.txt' for targ in \
  #     verified_targets], 'I do not see /file2.txt in the verified targets.' + \
  #     ' Test has changed or something is wrong. The targets are: ' + \
  #     repr(verified_targets)

  # If you execute the following, commented-out command, you'll get a not found
  # error, because while the mainrepo specifies file1.txt, the Director does not.
  # Anything the Director doesn't also list can't be validated.
  # file1_trustworthy_info = secondary.updater.target('file1.txt')

  # # Delete file2.txt if it already exists. We're about to download it.
  # if os.path.exists(os.path.join(client_directory_name, 'file2.txt')):
  #   os.remove(os.path.join(client_directory_name, 'file2.txt'))


  # For each target for which we have verified metadata:
  for target in verified_targets:

    # Make sure the resulting filename is actually in the client directory.
    # (In other words, enforce a jail.)
    full_targets_directory = os.path.abspath(os.path.join(
        client_directory_name, 'targets'))
    filepath = target['filepath']
    if filepath[0] == '/':
      filepath = filepath[1:]
    full_fname = os.path.join(full_targets_directory, filepath)
    enforce_jail(filepath, full_targets_directory)

    # Delete existing targets.
    if os.path.exists(full_fname):
      os.remove(full_fname)

    # Download each target.
    # Now that we have fileinfo for all targets listed by both the Director and
    # the Supplier (mainrepo) -- which should include file2.txt in this test --
    # we can download the target files and only keep each if it matches the
    # verified fileinfo. This call will try every mirror on every repository
    # within the appropriate delegation in pinned.json until one of them works.
    # In this case, both the Director and OEM Repo are hosting the
    # file, just for my convenience in setup. If you remove the file from the
    # Director before calling this, it will still work (assuming OEM still
    # has it). (The second argument here is just where to put the files.)
    # This should include file2.txt.
    try:
      secondary_ecu.updater.download_target(target, full_targets_directory)

    except tuf.NoWorkingMirrorError as e:
      print('')
      print(YELLOW + 'In downloading target ' + repr(filepath) + ', am unable '
          'to find a mirror providing a trustworthy file.\nChecking the mirrors'
          ' resulted in these errors:')
      for mirror in e.mirror_errors:
        print('    ' + type(e.mirror_errors[mirror]).__name__ + ' from ' + mirror)
      print(ENDCOLORS)

      # If this was our firmware, notify that we're not installing.
      if filepath.startswith('/') and filepath[1:] == firmware_filename or \
        not filepath.startswith('/') and filepath == firmware_filename:

        print()
        print(YELLOW + ' While the Director and OEM provided consistent metadata'
            ' for new firmware,')
        print(' mirrors we contacted provided only untrustworthy images. ')
        print(GREEN + 'We have rejected these. Firmware not updated.\n' + ENDCOLORS)

    else:
      assert(os.path.exists(full_fname)), 'Programming error: no download ' + \
          'error, but file still does not exist.'
      print(GREEN + 'Successfully downloaded a trustworthy ' + repr(filepath) +
          ' image.' + ENDCOLORS)

      # If this is our firmware, "install".
      if filepath.startswith('/') and filepath[1:] == firmware_filename or \
        not filepath.startswith('/') and filepath == firmware_filename:

        print()
        print(GREEN + 'Provided firmware "installed"; metadata for this new '
            'firmware is stored for reporting back to the Director.' + ENDCOLORS)
        print()
        current_firmware_fileinfo = target




  # All targets have now been downloaded.

  if not len(verified_target_filepaths):
    print(YELLOW + 'No updates are required: the Director and OEM did'
        ' not agree on any updates.' + ENDCOLORS)
    return

  # # If we get here, we've tried all filepaths in the verified targets and not
  # # found something matching our expected firmware filename.
  # print('Targets were provided by the Director and OEM and were downloaded, '
  #     'but this Secondary expects its firmware filename to be ' +
  #     repr(firmware_filename) + ' and no such file was listed.')
  return





def generate_and_send_manifest_to_director():
  
  global secondary_ecu
  global most_recent_signed_ecu_manifest
  
  # Generate and sign a manifest indicating that this ECU has a particular
  # version/hash/size of file2.txt as its firmware.
  most_recent_signed_ecu_manifest = secondary_ecu.generate_signed_ecu_manifest(
      current_firmware_fileinfo, [ecu_key])


  print('Submitting the Primary\'s manifest to the Director.')
  secondary_ecu.submit_ecu_manifest_to_director(most_recent_signed_ecu_manifest)
  print('Submission successful.')




def ATTACK_send_corrupt_manifest_to_director():
  """
  Attack: MITM w/o key modifies ECU manifest.
  Modify the ECU manifest without updating the signature.
  """
  # Copy the most recent signed ecu manifest.
  corrupt_signed_manifest = {k:v for (k,v) in most_recent_signed_ecu_manifest.items()}

  corrupt_signed_manifest['signed']['attacks_detected'] += 'Everything is great, I PROMISE!'
  #corrupt_signed_manifest['signed']['ecu_serial'] = 'ecu22222'

  print(YELLOW + 'ATTACK: Corrupted Manifest (bad signature):' + ENDCOLORS)
  print('   Modified the signed manifest as a MITM, simply changing a value:')
  print('   The attacks_detected field now reads ' + RED + '"Everything is great, I PROMISE!' + ENDCOLORS)

  import xmlrpc.client # for xmlrpc.client.Fault

  try:
    secondary_ecu.submit_ecu_manifest_to_director(corrupt_signed_manifest)
  except xmlrpc.client.Fault:
    print(GREEN + 'Director service REJECTED the fraudulent ECU manifest.' + ENDCOLORS)
  else:
    print(RED + 'Director service ACCEPTED the fraudulent ECU manifest!' + ENDCOLORS)
  # (The Director, in its window, should now indicate that it has received this
  # manifest. If signature checking for manifests is on, then the manifest is
  # rejected. Otherwise, it is simply accepted.)




def ATTACK_send_manifest_with_wrong_sig_to_director():
  """
  Attack: MITM w/o key modifies ECU manifest and signs with a different ECU's
  key.
  """
  # Discard the signatures and copy the signed contents of the most recent
  # signed ecu manifest.
  corrupt_manifest = {k:v for (k,v) in most_recent_signed_ecu_manifest['signed'].items()}

  corrupt_manifest['attacks_detected'] += 'Everything is great; PLEASE BELIEVE ME THIS TIME!'

  signable_corrupt_manifest = tuf.formats.make_signable(corrupt_manifest)
  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
      signable_corrupt_manifest)

  # Attacker loads a key she may have (perhaps some other ECU's key)
  key2_pub = rt.import_ed25519_publickey_from_file('secondary2.pub')
  key2_pri = rt.import_ed25519_privatekey_from_file('secondary2', password='pw')
  ecu2_key = uptane.common.canonical_key_from_pub_and_pri(key2_pub, key2_pri)
  keys = [ecu2_key]

  # Attacker signs the modified manifest with that other key.
  signed_corrupt_manifest = uptane.common.sign_signable(
      signable_corrupt_manifest, keys)
  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
      signed_corrupt_manifest)

  import xmlrpc.client # for xmlrpc.client.Fault

  try:
    secondary_ecu.submit_ecu_manifest_to_director(signed_corrupt_manifest)
  except xmlrpc.client.Fault as e:
    print('Director service REJECTED the fraudulent ECU manifest.')
  else:
    print('Director service ACCEPTED the fraudulent ECU manifest!')
  # (The Director, in its window, should now indicate that it has received this
  # manifest. If signature checking for manifests is on, then the manifest is
  # rejected. Otherwise, it is simply accepted.)





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
