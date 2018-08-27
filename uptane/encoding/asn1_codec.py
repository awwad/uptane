"""
<Program Name>
  uptane/encoding/asn1_codec.py

<Purpose>
  Provides functions to allow use of ASN.1/DER-encoded metadata specific to
  Uptane.

  Note that TUF has its own module, tuf/encoding/asn1_codec.py, that performs
  translation from and to ASN.1/DER-encoded metadata that is specific to TUF.

  # TODO: NOTE ALSO THAT MUCH OF THIS CODE IS COPIED FROM
  tuf/encoding/asn1_codec.py. These two files should be refactored to eliminate
  duplicated code!

"""
from __future__ import print_function
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.
import tuf
import tuf.conf
import tuf.formats
import uptane.formats
import logging
import hashlib

logger = logging.getLogger('uptane.asn1_codec')

DATATYPE_TIME_ATTESTATION = 'type__time_attestation'
DATATYPE_ECU_MANIFEST = 'type__ecu_manifest'
DATATYPE_VEHICLE_MANIFEST = 'type__vehicle_manifest'

try:
  # pyasn1 modules
  import pyasn1.codec.der.encoder as p_der_encoder
  import pyasn1.codec.der.decoder as p_der_decoder
  import pyasn1.error

  # ASN.1 data specification modules that convert ASN.1 to JSON and back.
  import uptane.encoding.timeserver_asn1_coder as timeserver_asn1_coder
  import uptane.encoding.ecu_manifest_asn1_coder as ecu_manifest_asn1_coder
  import uptane.encoding.vehicle_manifest_asn1_coder as vehicle_manifest_asn1_coder
  import uptane.encoding.asn1_definitions as asn1_spec

  # This maps metadata type to the module that lays out the
  # ASN.1 format for that type.
  SUPPORTED_ASN1_METADATA_MODULES = {
      DATATYPE_TIME_ATTESTATION: timeserver_asn1_coder,
      DATATYPE_ECU_MANIFEST: ecu_manifest_asn1_coder,
      DATATYPE_VEHICLE_MANIFEST: vehicle_manifest_asn1_coder}


# This warning is provided in order to be helpful; behavior is not prescribed
# when a dependency is missing, so this clause is not tested (which would
# entail tests running after a separate installation with missing
# dependencies), so this clause is not included in coverage metrics.
except ImportError: # pragma: no cover
  logger.warning('Minor: pyasn1 library not found. Proceeding using JSON only.')
  PYASN1_EXISTS = False

else:
  PYASN1_EXISTS = True





def ensure_valid_metadata_type_for_asn1(metadata_type):
  if metadata_type not in SUPPORTED_ASN1_METADATA_MODULES:
    # TODO: Choose/make better exception class.
    raise uptane.Error('This is not one of the metadata types configured for '
        'translation from JSON to DER-encoded ASN1. Type of given metadata: ' +
        repr(metadata_type) + '; types accepted: ' +
        repr(list(SUPPORTED_ASN1_METADATA_MODULES)))





def convert_signed_der_to_dersigned_json(der_data, datatype):
  """
  Convert the given der_data to a Python dictionary representation consistent
  with Uptane's typical JSON encoding.

  The 'signed' portion will be a JSON-compatible Python dict translation
  of der_data's 'signed' portion. Likewise for the 'signatures'
  portion. The result will be a dict containing a 'signatures' section that has
  signatures over not what is in the 'signed' section, but rather over a
  different format and encoding of what is in the 'signed' section. Please take
  care.

  <Arguments>
    der_data:
      # TODO: FILL IN

    datatype:
      String chosen from SUPPORTED_ASN1_METADATA_MODULES.
      Specifies the type of data provided in der_data, whether a Time
      Attestation, ECU Manifest, or Vehicle Manifest. This is used to determine
      the module to use for the conversion.

      If the metadata contained a metadata type indicator (the way that
      DER TUF metadata does), and if we could also capture this in an ASN.1
      specification that flexibly supports each possible metadata type (the
      way that the Metadata specification does in TUF ASN.1), then this would
      not be necessary....
      # TODO: Try to find some way to add the type to the metadata and cover
      # these requirements above.

  <Returns>
    A JSON-compatible Python dictionary representing the data from der_data,
    including signatures that are still over the DER data.

  <Exceptions>
    tuf.FormatError
      If der_data does not seem to be valid DER data (regardless of the type).

    uptane.Error
      If datatype is not a data type that Uptane supports converting into
      ASN.1/DER.

    uptane.ASN1DERDecodingError
      If der_data cannot be decoded as the given datatype (if pyasn1 raises an
      error in the decode process).
  """

  if not PYASN1_EXISTS:
    # This error message is provided in order to be helpful; behavior is not
    # prescribed when a dependency is missing, so this clause is not tested
    # (which would entail tests running after a separate installation with
    # missing dependencies), so this clause is not included in coverage
    # metrics.
    raise uptane.Error( # pragma: no cover
        'Request was made to load a DER file, but the required '
        'pyasn1 library failed to import.')

  uptane.formats.DER_DATA_SCHEMA.check_match(der_data)

  # Make sure it's a supported type of metadata for ASN.1 to Python dict
  # translation. (Throw an exception if not.)
  ensure_valid_metadata_type_for_asn1(datatype)


  # "_signed" here refers to the portion of the metadata that will be signed.
  # The metadata is divided into "signed" and "signature" portions. The
  # signatures are signatures over the "signed" portion. "json_signed" below
  # is actually not signed - it is simply the portion that will be put into
  # the "signed" section - the portion to be signed. The nomenclature is
  # unfortunate....
  # Note that decode() returns a tuple: (pyasn1_object, remaining_input)
  # We don't expect any remaining input (TODO: Consider testing it?) and
  # are only interested in the pyasn1 object decoded from the DER.

  # TODO: Determine type of metadata here first, so that you can choose the
  # correct class from asn1_spec.
  # This object will be used by the decoder for its structure, to determine
  # how to decode the DER object.
  # I can't seem to figure out why I need to do this this way.
  # Why can't I just use Metadata() by adding TokensAndTimestamp as an optional
  # component of SignedBody()? Anyway, this seems to work.......
  # Handle for the corresponding module.
  relevant_asn_module = SUPPORTED_ASN1_METADATA_MODULES[datatype]
  if datatype == DATATYPE_TIME_ATTESTATION:
    exemplar_object = asn1_spec.TokensAndTimestampSignable()
  elif datatype == DATATYPE_ECU_MANIFEST:
    exemplar_object = asn1_spec.ECUVersionManifest()
  elif datatype == DATATYPE_VEHICLE_MANIFEST:
    exemplar_object = asn1_spec.VehicleVersionManifest()

  # TODO: Determine if there are any other error types to add to the except
  # clause below to cover whatever errors we expect pyasn1 to raise when trying
  # to convert data. That error class covers ValueConstraintError and
  # SubstrateUnderrunError, but I'm not sure if pyasn1 wouldn't raise other
  # errors....
  try:
    asn_metadata = p_der_decoder.decode(der_data, asn1Spec=exemplar_object)[0]
  except pyasn1.error.PyAsn1Error as e:
    raise uptane.FailedToDecodeASN1DER('Unable to decode the provided '
        'der_data as datatype ' + repr(datatype) + '. The pyasn1-raised error '
        'follows: ' + repr(e))

  # asn_metadata here now has three components, indexed by integer 0, 1, 2.
  # 0 is the signed component (Signed())
  # 1 i the numberOfSignatures component (Length())
  # 2 is the signatures component (Signatures())

  asn_signed_metadata = asn_metadata[0]

  # TODO: The 'signed' component here should probably already be DER, since
  # that is what the signature is over. Because this would entail some changes
  # changes to the ASN.1 data specifications in metadataverificationmodule.py,
  # I'm not doing this yet (though I expect to).
  # So, for the time being, if we wanted to check the signature, we'd have to
  # encode this thing into DER again.
  # der_signed_metadata = p_der_encoder.encode(asn_signed)


  # Now we have to figure out what type of metadata the ASN.1 metadata is
  # so that we can use the appropriate spec to convert it back to JSON.

  # # (Even though this takes asn_metadata, it only uses asn_metadata[0],
  # # asn_signed_metadata....)
  # asn_type_data = asn_signed_metadata[0] # This is the RoleType info, a class.

  # # This is how we'd extract the name of the type from the enumeration that is
  # # in the class (namedValues), indexed by the underlying "value" of
  # # asn_type_data.
  # # We call lower() on it because I don't care about the casing, which has
  # # varied somewhat in TUF history, and I don't want casing to ruin this
  # # detection.
  # metadata_type = asn_type_data.namedValues[asn_type_data._value][0].lower()


  # Convert into the basic Python dict we use in the JSON encoding.
  json_signed = relevant_asn_module.get_json_signed(asn_metadata)

  # Extract the signatures from the ASN.1 representation.
  asn_signatures = asn_metadata[2]
  json_signatures = convert_signatures_to_json(asn_signatures)

  return {'signatures': json_signatures, 'signed': json_signed}





def convert_signed_metadata_to_der(signed_metadata, datatype,
    private_key=None, resign=False, only_signed=False):
  """
  Normal behavior ("resign" (re-sign) parameter being False) converts the
  basic Python dictionary format of signed_metadata provided into ASN.1 and
  encodes it as DER, returning the resulting DER encoding of the given metadata.

  "_signed" here refers to the portion of the metadata that will be signed.
  The metadata is divided into "signed" and "signature" portions. The
  signatures are signatures over the "signed" portion. "json_signed" below
  is actually not signed - it is simply the portion that will be put into
  the "signed" section - the portion to be signed. The nomenclature is
  unfortunate....
  TODO: Better variable and function naming.

  <Arguments>
    signed_metadata
      Metadata (time attestation or ecu manifest, for example), and signature(s)
      over it.
      A dictionary with keys 'signed' and 'signatures'.
      signed_metadata must conform to one of the following:
          SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA
          SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA
          SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA

      Each of the above also conforms to tuf.formats.SIGNABLE_SCHEMA.

    datatype:
      String chosen from SUPPORTED_ASN1_METADATA_MODULES.
      Specifies the type of data provided in der_data, whether a Time
      Attestation, ECU Manifest, or Vehicle Manifest. This is used to determine
      the module to use for the conversion.

    resign
      ("re-sign"). Normally False, resulting in the signatures in
      signed_metadata being formatted as ASN.1 and encoded as DER, but otherwise
      preserved (for example, they may still be signatures over JSON - the
      signature values themselves are unchanged).
      If resign is instead True, any signatures provided are
      discarded, and a new signature is generated. This new signature will be
      over the DER encoding of the data provided in signed_metadata['signed'].
      In other words, 'signed' will first be converted into ASN.1 and then
      encoded as DER, and a signature will be made using the given private_key,
      over that DER encoding.
      If the given signatures are already over DER encoding before reaching
      this point (as may happen in the current design), then you will not
      need this to be True.
      NOTE that if given a vehicle manifest and told to re-sign, this function
      will only re-sign the vehicle manifest itself - it will not try to re-sign
      every ECU Manifest contained in it. (Those would presumably be signed
      by other keys.)

    private_key
      This should be left out (None) unless resign is True, in which case
      private_key must conform to tuf.formats.ANYKEY_SCHEMA, containing a
      private key, specifically. It will be used to re-sign the metadata
      provided in signed_metadata['signed'].
      Such a key can be imported, for example, through the
      tuf.repository_tool.import_*_private_key() functions.

    only_signed
      Default False. If this is set to True, instead of returning the DER
      encoding of the full {'signed': {"abc..."}, 'signatures': [{"xyz..."}]}
      object, the DER encoding of only the 'signed' entry will be returned
      {"abc..."}.

  <Returns>
    By default (only_signed=False, resign=False), the returned value is the DER
    encoding of the full signed_metadata dictionary.

    If only_signed is True, the returned value is the DER encoding of only the
    'signed' entry in the signed_metadata dictionary.

    Otherwise, if resign is True, the returned value is the DER encoding of the
    full signed_metadata dictionary, but with the 'signatures' entry
    discarded and rebuilt anew with a new signature over the DER ENCODING of the
    'signed' entry in the signed_metadata dictionary.

  """
  # Make sure that if and only if the re-sign ('resign') parameter is True, a
  # private_key has been provided.
  tuf.formats.BOOLEAN_SCHEMA.check_match(resign)
  if resign != (private_key is not None):
    raise uptane.Error('Inconsistent arguments: a private key should be '
        'provided to convert_signed_json_to_signed_der if and only if the '
        'resign argument is True.')

  if only_signed and resign:
    raise uptane.Error('Inconsistent arguments: request to re-sign metadata '
        'in a new encoding and then throw those same new signatures away.')


  if private_key is not None:
    tuf.formats.ANYKEY_SCHEMA.check_match(private_key)
    # TODO: Note that this does not confirm that it is specifically a private key.
    # Consider checking that. (Best way is to have an additional SCHEMA in
    # tuf.formats and use that.)

  tuf.formats.SIGNABLE_SCHEMA.check_match(signed_metadata)
  uptane.formats.ANY_SIGNABLE_UPTANE_METADATA_SCHEMA.check_match(
      signed_metadata)

  json_signed = signed_metadata['signed']

  # # Force lowercase for metadata type because some TUF versions have been
  # # inconsistent in the casing of metadata types ('targets' vs 'Targets').
  # metadata_type = json_signed['_type'].lower()

  # Ensure that the type is one of the supported metadata types, for which
  # a module exists that translates it to and from an ASN.1 format.
  ensure_valid_metadata_type_for_asn1(datatype)

  # Handle for the corresponding module.
  relevant_asn_module = SUPPORTED_ASN1_METADATA_MODULES[datatype]

  asn_signed = relevant_asn_module.get_asn_signed(json_signed)

  if only_signed:
    # If the caller doesn't want any signatures included in the returned
    # DER object, then we need go no further and may encode what we already
    # have, which is the 'signed' component, the core metadata itself.
    der_signed = p_der_encoder.encode(asn_signed)
    return der_signed

  # Otherwise, we're to produce the full signable object (signed + signatures).
  # Either we will be retaining existing signatures or re-signing.


  if resign:

    # Encode the ASN.1 as DER first using pyasn1.
    # TODO: Determine if there are any other error types to add to the except
    # clause below to cover whatever errors we expect pyasn1 to raise when
    # trying to encode data. That error class covers ValueConstraintError and
    # SubstrateUnderrunError, but I'm not sure if pyasn1 wouldn't raise other
    # errors....
    try:
      der_signed = p_der_encoder.encode(asn_signed)
    except pyasn1.error.PyAsn1Error as e:
      raise uptane.FailedToEncodeASN1DER('Unable to encode the provided '
          'der_data as datatype ' + repr(datatype) + '. The pyasn1-raised '
          'error follows: ' + repr(e))


    # This hashing is redundant and temporary. Eventually, the hash will
    # consistently be performed in securesystemslib/keys.py in the
    # create_signature() function, so we shouldn't be taking a hash here.
    # For the time being, I do this so that it always uses a hash even for ed25519
    # and also so that the canonicalization that is currently called by
    # create_signature() doesn't choke on the DER I want to sign.
    hash_of_der = hashlib.sha256(der_signed).digest()

    # Now sign the metadata. (This signs a cryptographic hash of the metadata.)
    # The returned value is a basic Python dict writable into JSON.
    # This is a signature over the hash of the DER encoding.
    # Tell keys.create_signature that the data we're providing is not JSON so
    # that it doesn't try to canonicalize it (and wrap the hash in double
    # quotes).
    pydict_signatures = [tuf.keys.create_signature(private_key, hash_of_der)]

  else:
    pydict_signatures = signed_metadata['signatures']

  asn_signatures_list = convert_signatures_to_asn(pydict_signatures)


  # Now construct an ASN.1 representation of the signed/signatures-encapsulated
  # metadata, populating it.
  if datatype == DATATYPE_TIME_ATTESTATION:
    metadata = asn1_spec.TokensAndTimestampSignable()
  elif datatype == DATATYPE_ECU_MANIFEST:
    metadata = asn1_spec.ECUVersionManifest()
  elif datatype == DATATYPE_VEHICLE_MANIFEST:
    metadata = asn1_spec.VehicleVersionManifest()
  metadata['signed'] = asn_signed #considering using der_signed instead - requires changes
  metadata['signatures'] = asn_signatures_list # TODO: Support multiple sigs, or integrate with TUF.
  metadata['numberOfSignatures'] = len(asn_signatures_list)

  # Encode our new (py)ASN.1 object as DER (Distinguished Encoding Rules).
  return p_der_encoder.encode(metadata)





def convert_signatures_to_json(asn_signatures):
  """
  Given an object compliant with uptane.encoding.asn1_definitions.Signatures()
  representing a list of signatures in ASN.1 (pyasn1), convert it to the
  more familiar TUF and Uptane compliant tuf.formats.SIGNATURES_SCHEMA.

  The data contained (the signature values, keyids, and method) are not changed.

  This is the exact reverse of convert_signatures_to_asn(); providing the
  output of this function as input to that function should reproduce the initial
  input to this function. Also vice versa.
  """
  json_signatures = []

  for asn_signature in asn_signatures:
    json_signatures.append({
        # Next lines are not ideal: prettyPrint and having to manually skip the
        # first two characters (which we expect to be '0x' indicating a hex
        # string). See if there's a better method of converting from the
        # octetString to what TUF expects.
        'keyid': asn_signature['keyid'].prettyPrint()[2:],
        # TODO: See if it's possible to tweak the definition of 'method' so that str(method) returns what we want rather here than the enum, so that we don't have to do make this weird enum translation call?
        'method': asn_signature['method'].namedValues[asn_signature['method']._value],
        'sig': asn_signature['value'].prettyPrint()[2:]})


  return json_signatures





def convert_signatures_to_asn(pydict_signatures):
  """
  Given a Python dictionary compliant with tuf.formats.SIGNATURES_SCHEMA,
  containing signatures, convert it to an ASN.1 (pyasn1) representation
  that conforms to the uptane.encoding.asn1_definitions.Signatures() class.

  The data contained (the signature values, keyids, and method) are not changed.

  This is the exact reverse of convert_signatures_to_json(); providing the
  output of this function as input to that function should reproduce the initial
  input to this function. Also vice versa.
  """

  # Create a pyASN.1 object of custom class Signatures
  asn_signatures_list = asn1_spec.Signatures()

  # Now convert each Python dictionary-style signature into an ASN.1 signature
  # and stick those into the ASN.1 list just created.
  # Note that a Signatures() object has no append() method, so we clumsily
  # iterate through with index 'i'.
  i = 0 # Index for iterating through asn
  for pydict_sig in pydict_signatures:

    # Construct an ASN.1 representation of the signature and populate it.
    asn_sig = asn1_spec.Signature()

    # This constructs a Keyid() object and assigns it the
    # value from pydict_sig['keyid'] through pyasn1.
    asn_sig['keyid'] = asn1_spec.Keyid(hexValue=pydict_sig['keyid'])


    # Because 'method' is an enum, extracting the string value is a bit messy.
    asn_sig['method'] = int(asn1_spec.SignatureMethod(pydict_sig['method']))

    # This stuff constructs an OctetString() object to hold the actual
    # signature itself, and assigns it the value from pydict_sig['sig'] through
    # pyasn1.
    asn_sig['value'] = asn1_spec.OctetString(hexValue=pydict_sig['sig'])


    # Add to the Signatures() list.
    asn_signatures_list[i] = asn_sig # has no append method
    i += 1

  return asn_signatures_list
