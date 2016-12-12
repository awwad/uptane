"""
"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open


def json_to_asn1(json_input):
  print("Pretending to convert.")


def asn1_to_json(asn1_input):
  print("Pretending to convert.")





  # ASN.1, dev
  def _pretend_to_receive_vehicle_manifest(self):
    # For dev purposes.
    vin = '1234567890'
    encoded_manifest = open('manifest.cer', 'rb').read()
    self.receive_and_convert_vehicle_manifest(vin, encoded_manifest)



  # ASN.1
  def receive_and_convert_vehicle_manifest(self, vin, encoded_manifest):
    """
    manifest here is a binary, ASN.1 BER/CER/DER object representing the
    vehicle manifest.
    It is an object matching uptane.clients.applicationmodule.MetadataFile
    """

    # Check argument format.
    uptane.formats.VIN_SCHEMA.check_match(vin)

    # Convert manifest to uptane.formats.VEHICLE_VERSION_MANIFEST_SCHEMA.
    # TODO: Move imports up later.
    import pyasn1.type #from pyasn1.type import univ, char, namedtype, namedval, tag, constraint, useful
    from pyasn1.codec.cer import decoder
    import uptane.clients.applicationmodule as appmodule
    decoded_tuples = decoder.decode(
        encoded_manifest, asn1Spec=appmodule.MetadataFile())

    signed_metadata = decoded_tuples[0][3]['signed']
    signatures = decoded_tuples[0][3]['signatures']

    #print(signed_metadata.prettyPrint())

    # 1. Convert this signed_metadata object:
    #      From: uptane.clients.applicationmodule.Metadata               (ASN1)
    #      Into: uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA (JSON)

    # 2. Validate signatures on these objects.
    #     - Determine key to use.
    #     - Get cryptographic hash of the original object:
    #         (a uptane.clients.applicationmodule.Metadata object or no??)
    #     - Check signature.

    print('Signed contents of object are:')
    print(signed_metadata.prettyPrint())

    print('Not yet converting to JSON or checking signature!!')
