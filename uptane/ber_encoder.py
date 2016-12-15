from __future__ import print_function
from __future__ import unicode_literals

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
  print('(Skipping ASN.1-BER encoding of signable object!)')
  return signable

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
  print('(Skipping ASN.1-BER encoding of ECU manifest!)')
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