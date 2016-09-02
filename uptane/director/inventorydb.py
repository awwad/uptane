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
      ECU_SOFTWARE_ATTESTATION_SCHEMA (in JSON).

    VEHICLE DATA:
      JSON files, one per serviced vehicle, will store information for each
      vehicle. The filename of each file will be the vehicle's VIN (vehicle
      identification number), for now, as defined in formats.py as VIN_SCHEMA.

      The contained data will match SCHEMA.ListOf(ECU_SERIAL_SCHEMA).
"""

import os.path
join = os.path.join
import uptane
import uptane.formats
import tuf
import json

INVENTORY_DB_DIR = os.path.join(uptane.WORKING_DIR + 'inventorydb')





def get_vehicle_manifest(vin):

  uptane.formats.VIN_SCHEMA.check_match(vin) # Check arg format
  # This is obviously EXTREMELY insecure and the 'vin' passed in should be
  # scrubbed.
  # Perform trivial validation. NOT TO BE TRUSTED.
  scrubbed_vin = scrub_filename(vin, INVENTORY_DB_DIR)

  return json.load(open(scrubbed_vin, 'r'))





def save_vehicle_manifest(vin, manifest_dict):
  """
  Given a manifest of form VEHICLE_SOFTWARE_MANIFEST_SCHEMA, save it in an
  index by vin, and save the individual ecu attestations in an index by ecu
  serial.

  This is CURRENTLY EXPOSED DIRECTLY via director.py:Director.listen() over an
  XML-RPC interface.
  """
  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.VEHICLE_SOFTWARE_MANIFEST_SCHEMA.check_match(manifest_dict)

  scrubbed_vin = scrub_filename(vin, INVENTORY_DB_DIR)

  json.dump(open(scrubbed_vin, 'w'))

  for ecu_serial in manifest_dict:
    save_ecu_attestation(ecu_serial, manifest_dict[ecu_serial])





def get_ecu_attestation(ecu_serial):
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial) # Check arg format
  # This is obviously EXTREMELY insecure and the 'vin' passed in should be
  # scrubbed.
  # Perform trivial validation. NOT TO BE TRUSTED.
  scrubbed_ecu_serial = scrub_filename(ecu_serial, INVENTORY_DB_DIR)

  return json.load(open(scrubbed_ecu_serial, 'r'))





def save_ecu_attestation(ecu_serial, attestation_dict):
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
  uptane.formats.ECU_SOFTWARE_ATTESTATION_SCHEMA.check_match(attestation_dict)

  scrubbed_ecu_serial = scrub_filename(ecu_serial, INVENTORY_DB_DIR)

  json.dump(open(scrubbed_ecu_serial, 'w'))





def scrub_filename(fname, expected_containing_dir):
  """
  DO NOT ASSUME THAT THIS TEMPORARY FUNCTION IS SECURE.

  Performs basic scrubbing to try to ensure that the filename provided is
  actually just a plain filename (no pathing), so that it cannot specify a file
  that 

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
  if not abs_fname.startswith(expected_containing_dir):
    raise ValueError('Expected a plain filename. Was given one that had '
        'pathing specified that put it in a different, unexpected directory. '
        'Filename was: ' + fname)

  return abs_fname



