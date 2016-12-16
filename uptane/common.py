"""
Some common utilities for Uptane, to be assigned to more sensible locations in
the future.
"""
import tuf
import tuf.formats

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
  Turn this into a canonical key matching tuf.formats.ANYKEY_SCHEMA
  Note: it looks like the resulting object is the same as the private key
  anyway, at least with ed25519. Is it always?

  TODO: <~> Find out if this is necessary. If not, instead, replace calls to
  this with use of private key, but don't forget to STILL call check_match.
  """
  key = {
      'keytype': key_pub['keytype'],
      'keyid': key_pub['keyid'],
      'keyval': {
        'public': key_pub['keyval']['public'],
        'private': key_pri['keyval']['private']}}
  tuf.formats.ANYKEY_SCHEMA.check_match(key)

  return key





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
