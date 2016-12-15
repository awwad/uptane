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
from __future__ import print_function
from __future__ import unicode_literals
from io import open


import os.path
#join = os.path.join
import uptane
import uptane.formats
import tuf
import json
import canonicaljson

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



def get_vehicle_manifest(vin):

  uptane.formats.VIN_SCHEMA.check_match(vin) # Check arg format
  # This is obviously EXTREMELY insecure and the 'vin' passed in should be
  # scrubbed.
  # Perform trivial validation. NOT TO BE TRUSTED.
  scrubbed_vin = scrub_filename(vin, INVENTORY_DB_DIR)

  fname = os.path.join(scrubbed_vin, 'vehicle')

  return json.load(open(fname, 'r', encoding="utf-8"))





def save_vehicle_manifest(vin, signed_vehicle_manifest):
  """
  Given a manifest of form
  uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA, save it in an index
  by vin, and save the individual ecu attestations in an index by ecu serial.
  """
  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
      signed_vehicle_manifest)

  print('Saving Vehicle Manifest...')

  scrubbed_vin = scrub_filename(vin, INVENTORY_DB_DIR)

  if not os.path.exists(scrubbed_vin):
    os.mkdir(scrubbed_vin)

  fname = os.path.join(scrubbed_vin, 'vehicle')

  with open(fname, 'wb') as fobj:
    fobj.write(canonicaljson.encode_canonical_json(signed_vehicle_manifest))

  print('Saved Vehicle Manifest.')





def get_ecu_manifest(vin, ecu_serial):
  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial) # Check arg format
  # This is obviously EXTREMELY insecure and the 'vin' passed in should be
  # scrubbed.
  # Perform trivial validation. NOT TO BE TRUSTED.
  scrubbed_vin = scrub_filename(vin, INVENTORY_DB_DIR)
  scrubbed_ecu_serial = scrub_filename(ecu_serial, INVENTORY_DB_DIR)

  fname = os.path.join(scrubbed_vin, ecu_serial) # Note non-scrubbed.

  return json.load(open(fname, 'r', encoding="utf-8"))





def save_ecu_manifest(vin, ecu_serial, signed_ecu_manifest):
  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
      signed_ecu_manifest)

  print('Saving ECU Manifest...')

  scrubbed_vin = scrub_filename(vin, INVENTORY_DB_DIR)
  if not os.path.exists(scrubbed_vin):
    os.mkdir(scrubbed_vin)

  scrubbed_ecu_serial = scrub_filename(ecu_serial, INVENTORY_DB_DIR)

  fname = os.path.join(scrubbed_vin, ecu_serial) # Note non-scrubbed.

  with open(fname, 'wb') as fobj:
    fobj.write(canonicaljson.encode_canonical_json(signed_ecu_manifest))

  print('Saved ECU Manifest for ECU ' + str(ecu_serial) + ' at ' + fname)




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





def get_random_string(length):
  """
  Returns a random alphanumeric string of length length. Not
  cryptographically reliable.
  """
  return ''.join(
      random.choice(string.ascii_uppercase + string.ascii_lowercase +
      string.digits) for i in range(length))
