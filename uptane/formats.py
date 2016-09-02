"""
<Program Name>
  schema.py

<Purpose>
  Define (and allow validation of) types used by uptane code.
  Follows conventions from tuf. See tuf.formats.
"""

# We will have a superset of formats in TUF
from tuf.formats import *
import tuf.schema as SCHEMA

# Constitutes a nonce used by e.g. ECUs to help defend their validation of
# responses from the timeserver against replay attacks.
NONCE_LOWER_BOUND = 0
NONCE_UPPER_BOUND = 2147483647
NONCE_SCHEMA = SCHEMA.Integer(lo=NONCE_LOWER_BOUND, hi=NONCE_UPPER_BOUND)

# A list of nonces to be bundled in the primary's request to the timeserver
# for a signed and nonce-incorporating time datum.
NONCE_LIST_SCHEMA = SCHEMA.ListOf(NONCE_SCHEMA)

# Uniquely identifies a vehicle.
VIN_SCHEMA = SCHEMA.AnyString()

# Information characterizing and identifying an ECU.
# ECU_SCHEMA = SCHEMA.Object(
#     ecu_id = SCHEMA.AnyString(),
#     ecu_type = SCHEMA.AnyString(),
#     vin = VIN_SCHEMA)
ECU_SERIAL_SCHEMA = SCHEMA.AnyString() # Instead, for now, we'll go with an ecu serial number.


# Information specifying the target(s) installed on a given ECU.
ECU_SOFTWARE_ATTESTATION_SCHEMA = SCHEMA.Object(
    #ecu_serial = ECU_SERIAL_SCHEMA, # Will include in parallel instead.
    current_bootloader_images = SCHEMA.ListOf(TARGETFILE_SCHEMA), # multiple targets per ECU possible
    current_application_images = SCHEMA.ListOf(TARGETFILE_SCHEMA),
    timeserver_time = ISO8601_DATETIME_SCHEMA,
    previous_timeserver_time = ISO8601_DATETIME_SCHEMA,
    freeze_attack_detected = BOOLEAN_SCHEMA) # was expired metadata previously detected?

# Manifest detailing the targets installed on all ECUs in a vehicle for which
# Uptane is responsible.
VEHICLE_SOFTWARE_MANIFEST_SCHEMA = SCHEMA.DictOf(
    key_schema = ECU_SERIAL_SCHEMA,
    value_schema = ECU_SOFTWARE_ATTESTATION_SCHEMA)

# Information sent to the director by the primary.
# There probably will be additional fields here.
VEHICLE_REPORT_TO_DIRECTOR_SCHEMA = SCHEMA.Object(
    vin = VIN_SCHEMA,
    software_manifest = VEHICLE_SOFTWARE_MANIFEST_SCHEMA)


# This is the format for a single assignment given to an ECU by the Director.
ECU_SOFTWARE_ASSIGNMENT_SCHEMA = SCHEMA.Object(
    ecu_serial = ECU_SERIAL_SCHEMA,
    image_type = SCHEMA.OneOf('bootloader', 'application', 'other'),
    image = SCHEMA.TARGETFILE_SCHEMA
    load_order = SCHEMA.Integer(lo=0, hi=2147483647))

# A list of ECU_SOFTWARE_ASSIGNMENT_SCHEMA should be everything that is
# required for the director metadata to be written.
VEHICLE_SOFTWARE_ASSIGNMENTS_SCHEMA = SCHEMA.ListOf(
    ECU_SOFTWARE_ASSIGNMENT_SCHEMA)


# The format for the timeserver's signed time response will be a
# SIGNABLE_SCHEMA (from TUF). THAT in TURN will contain, in field 'signed', one
# of these objects:
TIMESERVER_ATTESTATION_SCHEMA = SCHEMA.Object(
    time = ISO8601_DATETIME_SCHEMA,
    nonces = NONCE_LIST_SCHEMA)

