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

import ecu_manifest_asn1_coder


def get_asn_signed(json_signed):
  signed = VehicleVersionManifestSigned()\
           .subtype(implicitTag=tag.Tag(tag.tagClassContext,
                                        tag.tagFormatConstructed, 0))

  signed['vehicleIdentifier'] = json_signed['vin']
  signed['primaryIdentifier'] = json_signed['primary_ecu_serial']

  ecuVersionManifests = ECUVersionManifests()\
                        .subtype(implicitTag=tag.Tag(tag.tagClassContext,
                                                     tag.tagFormatSimple, 3))
  numberOfECUVersionManifests = 0

  for manifest in json_signed['ecu_version_manifests']:
    json_signed, json_signatures = manifest['signed'], manifest['signatures']
    asn_signed, der_signed = metadata.get_asn_and_der_signed(
        ecu_manifest_asn1_coder.get_asn_signed, json_signed)
    ecuVersionManifest = \
        metadata.json_to_asn_metadata(asn_signed, der_signed, json_signatures,
                                      ECUVersionManifest)
    ecuVersionManifests[numberOfECUVersionManifests] = ecuVersionManifest
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

  json_manifests = []
  numberOfECUVersionManifests = int(asn_signed['numberOfECUVersionManifests'])
  ecuVersionManifests = asn_signed['ecuVersionManifests']
  for i in range(numberOfECUVersionManifests):
    manifest = ecuVersionManifests[i]
    json_manifest = metadata.asn_to_json_metadata(
        ecu_manifest_asn1_coder.get_json_signed, manifest)
    json_manifests.append(json_manifest)
  json_signed['ecu_version_manifests'] = json_manifests

  return json_signed
