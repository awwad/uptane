"""
<Program Name>
  inventorydb.py

<Purpose>
  Interface for storing data describing the software state of vehicles served
  by the Director.

  For now, this is a minimal schema:

    ECU DATA:
      JSON files, one per serviced ECU, will store the information for those
      ECUs. The filename of each file will be the ECU ID, as defined in
      formats.py as ECU_SERIAL_SCHEMA.
      These files will be stored at path INVENTORY_DB_DIR/.

      In other words, the files in INVENTORY_DB_DIR will map their filenames as
      ECU_SERIAL_SCHEMA to their contents, which will be
      ECU_VERSION_MANIFEST_SCHEMA (in JSON).

    VEHICLE DATA:
      JSON files, one per serviced vehicle, will store information for each
      vehicle. The filename of each file will be the vehicle's VIN (vehicle
      identification number), for now, as defined in formats.py as VIN_SCHEMA.

      The contained data will match SCHEMA.ListOf(ECU_SERIAL_SCHEMA).

  For now, only the most recent validated manifest from the vehicle is stored.
  Once a manifest is validated, it replaces the previously held manifest.
"""

import os.path
#join = os.path.join
import uptane
import uptane.formats
import tuf
import json

# TODO: Move this out of import territory and to somewhere sensible.
INVENTORY_DB_DIR = os.path.join(uptane.WORKING_DIR, 'inventorydb')
if not os.path.exists(INVENTORY_DB_DIR):
  os.mkdir(INVENTORY_DB_DIR)

def get_ecu_public_key(ecu_serial):

  # Hardcoded single example for now:
  # ECU ID ecu1234
  # key type ED25519
  # filename ecu1234.pub
  if ecu_serial == 'ecu1234':
    pubkey = rt.import_ed25519_publickey_from_file('ecu1234.pub')
  else:
    raise NotImplementedError('Ask for key ecu1234.')

  return pubkey


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



# Global dictionaries
vehicle_manifests_dic = {'vehicle_manifests': {}}
ecu_manifests_dic = {'ecu_manifests': {}}
primary_public_keys = {'vehicle_primaries': {}}
public_keys = {'all_ecus': {}}



# Save ECU manifest
def save_ecu_manifest(ecu_serial, signed_ecu_manifest):

  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
       signed_ecu_manifest)

  if ecu_serial not in public_keys['all_ecus']:
    raise uptane.UnknownECU("ECU serial has not been registered yet!")

  if ecu_serial not in ecu_manifests_dic['vehicle_manifests']:
    ecu_list = []
    ecu_list.append(signed_ecu_manifest)
    ecu_manifests_dic['ecu_manifests'][ecu_serial] = ecu_list
  else:
    ecu_manifests_dic['ecu_manifests'][ecu_serial].append(signed_vehicle_manifest)



# Get ECU manifest
def get_ecu_manifest(vin):

  uptane.formats.VIN_SCHEMA.check_match(vin)

  if vin not in ecu_manifests_dic['ecu_manifests']:
    raise uptane.Error('The given VIN, ' + repr(vin) + ', is not known.')
  else:
    return ecu_manifests_dic['ecu_manifests'][vin]


# Save vehicle manifest
def save_vehicle_manifest(vin, signed_vehicle_manifest):

  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
       signed_ecu_manifest)

  if vin not in vehicle_manifests_dic['vehicle_manifests']:
    vm_list = []
    vm_list.append(signed_vehicle_manifest)
    vehicle_manifests_dic['vehicle_manifests'][vin] = vm_list
  else:
    vehicle_manifests_dic['vehicle_manifests'][vin].append(signed_vehicle_manifest)

  # Save all the contained ECU manifests.
  # NOTE: not tested
  all_contained_ecu_manifests = signed_vehicle_manifest['signed']['ecu_manifests']
  for ecu_serial in all_contained_ecu_manifests:
    save_ecu_manifest(ecu_serial, all_contained_ecu_manifests[ecu_serial])


# Get vehicle manifest
def get_vehicle_manifest(vin):

  uptane.formats.VIN_SCHEMA.check_match(vin)

  if vin not in vehicle_manifests_dic['vehicle_manifests']:
    raise uptane.Error('The given VIN, ' + repr(vin) + ', is not known.')
  else:
    return vehicle_manifests_dic['vehicle_manifests'][vin]



# Register ECU
def register_ecu(isPrimary, vin, ecu_serial, public_key):
  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)

  if isPrimary:
    if vin in primary_public_keys['vehicle_primaries']:
      # rewrite value
      # TODO later it should return exeption or warning
      primary_public_keys['vehicle_primaries'][vin] = \
        {'ecu_id': ecu_serial, 'public_key': public_key}
    else:
      temp_dic = {'ecu_id': ecu_serial, 'public_key': public_key}
      primary_public_keys['vehicle_primaries'][vin] = temp_dic

  # public keys
  public_keys['all_ecus'][ecu_serial] = public_key

