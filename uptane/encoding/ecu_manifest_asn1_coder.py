"""
<Name>
  uptane/encoding/ecu_manifest_asn1_coder.py

<Purpose>
  This module contains conversion functions (get_asn_signed and get_json_signed)
  for converting ECU Version Manifests to and from Uptane's standard
  Python dictionary metadata format (usually serialized as JSON) and an ASN.1
  format that conforms to pyasn1 specifications and Uptane's ASN.1 definitions.

<Functions>
  get_asn_signed(pydict_signed)
  get_json_signed(asn_signed)    # TODO: Rename to get_pydict_signed in all mods

"""
from __future__ import print_function
from __future__ import unicode_literals

from pyasn1.type import tag

from uptane.encoding.asn1_definitions import *

import calendar
from datetime import datetime


def get_asn_signed(json_signed):
  signed = ECUVersionManifestSigned()
  signed['ecuIdentifier'] = json_signed['ecu_serial']
  signed['previousTime'] = calendar.timegm(datetime.strptime(
      json_signed['previous_timeserver_time'], "%Y-%m-%dT%H:%M:%SZ").timetuple())
  signed['currentTime'] = calendar.timegm(datetime.strptime(
      json_signed['timeserver_time'], "%Y-%m-%dT%H:%M:%SZ").timetuple())

  # Optional bit.
  if 'attacks_detected' in json_signed and json_signed['attacks_detected']:
    attacks_detected = json_signed['attacks_detected']
    signed['securityAttack'] = attacks_detected

  target = Target()
  filename = json_signed['installed_image']['filepath']
  filemeta = json_signed['installed_image']['fileinfo']
  target['filename'] = filename
  target['length'] = filemeta['length']

  hashes = Hashes()
  numberOfHashes = 0

  # We're going to generate a list of hashes from the dictionary of hashes.
  # The DER will contain this list, and the order of items in this list will
  # affect hashing of the DER, and therefore signature verification.
  # We have to make the order deterministic.
  sorted_hash_functions = sorted(filemeta['hashes'])

  for hash_function in sorted_hash_functions:
    hash_value = filemeta['hashes'][hash_function]
    hash = Hash()
    hash['function'] = int(HashFunction(hash_function))
    hash['digest'] = OctetString(hexValue=hash_value)
    hashes[numberOfHashes] = hash
    numberOfHashes += 1

  target['numberOfHashes'] = numberOfHashes
  target['hashes'] = hashes
  signed['installedImage'] = target

  return signed


def get_json_signed(asn_metadata):
  # TODO: Fix obnoxious property: that this function takes asn_metadata instead
  # of asn_metadata['signed'].
  asn_signed = asn_metadata['signed']

  timeserver_time = datetime.utcfromtimestamp(
      asn_signed['currentTime']).isoformat() + 'Z'
  previous_timeserver_time = datetime.utcfromtimestamp(
      asn_signed['previousTime']).isoformat() + 'Z'
  ecu_serial = str(asn_signed['ecuIdentifier'])

  target = asn_signed['installedImage']
  filepath = str(target['filename'])
  fileinfo = {'length': int(target['length'])}

  numberOfHashes = int(target['numberOfHashes'])
  # Quick workaround for now.
  hashenum_to_hashfunction = {
    1: 'sha256',
    3: 'sha512'
  }
  hashes = target['hashes']
  json_hashes = {}
  for j in range(numberOfHashes):
    hash = hashes[j]
    hash_function = hashenum_to_hashfunction[int(hash['function'])]
    hash_value = hash['digest'].prettyPrint()
    assert hash_value.startswith('0x')
    hash_value = hash_value[2:]
    json_hashes[hash_function] = hash_value
  fileinfo['hashes'] = json_hashes

  installed_image = {
    'filepath': filepath,
    'fileinfo': fileinfo
  }

  json_signed = {
    'ecu_serial': ecu_serial,
    'installed_image': installed_image,
    'previous_timeserver_time': previous_timeserver_time,
    'timeserver_time': timeserver_time,
    'attacks_detected': ''
  }

  # Optional bit.
  if 'securityAttack' in asn_signed and asn_signed['securityAttack'].hasValue():
    json_signed['attacks_detected'] = str(asn_signed['securityAttack'])

  return json_signed
