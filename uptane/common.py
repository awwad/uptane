"""
Some common utilities for Uptane, to be assigned to more sensible locations in
the future.
"""
from __future__ import print_function
from __future__ import unicode_literals

import tuf
import tuf.formats
import json
import os
import shutil
import copy

SUPPORTED_KEY_TYPES = ['ed25519', 'rsa']

def sign_signable(signable, keys_to_sign_with):
  """
  Signs the given signable (e.g. an ECU manifest) with all the given keys.

  Arguments:

    signable:
      An object with a 'signed' dictionary and a 'signatures' list:
      conforms to tuf.formats.SIGNABLE_SCHEMA

    keys_to_sign_with:
      A list whose elements must conform to tuf.formats.ANYKEY_SCHEMA.

  Returns:

    A signable object (tuf.formats.SIGNABLE_SCHEMA), but with the signatures
    added to its 'signatures' list.

  """

  # The below was partially modeled after tuf.repository_lib.sign_metadata()

  signatures = []

  for signing_key in keys_to_sign_with:

    tuf.formats.ANYKEY_SCHEMA.check_match(signing_key)

    # If we already have a signature with this keyid, skip.
    if signing_key['keyid'] in [key['keyid'] for key in signatures]:
      print('Already signed with this key.')
      continue

    # If the given key was public, raise a FormatError.
    if 'private' not in signing_key['keyval']:
      raise tuf.FormatError('One of the given keys lacks a private key value, '
          'and so cannot be used for signing: ' + repr(signing_key))

    # We should already be guaranteed to have a supported key type due to
    # the ANYKEY_SCHEMA.check_match call above. Defensive programming.
    if signing_key['keytype'] not in SUPPORTED_KEY_TYPES:
      assert False, 'Programming error: key types have already been ' + \
          'validated; should not be possible that we now have an ' + \
          'unsupported key type, but we do: ' + repr(signing_key['keytype'])


    # Else, all is well. Sign the signable with the given key, adding that
    # signature to the signatures list in the signable.
    signable['signatures'].append(
        tuf.keys.create_signature(signing_key, signable['signed']))


  # Confirm that the formats match what is expected post-signing, including a
  # check again for SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA. Raise
  # 'tuf.FormatError' if the format is wrong.

  # TODO: <~> Make the function call below useful. The problem is that it
  # demancs a _type field in the 'signed' sub-object, but we don't guarantee
  # that will be there here. (TUF signs roles. This isn't a role.))
  #tuf.formats.check_signable_object_format(signable)

  return signable # Fully signed





def canonical_key_from_pub_and_pri(key_pub, key_pri):
  """
  Turn this into a canonical key matching tuf.formats.ANYKEY_SCHEMA, with
  the optional element keyid_hash_algorithms, which can be found in the
  public key, and containing both public and private key values.

  It is assumed that the following elements of each of the two arguments is a
  string:
    key['keytype']
    key['keyid']
    key['keyval']['public']
    key['keyval']['private']  (for key_pri)
  """
  key = {
      'keytype': key_pub['keytype'],
      'keyid': key_pub['keyid'],
      'keyval': {
        'public': key_pub['keyval']['public'],
        'private': key_pri['keyval']['private']},
      'keyid_hash_algorithms': copy.deepcopy(key_pub['keyid_hash_algorithms'])}
  tuf.formats.ANYKEY_SCHEMA.check_match(key)

  return key





def public_key_from_canonical(key_canonical):
  """
  Given a key that includes all public and private key information, return a
  public key (assumed to be the canonical key with the 'private' component
  of the 'keyval' dictionary stripped).
  """
  tuf.formats.ANYKEY_SCHEMA.check_match(key_canonical)

  key_public = copy.deepcopy(key_canonical)

  del key_public['keyval']['private']

  return key_public





# Not sure where to put this yet.
def create_directory_structure_for_client(
    client_dir,
    pinning_fname,
    root_fnames_by_repository):
  """

  Creates a directory structure for a client, including current and previous
  metadata directories.

  Arguments:
    client_dir
      the client directory, into which metadata and targets will be downloaded
      from repositories

    pinning_fname
      the filename of a pinned.json file to copy and use to map targets to
      repositories

    root_fnames_by_repository
      a dictionary mapping repository name to the filename of the root.json
      file for that repository to start with as the root of trust for that
      repository.
      e.g.
        {'supplier': 'distributed_roots/mainrepo_root.json',
         'director': 'distributed_roots/director_root.json'}
      Each repository listed in the pinning.json file should have a
      corresponding entry in this dict.

  """

  # Read the pinning file here and create a list of repositories and
  # directories.

  # Set up the TUF client directories for each repository.
  if os.path.exists(client_dir):
    shutil.rmtree(client_dir)
  os.makedirs(os.path.join(client_dir, 'metadata'))

  # Add a pinned.json to this client (softlink it from the indicated copy).
  os.symlink(
      pinning_fname, #os.path.join(WORKING_DIR, 'pinned.json'),
      os.path.join(client_dir, 'metadata', 'pinned.json'))

  pinnings = json.load(open(pinning_fname, 'r'))

  for repo_name in pinnings['repositories']:
    os.makedirs(os.path.join(client_dir, 'metadata', repo_name, 'current'))
    os.makedirs(os.path.join(client_dir, 'metadata', repo_name, 'previous'))

    # Set the root of trust we have for that repository.
    shutil.copyfile(
      root_fnames_by_repository[repo_name],
      os.path.join(client_dir, 'metadata', repo_name, 'current', 'root.json'))


  # Configure tuf with the client's metadata directories (where it stores the
  # metadata it has collected from each repository, in subdirectories).
  tuf.conf.repository_directory = client_dir # TODO for TUF: This setting should probably be called client_directory instead, post-TAP4.




def scrub_filename(fname, expected_containing_dir):
  """
  DO NOT ASSUME THAT THIS TEMPORARY FUNCTION IS SECURE.

  Performs basic scrubbing to try to ensure that the filename provided is
  actually just a plain filename (no pathing), so that it cannot specify a file
  that is not in the provided directory.

  May break (exception trigger-happy) if there's a softlink somewhere in the
  working directory path.

  Returns an absolute path that was confirmed to be inside
  expected_containing_dir.
  """
  # Assert no tricksy characters. (Improvised, not to be trusted)
  assert '..' not in fname and '/' not in fname and '$' not in fname and \
      '~' not in fname and b'\\' not in fname.encode('unicode-escape'), \
      'Unacceptable string: ' + fname

  # Make sure it's in the expected directory.
  abs_fname = os.path.abspath(os.path.join(expected_containing_dir, fname))
  if not abs_fname.startswith(os.path.abspath(expected_containing_dir)):
    raise ValueError('Expected a plain filename. Was given one that had '
        'pathing specified that put it in a different, unexpected directory. '
        'Filename was: ' + fname)

  return abs_fname
