from __future__ import print_function
from __future__ import unicode_literals

import uptane
import json
import pyasn1.codec.ber.encoder as p_ber_encoder
import pyasn1.codec.ber.decoder as p_ber_decoder
import pyasn1.type # Only needed for the sorcery at about line 100.
import tuf.keys

import hashlib # temporary

import uptane.encoding.timestampmetadata as timestampmetadata
import uptane.encoding.targetsmetadata as targetsmetadata
import uptane.encoding.metadataverificationmodule as metadata_asn1_spec

# This maps metadata type ('_type') to the module that lays out the
# ASN.1 format for that type.
SUPPORTED_METADATA_MODULES = {
    'timestamp': timestampmetadata,
    'targets': targetsmetadata}



def validate_metadata_type(metadata_type):
  if metadata_type not in SUPPORTED_METADATA_MODULES:
    # TODO: Choose/make better exception class.
    raise uptane.Error('This is not one of the metadata types configured for '
        'translation from JSON to BER. Type of given metadata: ' +
        repr(metadata_type) + '; types accepted: ' +
        repr([t for t in SUPPORTED_METADATA_MODULES]))




def ber_encode_signable_object(signable):
  """
  Arguments:

    signable:
      A dictionary containing dict 'signed' and list 'signatures'.
      e.g.:
        {
          'signed':
            <bytes object UNCHANGED from Signed above>,

          'signature':
            A list[] of DECODED objects conforming to
            tuf.formats.SIGNATURE_SCHEMA
        }

  Returns:
    ber_encoded_object: bytes object representing this ASN.1:
      SEQUENCE {
        signed Signed,
        signature Signature
      }
  """
  #print('(Skipping ASN.1-BER encoding of signable object!)')
  return signable





#def encode_signed_json_metadata_as_ber(json_filename, private_key):
def convert_signed_json_to_signed_ber(json_filename, private_key):
  # "_signed" here refers to the portion of the metadata that will be signed.
  # The metadata is divided into "signed" and "signature" portions. The
  # signatures are signatures over the "signed" portion. "json_signed" below
  # is actually not signed - it is simply the portion that will be put into
  # the "signed" section - the portion to be signed. The nomenclature is
  # unfortunate....
  # TODO: Better variable and function naming.

  # TODO: Use TUF's json loader functions instead.
  json_signed = json.load(open(json_filename))['signed']

  # Force lowercase for metadata type because some TUF versions have been
  # inconsistent in the casing of metadata types ('targets' vs 'Targets').
  metadata_type = json_signed['_type'].lower()

  # Ensure that the type is one of the supported metadata types, for which
  # a module exists that translates it to and from an ASN.1 format.
  validate_metadata_type(metadata_type)

  # Handle for the corresponding module.
  relevant_asn_module = SUPPORTED_METADATA_MODULES[metadata_type]
  asn_signed = relevant_asn_module.get_asn_signed(json_signed) # Python3 breaks here.

  ber_signed = p_ber_encoder.encode(asn_signed)
  hash_of_ber = hashlib.sha256(ber_signed).hexdigest()

  # Now sign the metadata. (This signs a cryptographic hash of the metadata.)
  # The returned value is a basic Python dict writable into JSON.
  dict_signature_over_ber = tuf.keys.create_signature(private_key, hash_of_ber)#ber_signed)

  # Construct an ASN.1 representation of the signature and populate it.
  asn_signature_over_ber = metadata_asn1_spec.Signature()
  asn_signature_over_ber['keyid'] = dict_signature_over_ber['keyid']
  # Why is this next line required for 'method' but not for 'keyid'??
  asn_signature_over_ber['method'] = int(metadata_asn1_spec.SignatureMethod(
      dict_signature_over_ber['method'].encode('ascii')))
  asn_signature_over_ber['value'] = dict_signature_over_ber['sig']

  # Create a Signatures object containing some unknown sorcery to specify types.
  # TODO: <~> Understand and clarify!
  # The following documents tagging in pyasn1:
  #   http://www.red-bean.com/doc/python-pyasn1/pyasn1-tutorial.html#1.2
  asn_signatures_list = metadata_asn1_spec.Signatures().subtype(
      implicitTag=pyasn1.type.tag.Tag(pyasn1.type.tag.tagClassContext,
      pyasn1.type.tag.tagFormatSimple, 2))

  asn_signatures_list[0] = asn_signature_over_ber

  # Now construct an ASN.1 representation of the signed/signatures-encapsulated
  # metadata, populating it.
  metadata = metadata_asn1_spec.Metadata()
  metadata['signed'] = asn_signed #considering using ber_signed instead - requires changes
  metadata['signatures'] = asn_signatures_list # TODO: Support multiple sigs, or integrate with TUF.
  metadata['numberOfSignatures'] = 1

  return p_ber_encoder.encode(metadata)





# TODO: Make this and previous function consistent. This one takes data.
# Previous one takes a file. Make that and naming consistent.
def convert_signed_ber_to_unsigned_json(ber_data):
  """
  Convert the given ber_data to JSON, retaining only the 'signed'
  segment (and not the signatures themselves). This is for testing.
  """
  # "_signed" here refers to the portion of the metadata that will be signed.
  # The metadata is divided into "signed" and "signature" portions. The
  # signatures are signatures over the "signed" portion. "json_signed" below
  # is actually not signed - it is simply the portion that will be put into
  # the "signed" section - the portion to be signed. The nomenclature is
  # unfortunate....
  asn_metadata = p_ber_decoder.decode(
      ber_data, asn1Spec=metadata_asn1_spec.Metadata())[0] # why 0? Magic.

  # asn_metadata here now has three components, indexed by integer 0, 1, 2.
  # 0 is the signed component (Signed())
  # 1 i the numberOfSignatures component (Length())
  # 2 is the signatures component (Signatures())

  asn_signed_metadata = asn_metadata[0]

  # TODO: <~> The 'signed' component here should probably already be BER, since
  # that is what the signature is over. Because this would entail some changes
  # changes to the ASN.1 data specifications in metadataverificationmodule.py,
  # I'm not doing this yet (though I expect to).
  # So, for the time being, if we wanted to check the signature, we'd have to
  # encode this thing into BER again.
  # ber_signed_metadata = p_ber_encoder.encode(asn_signed)


  # Now we have to figure out what type of metadata the ASN.1 metadata is
  # so that we can use the appropriate spec to convert it back to JSON.
  # For example, if it's targets metadata, we do this:
  # TODO: <~> DETERMINE THE METADATA TYPE FIRST.
  # (Even those this takes asn_metadata, it only uses asn_metadata[0],
  # asn_signed_metadata....)
  asn_type_data = asn_signed_metadata[0] # This is the RoleType info, a class.
  # This is how we'd extract the name of the type from the enumeration that is
  # in the class (namedValues), indexed by the underlying "value" of
  # asn_type_data.
  # We call lower() on it because I don't care about the casing, which has
  # varied somewhat in TUF history, and I don't want casing to ruin this
  # detection.
  metadata_type = asn_type_data.namedValues[asn_type_data._value][0].lower()

  # Make sure it's a supported type. (Throw an exception if not.)
  validate_metadata_type(metadata_type)

  # Handle for the corresponding module.
  relevant_asn_module = SUPPORTED_METADATA_MODULES[metadata_type]

  # Finally, convert into the basic Python dict we use in the JSON encoding.
  json_signed = relevant_asn_module.get_json_signed(asn_metadata)

  return json_signed




def ber_encode_ecu_manifest(ecu_manifest):
  """
  Arguments:
    ecu_manifest:
      An object conforming to uptane.formats.ECU_VERSION_MANIFEST_SCHEMA:
        ECU_VERSION_MANIFEST_SCHEMA = SCHEMA.Object(
            ecu_serial = ECU_SERIAL_SCHEMA
            installed_image = tuf.formats.TARGETFILE_SCHEMA,
            timeserver_time = tuf.formats.ISO8601_DATETIME_SCHEMA,
            previous_timeserver_time = tuf.formats.ISO8601_DATETIME_SCHEMA,
            attacks_detected = SCHEMA.AnyString())

  Returns:
    ber_ecu_version_manifest:
      See the Implementation Specification Table 8.1.2a:
      ECUVersionManifest.Signed (not the whole object: the Signed bit):
          ecuIdentifier   VisibleString,
          previousTime    UTCDateTime,
          currentTime     UTCDateTime,
          securityAttack  VisibleString OPTIONAL,
          installedImage  Target


  """
  #print('(Skipping ASN.1-BER encoding of ECU manifest!)')
  return ecu_manifest




def ber_decode_signable_object(ber_encoded_object):
  """



  Arguments:

    ber_encoded_object: bytes object representing this ASN.1:
      SEQUENCE {
        signed Signed,
        signature Signature
      }

  Returns:

    decoded_dict:
      A dictionary containing dict 'signed' and list 'signatures'.
      e.g.:
        {
          'signed':
            <bytes object UNCHANGED from Signed above>,

          'signature':
            A list[] of DECODED objects conforming to
            tuf.formats.SIGNATURE_SCHEMA
        }
  """

  pass



# SEVERAL functions like the below geared to each individual kind of message.
# Includes separate pieces of the Vehicle Version Manifest itself as well as
# the individual ECU Version Manifests.

def ber_decode_ecu_version_manifest(ber_ecu_version_manifest):

  """


  Arguments:
    ber_ecu_version_manifest:
      See the Implementation Specification Table 8.1.2a:
      ECUVersionManifest.Signed (not the whole object: the Signed bit):
          ecuIdentifier   VisibleString,
          previousTime    UTCDateTime,
          currentTime     UTCDateTime,
          securityAttack  VisibleString OPTIONAL,
          installedImage  Target

  Returns:
    An object conforming to uptane.formats.ECU_VERSION_MANIFEST_SCHEMA:
      ECU_VERSION_MANIFEST_SCHEMA = SCHEMA.Object(
          ecu_serial = ECU_SERIAL_SCHEMA
          installed_image = tuf.formats.TARGETFILE_SCHEMA,
          timeserver_time = tuf.formats.ISO8601_DATETIME_SCHEMA,
          previous_timeserver_time = tuf.formats.ISO8601_DATETIME_SCHEMA,
          attacks_detected = SCHEMA.AnyString())


  """
  pass