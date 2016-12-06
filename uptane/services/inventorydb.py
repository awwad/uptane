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


class InventoryDataBase():
  """
  Dictionary design:

  {
    'vehicle manifests':
             {
               'vehicle_id_1': [ <full vehicle manifests, in order of receipt> ],
               ...
             },
    'ecu_manifests':
             {
               'ecu_serial': [ <full ECU manifests, in order of receipt>],
               ...
             }
    'public_keys':
             {
               'vehicle_primaries':
               {
                 'vehicle_id_1': { ecu_id: 'primary_ecu_id',
                                   public_key: <publickey for primary ecu>
                                 },
                 ...
               },
               'all_ecus':
               {
                 'ecu_serial_2': <publickey>,
                 ...
               }
             }
  }
  """
  # Inventory database dictionary
  inventory_db = {'vehicle_manifests': {},
                  'ecu_manifests': {},
                  'public_keys': {
                                  'vehicle_primaries': {},
                                  'all_ecus': {}
                                 }
                 }

  # Register ECU
  def register_ecu(self, isPrimary, vin, ecu_serial, public_key):
    if isPrimary:
      vehicle_primary_ids = self.inventory_db['public_keys']['vehicle_primaries']
      if (vehicle_primary_ids and (vin in vehicle_primary_ids)):
        # rewrite value
        (self.inventory_db['public_keys']['vehicle_primaries'])[vin] = \
           {'ecu_id': ecu_serial, 'public_key': public_key}
      else:
        temp_dic = {'ecu_id': ecu_serial, 'public_key': public_key}
        (self.inventory_db['public_keys']['vehicle_primaries'])[vin] = temp_dic
    else:
      ecu_serial_ids = self.inventory_db['public_keys']['all_ecus']
      if (ecu_serial_ids and (ecu_serial in ecu_serial_ids)):
        (self.inventory_db['public_keys']['all_ecus'])[ecu_serial] = public_key
      else:
        (self.inventory_db['public_keys']['all_ecus'])[ecu_serial] = public_key

    is_registered = 1


  # Save vehicle manifest
  def save_vehicle_manifest(self, vin, signed_vehicle_manifest):
    """
    Given a manifest of form
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA, save it in an index
    by vin, and save the individual ecu attestations in an index by ecu serial.
    """
    vehicle_primary_ids = self.inventory_db['public_keys']['vehicle_primaries']
    ecu_serial_ids = self.inventory_db['public_keys']['all_ecus']
    if len(vehicle_primary_ids) == 0 or len(ecu_serial_ids) == 0:
      raise uptane.UnknownECU("InventoryDataBase has not registered yet!")

    vehicle_ids = self.inventory_db['vehicle_manifests']
    if (vehicle_ids and (vin in vehicle_ids)):
      (self.inventory_db['vehicle_manifests'][vin]).append(signed_vehicle_manifest)
    else:
      vm_list = []
      vm_list.append(signed_vehicle_manifest)
      vehicle_ids[vin] = vm_list
      self.inventory_db['vehicle_manifests'] = vehicle_ids


  # Get vehicle manifest
  def get_vehicle_manifest(self, vin):
    # Check arg format
    vehicle_ids = self.inventory_db['vehicle_manifests']
    if (vehicle_ids and (vin in vehicle_ids)):
      return self.inventory_db['vehicle_manifests'][vin]
    return False


  # Save ECU manifest
  def save_ecu_manifest(self, ecu_serial, signed_ecu_manifest):
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)

    ecu_serial_ids = self.inventory_db['ecu_manifests']
    if (ecu_serials_ids and (ecu_serial in ecu_serials_ids)):
      (self.inventory_db['ecu_manifests'][ecu_serial]).append(signed_vehicle_manifest)
    else:
      ecu_list = []
      ecu_list.append(signed_vehicle_manifest)
      ecu_serial_ids[ecu_serial] = ecu_list
      self.inventory_db['ecu_manifests'] = ecu_serial_ids


  # Get ECU manifest
  def get_ecu_manifest(self, ecu_serial):
    # Check arg format
    ecu_serial_ids = self.inventory_db['ecu_manifests']
    if (ecu_serial_ids and (ecu_serial in ecu_serial__ids)):
      return self.inventory_db['ecu_manifests'][ecu_serial]
    return False


