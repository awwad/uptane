"""
Some common utilities for Uptane, to be assigned to more sensible locations in
the future.
"""
from __future__ import print_function
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.
import tuf
import tuf.formats
import json
import os
import shutil
import copy
import hashlib

# TODO: This import is not ideal at this level. Common should probably not
# import anything from other Uptane modules. Consider putting the
# signature-related functions into a new module (sig or something) that
# imports asn1_codec.
import uptane.encoding.asn1_codec as asn1_codec
import uptane.formats

# Both key types below are supported, but issues may be encountered with RSA
# if tuf.conf.METADATA_FORMAT is 'der' (rather than 'json').
# TODO: Ensure RSA support in ASN.1/DER conversion.
SUPPORTED_KEY_TYPES = ['ed25519', 'rsa']

def sign_signable(
  signable, keys_to_sign_with, datatype,
  metadata_format=tuf.conf.METADATA_FORMAT):
  """
  <Purpose>
    Signs the given signable (e.g. an ECU manifest) with all the given keys.

    Wraps sign_over_metadata such that multiple signatures can be generated,
    and places them all in the 'signatures' field of the given signable.

    Also does some additional argument validation.


  <Arguments>

    signable:
      An object with a 'signed' dictionary and a 'signatures' list:
      conforms to tuf.formats.SIGNABLE_SCHEMA

    keys_to_sign_with:
      A list whose elements must conform to tuf.formats.ANYKEY_SCHEMA.

    datatype:
      The type of data signable['signed'] represents.
      Must be in uptane.encoding.asn1_codec.SUPPORTED_ASN1_METADATA_MODULES.
      Specifies the type of data provided in der_data, whether a Time
      Attestation, ECU Manifest, or Vehicle Manifest.

      'datatype' is used to determine the module to use for the conversion to
      ASN.1/DER, if the metadata format is 'der'. When 'der' is the metadata
      format, we need to convert to ASN.1/DER first, and conversion to
      ASN.1/DER varies by type. 'datatype' doesn't matter if signing is
      occuring over JSON.

      If the metadata contained a metadata type indicator (the way that
      DER TUF metadata does), and if we could also capture this in an ASN.1
      specification that flexibly supports each possible metadata type (the
      way that the Metadata specification does in TUF ASN.1), then this would
      not be necessary....
      # TODO: Try to find some way to add the type to the metadata and cover
      # these requirements above.

    metadata_format: (optional; default tuf.conf.METADATA_FORMAT)
      'json' or 'der'. Determines what the signature will be over.
      Should generally be left to the default except when testing different
      encodings or otherwise intentionally signing a different format.


  <Exceptions>
    tuf.FormatError if the provided key is not the correct format or lacks a
    private element.

    uptane.Error if the key type is not in the SUPPORTED_KEY_TYPES for Uptane.

  <Side Effects>
    Adds a signature to the provided signable.

  <Returns>
    None. Note that the provided object, 'signable', is modified in place.


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
      raise uptane.Error(
          'Unsupported key type: ' + repr(signing_key['keytype']))

    # Else, all is well. Sign the signable with the given key, adding that
    # signature to the signatures list in the signable.
    signable['signatures'].append(sign_over_metadata(
        signing_key, signable['signed'], datatype=datatype,
        metadata_format=metadata_format))

  uptane.formats.ANY_SIGNABLE_UPTANE_METADATA_SCHEMA.check_match(signable)





def sign_over_metadata(
    key_dict, data, datatype, metadata_format=tuf.conf.METADATA_FORMAT):
  """
  <Purpose>
    Given a key and data, returns a signature over that data.

    Higher level function that wraps tuf.keys.create_signature, and works
    specifically with Time Attestations, ECU Manifsts, and Vehicle Manifests
    that will be in JSON or ASN.1/DER format.

    Almost exactly identical to the function simultaneously added to TUF,
    tuf.sig.sign_over_metadata(). Requires datatype, and operates on
    Uptane-specific metadata (see 'datatype' argument below)

    Must differ in Uptane simply because it is not possible to convert
    Uptane-specific metadata (Time Attestations, ECU Manifests, and Vehicle
    Manifests) to or from ASN.1/DER without knowing which of those three
    types of metadata you're dealign with, and this conversion is required for
    signing and verifying signatures.

    See tuf.keys.create_signature for lower level details.

  <Arguments>
    key_dict:
      A dictionary containing the TUF keys.  An example RSA key dict has the
      form:

      {'keytype': 'rsa',
       'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
       'keyval': {'public': '-----BEGIN RSA PUBLIC KEY----- ...',
                  'private': '-----BEGIN RSA PRIVATE KEY----- ...'}}

      The public and private keys are strings in PEM format.

    data:
      Data object used by create_signature() to generate the signature.
      Acceptable format depends somewhat on tuf.conf.METADATA_FORMAT, or, if
      the optional argument is provided, metadata_format.

      This will be converted into a bytes object and passed down to
      tuf.keys.create_signature().

      In 'der' mode:
        'data' is expected to be a dictionary compliant with
        uptane.formats.ANY_SIGNABLE_UPTANE_METADATA_SCHEMA. ASN.1/DER
        conversion requires strictly defined formats.

      In 'json' mode:
        'data' can be any data that can be processed by
        tuf.formats.encode_canonical(data) can be signed. This function is
        generally intended to sign metadata (tuf.formats.ANYROLE_SCHEMA), but
        can be used more broadly.

    datatype:
      The type of data signable['signed'] represents.
      Must be in uptane.encoding.asn1_codec.SUPPORTED_ASN1_METADATA_MODULES.
      Specifies the type of data provided in der_data, whether a Time
      Attestation, ECU Manifest, or Vehicle Manifest.

      'datatype' is used to determine the module to use for the conversion to
      ASN.1/DER, if the metadata format is 'der'. When 'der' is the metadata
      format, we need to convert to ASN.1/DER first, and conversion to
      ASN.1/DER varies by type. 'datatype' doesn't matter if signing is
      occuring over JSON.

      If the metadata contained a metadata type indicator (the way that
      DER TUF metadata does), and if we could also capture this in an ASN.1
      specification that flexibly supports each possible metadata type (the
      way that the Metadata specification does in TUF ASN.1), then this would
      not be necessary....
      # TODO: Try to find some way to add the type to the metadata and cover
      # these requirements above.

    metadata_format: (optional; default based on tuf.conf.METADATA_FORMAT)

      If 'json', treats data as a JSON-friendly Python dictionary to be turned
      into a canonical JSON string and then encoded as utf-8 before signing.
      When operating TUF with DER metadata but checking the signature on some
      piece of JSON for some reason, this should be manually set to 'json'. The
      purpose of this canonicalization is to produce repeatable signatures
      across different platforms and Python key dictionaries (avoiding things
      like different signatures over the same dictionary).

      If 'der', the data will be converted into ASN.1, encoded as DER,
      and hashed. The signature is then checked against that hash.

  <Exceptions>
    tuf.FormatError, if 'key_dict' is improperly formatted.

    tuf.UnsupportedLibraryError, if an unsupported or unavailable library is
    detected.

    TypeError, if 'key_dict' contains an invalid keytype.

  <Side Effects>
    The cryptography library specified in 'tuf.conf' is called to do the actual
    verification. When in 'der' mode, argument data is converted into ASN.1/DER
    in order to verify it. (Argument object is unchanged.)

  <Returns>
    A signature dictionary conformant to 'tuf.format.SIGNATURE_SCHEMA'. e.g.:
    {'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
     'method': '...',
     'sig': '...'}.

  """

  tuf.formats.ANYKEY_SCHEMA.check_match(key_dict)
  # TODO: Check format of data, based on metadata_format.
  # TODO: Consider checking metadata_format redundantly. It's checked below.

  if metadata_format == 'json':
    data = tuf.formats.encode_canonical(data).encode('utf-8')

  elif metadata_format == 'der':

    # TODO: Have convert_signed_metadata_to_der take just the 'signed' element
    # so we don't have to do this silly wrapping in an empty signable.
    data = asn1_codec.convert_signed_metadata_to_der(
        {'signed': data, 'signatures': []}, only_signed=True, datatype=datatype)
    data = hashlib.sha256(data).digest()

  else:
    raise tuf.Error('Unsupported metadata format: ' + repr(metadata_format))


  return tuf.keys.create_signature(key_dict, data)





def verify_signature_over_metadata(
    key_dict, signature, data, datatype,
    metadata_format=tuf.conf.METADATA_FORMAT):
  """
  <Purpose>
    Determine whether the private key belonging to 'key_dict' produced
    'signature'. tuf.keys.verify_signature() will use the public key found in
    'key_dict', the 'method' and 'sig' objects contained in 'signature',
    and 'data' to complete the verification.

    Higher level function that wraps tuf.keys.verify_signature, and works
    specifically with Time Attestations, ECU Manifsts, and Vehicle Manifests
    that will be in JSON or ASN.1/DER format.

    Almost exactly identical to the function simultaneously added to TUF,
    tuf.sig.verify_signature_over_metadata(). Requires datatype.
    Must differ in Uptane simply because it is not possible to convert
    Uptane-specific metadata (Time Attestations, ECU Manifests, and Vehicle
    Manifests) to or from ASN.1/DER without knowing which of those three
    types of metadata you're dealign with, and this conversion is required for
    signing and verifying signatures.

    See tuf.keys.verify_signature for lower level details.

  <Arguments>
    key_dict:
      A dictionary containing the TUF keys and other identifying information.
      If 'key_dict' is an RSA key, it has the form:

      {'keytype': 'rsa',
       'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
       'keyval': {'public': '-----BEGIN RSA PUBLIC KEY----- ...',
                  'private': '-----BEGIN RSA PRIVATE KEY----- ...'}}

      The public and private keys are strings in PEM format.

    signature:
      The signature dictionary produced by one of the key generation functions.
      'signature' has the form:

      {'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
       'method': 'method',
       'sig': sig}.

      Conformant to 'tuf.formats.SIGNATURE_SCHEMA'.

    data:
      Data object over which the validity of the provided signature will be
      checked by verify_signature().

      Acceptable format depends somewhat on tuf.conf.METADATA_FORMAT, or, if
      the optional argument is provided, metadata_format.

      This will be converted into a bytes object and passed down to
      tuf.keys.verify_signature().

      In 'der' mode:
        'data' is expected to be a dictionary compliant with
        uptane.formats.ANY_SIGNABLE_UPTANE_METADATA_SCHEMA. ASN.1/DER
        conversion requires strictly defined formats.

      In 'json' mode:
        'data' can be any data that can be processed by
        tuf.formats.encode_canonical(data). This function is generally intended
        to verify signatures over Uptane metadata
        (uptane.formats.ANY_SIGNABLE_UPTANE_METADATA_SCHEMA), but can be used
        more broadly when in 'json' mode.

    metadata_format: (optional; default based on tuf.conf.METADATA_FORMAT)

      If 'json', treats data as a JSON-friendly Python dictionary to be turned
      into a canonical JSON string and then encoded as utf-8 before checking
      against the signature. When operating TUF with DER metadata but checking
      the signature on some piece of JSON for some reason, this should be
      manually set to 'json'. The purpose of this canonicalization is to
      produce repeatable signatures across different platforms and Python key
      dictionaries (avoiding things like different signatures over the same
      dictionary).

      If 'der', the data will be converted into ASN.1, encoded as DER,
      and hashed. The signature is then checked against that hash.

  <Exceptions>
    tuf.FormatError, raised if either 'key_dict' or 'signature' are improperly
    formatted.

    tuf.UnsupportedLibraryError, if an unsupported or unavailable library is
    detected.

    tuf.UnknownMethodError.  Raised if the signing method used by
    'signature' is not one supported.

  <Side Effects>
    The cryptography library specified in 'tuf.conf' is called to do the actual
    verification. When in 'der' mode, argument data is converted into ASN.1/DER
    in order to verify it. (Argument object is unchanged.)

  <Returns>
    Boolean.  True if the signature is valid, False otherwise.
  """

  tuf.formats.ANYKEY_SCHEMA.check_match(key_dict)
  tuf.formats.SIGNATURE_SCHEMA.check_match(signature)
  # TODO: Check format of data, based on metadata_format.
  # TODO: Consider checking metadata_format redundantly. It's checked below.

  if metadata_format == 'json':
    data = tuf.formats.encode_canonical(data).encode('utf-8')

  elif metadata_format == 'der':

    # TODO: Have convert_signed_metadata_to_der take just the 'signed' element
    # so we don't have to do this silly wrapping in an empty signable.
    data = asn1_codec.convert_signed_metadata_to_der(
        {'signed': data, 'signatures': []}, only_signed=True, datatype=datatype)
    data = hashlib.sha256(data).digest()

  else:
    raise tuf.Error('Unsupported metadata format: ' + repr(metadata_format))


  return tuf.keys.verify_signature(key_dict, signature, data)






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
        {'ImageRepo': 'distributed_roots/imagerepo_root.json',
         'Director': 'distributed_roots/director_root.json'}
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

  with open(pinning_fname) as fobj:
    pinnings = json.load(fobj)

  for repo_name in pinnings['repositories']:
    os.makedirs(os.path.join(client_dir, 'metadata', repo_name, 'current'))
    os.makedirs(os.path.join(client_dir, 'metadata', repo_name, 'previous'))

    # Set the root of trust we have for that repository.
    shutil.copyfile(
      root_fnames_by_repository[repo_name],
      os.path.join(client_dir, 'metadata', repo_name, 'current',
          'root.' + tuf.conf.METADATA_FORMAT))


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
