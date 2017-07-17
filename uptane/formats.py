"""
<Program Name>
  schema.py

<Purpose>
  Define (and allow validation of) types used by uptane code.
  Follows conventions from tuf. See tuf.formats.
"""
from __future__ import print_function
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

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

HARDWARE_ID_SCHEMA = SCHEMA.AnyString()

RELEASE_COUNTER_SCHEMA = SCHEMA.Integer(lo=0)

# Information specifying the target(s) installed on a given ECU.
# This object corresponds to not "ECUVersionManifest" in the Uptane
# Implementation Specification, but the signed contents of that object.
ECU_VERSION_MANIFEST_SCHEMA = SCHEMA.Object(
    ecu_serial = ECU_SERIAL_SCHEMA,
    hardware_ID = HARDWARE_ID_SCHEMA,
    release_counter = RELEASE_COUNTER_SCHEMA,
    installed_image = TARGETFILE_SCHEMA,
    timeserver_time = ISO8601_DATETIME_SCHEMA,
    previous_timeserver_time = ISO8601_DATETIME_SCHEMA,
    attacks_detected = SCHEMA.AnyString()) # was expired metadata previously detected?

# This object corresponds to "ECUVersionManifest" in ASN.1 in the Uptane
# Implementation Specification.
SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA = SCHEMA.Object(
    object_name = 'SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA',
    signed = ECU_VERSION_MANIFEST_SCHEMA,
    signatures = SCHEMA.ListOf(SIGNATURE_SCHEMA))

# Anything encoded as DER is not readily inspected. Its encoding can be checked
# this way, and conversion back from ASN.1/DER to a Python dictionary should be
# performed before a thorough check of the contents.
DER_DATA_SCHEMA = SCHEMA.AnyBytes()

# Manifest detailing the targets installed on all ECUs in a vehicle for which
# Uptane is responsible.
# This object corresponds to not "VehicleVersionManifest" in the Uptane
# Implementation Specification, but the signed contents of that object.
VEHICLE_VERSION_MANIFEST_SCHEMA = SCHEMA.Object(
    vin = VIN_SCHEMA, # Spec: vehicleIdentifier
    primary_ecu_serial = ECU_SERIAL_SCHEMA, # Spec: primaryIdentifier
    hardware_id = HARDWARE_ID_SCHEMA,
    release_counter = RELEASE_COUNTER_SCHEMA,
    ecu_version_manifests = SCHEMA.DictOf(
        key_schema = ECU_SERIAL_SCHEMA,
        value_schema = SCHEMA.ListOf(SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA)))

# This object corresponds to "VehicleVersionManifest" in ASN.1 in the Uptane
# Implementation Specification.
SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA = SCHEMA.Object(
    object_name = 'SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA',
    signed = VEHICLE_VERSION_MANIFEST_SCHEMA,
    signatures = SCHEMA.ListOf(SIGNATURE_SCHEMA))


# Information sent to the director by the primary.
# There probably will be additional fields here.
VEHICLE_REPORT_TO_DIRECTOR_SCHEMA = SCHEMA.Object(
    vin = VIN_SCHEMA,
    software_manifest = VEHICLE_VERSION_MANIFEST_SCHEMA)


DESCRIPTION_OF_ATTACKS_SCHEMA = SCHEMA.AnyString()

# This is the format for a single assignment given to an ECU by the Director.
ECU_SOFTWARE_ASSIGNMENT_SCHEMA = SCHEMA.Object(
    ecu_serial = ECU_SERIAL_SCHEMA,
    previous_time = tuf.formats.ISO8601_DATETIME_SCHEMA, #UTC_DATETIME_SCHEMA,
    current_time = tuf.formats.ISO8601_DATETIME_SCHEMA,
    security_attack = SCHEMA.Optional(DESCRIPTION_OF_ATTACKS_SCHEMA),
    #image_type = SCHEMA.OneOf('bootloader', 'application', 'other'), # removed from spec
    installed_image = tuf.formats.TARGETFILE_SCHEMA)
    #load_order = SCHEMA.Integer(lo=0, hi=2147483647)) # not in spec

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

SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA = SCHEMA.Object(
    object_name = 'SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA',
    signed = TIMESERVER_ATTESTATION_SCHEMA,
    signatures = SCHEMA.ListOf(SIGNATURE_SCHEMA))


ANY_SIGNABLE_UPTANE_METADATA_SCHEMA = SCHEMA.OneOf([
    SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA,
    SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA,
    SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA])

