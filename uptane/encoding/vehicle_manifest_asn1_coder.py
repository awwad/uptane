"""
<Name>
  uptane/encoding/vehicle_manifest_asn1_coder.py

<Purpose>
  This module contains conversion functions (get_asn_signed and get_json_signed)
  for converting vehicle version manifests to and from Uptane's standard
  Python dictionary metadata format (usually serialized as JSON) and an ASN.1
  format that conforms to pyasn1 specifications and Uptane's ASN.1 definitions.

<Functions>
  get_asn_signed(pydict_signed)
  get_json_signed(asn_signed)    # TODO: Rename to get_pydict_signed in all mods

"""
from __future__ import print_function
from __future__ import unicode_literals

from pyasn1.type import univ, tag

from uptane.encoding.asn1_definitions import *

import uptane.encoding.ecu_manifest_asn1_coder as ecu_manifest_asn1_coder


def get_asn_signed(json_signed):
  signed = VehicleVersionManifestSigned()\
           .subtype(implicitTag=tag.Tag(tag.tagClassContext,
                                        tag.tagFormatConstructed, 0))

  signed['vehicleIdentifier'] = json_signed['vin']
  signed['primaryIdentifier'] = json_signed['primary_ecu_serial']

  ecuVersionManifests = ECUVersionManifests()\
                        .subtype(implicitTag=tag.Tag(tag.tagClassContext,
                                                     tag.tagFormatSimple, 3)) # Should this be tagFormatConstructed?
  numberOfECUVersionManifests = 0

  # We're going to generate a list of ECU Manifests from the dictionary of lists
  # of ECU Manifests.
  # The DER will contain this list, and the order of items in this list will
  # affect hashing of the DER, and therefore signature verification.
  # We have to make the order deterministic.
  sorted_ecu_serials = sorted(json_signed['ecu_version_manifests'])
  for ecu_serial in sorted_ecu_serials:
    for manifest in json_signed['ecu_version_manifests'][ecu_serial]:
      temp_ecu_manifest = ECUVersionManifest()
      # This is the 'signed' element of the ECU Manifest,
      # and we need the full signable (including 'signatures').
      ecu_manifest_signed = ecu_manifest_asn1_coder.get_asn_signed(
          manifest['signed'])
      # TODO: RESOLVE CIRCULAR IMPORT and move this import to top of module.
      # Will probably collapse the *coder.py modules into this module and
      # refactor.
      import uptane.encoding.asn1_codec as asn1_codec
      ecu_manifest_signatures = asn1_codec.convert_signatures_to_asn(
          manifest['signatures'])

      temp_ecu_manifest['numberOfSignatures'] = len(ecu_manifest_signatures)
      temp_ecu_manifest['signatures'] = ecu_manifest_signatures
      temp_ecu_manifest['signed'] = ecu_manifest_signed

      # TODO: For now, the ASN.1 data keeps all the ECU Manifests in a list
      # rather than having a dictionary with index ECU Serial and value list of
      # ECU Manifests for that ECU Serial. This should probably be changed,
      # or the security implications of losing the association between the
      # exterior labeling of ECU Serial and the contents of the ECU Manifest
      # (which could hypothetically incorrectly contain the wrong ECU Serial?
      # That is checked by the Primary, but... this still bears thought.)
      ecuVersionManifests[numberOfECUVersionManifests] = temp_ecu_manifest
      numberOfECUVersionManifests += 1

  signed['numberOfECUVersionManifests'] = numberOfECUVersionManifests
  signed['ecuVersionManifests'] = ecuVersionManifests

  return signed


def get_json_signed(asn_metadata):
  asn_signed = asn_metadata['signed']

  json_signed = {
      'vin': str(asn_signed['vehicleIdentifier']),
      'primary_ecu_serial': str(asn_signed['primaryIdentifier'])
  }

  json_manifests = {}
  numberOfECUVersionManifests = int(asn_signed['numberOfECUVersionManifests'])
  ecuVersionManifests = asn_signed['ecuVersionManifests']

  # TODO: Don't simply assume that the number of manifests here is actually
  # equal to numberOfECUVersionManifests. We don't really care in Python about
  # this number.... Make sure to generate a meaningful exception if you can't
  # just iterate. Consider raising a warning if the number doesn't
  # match the actual number of ECU Manifests in here. (Would still be Primary-
  # validated via signature.)
  for i in range(numberOfECUVersionManifests):

    manifest = ecuVersionManifests[i]

    json_manifest_signed = ecu_manifest_asn1_coder.get_json_signed(
        manifest) # Weird: this takes the full manifest, not just 'signed'

    ecu_serial = json_manifest_signed['ecu_serial']

    import uptane.encoding.asn1_codec as asn1_codec # TODO: <~> Fix circular import and move.
    json_manifest_sigs = asn1_codec.convert_signatures_to_json(
        manifest['signatures'])

    json_manifest = {
        'signatures': json_manifest_sigs, 'signed': json_manifest_signed}

    # TODO: I think it's fine, but consider repercussions of trusting this ECU
    # Serial inside the manifest here.
    if ecu_serial not in json_manifests:
      json_manifests[ecu_serial] = []
    json_manifests[ecu_serial].append(json_manifest)

  json_signed['ecu_version_manifests'] = json_manifests

  return json_signed
