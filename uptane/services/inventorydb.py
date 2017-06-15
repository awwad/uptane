"""
<Program Name>
  inventorydb.py

<Purpose>
  Interface for storing data describing the software state of vehicles served
  by the Director.


  # TODO: <~> This is not properly thread-safe: there may be race conditions if
  Primaries are being switched frequently. The windows are extremely small, but
  assertions related to VIN registration in _check_registration_is_sane() are
  likely to fail if such a race   condition is encountered. Similar race
  conditions may exist. Cautious use of mutexes or a queue is probably
  necessary.



<Globals>
  The following five global dictionaries store information about ECUs and
  vehicles, including their serials, keys, and manifests submitted from
  (ostensibly) them to the Director.

    vehicle_manifests

      A dictionary indexed by the VINs (vehicle identification numbers) of
      known vehicles (uptane.format.VIN_SCHEMA), with values each being lists
      of vehicle manifests from that vehicle - each list element is a manifest
      with structure complying with the format specification
      uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.

      All known vehicles should be in this dictionary.

      e.g. {'vin1': [<vehiclemanifest>, <vehiclemanifest>, ...}], 'vin2': []}


    ecu_manifests

      A dictionary indexed by the ECU Serials of known ECUs
      (uptane.format.ECU_SERIAL_SCHEMA), with values each being lists of ECU
      manifests from that ECU. Individual list elements comply with
      uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.

      This is duplicated data, as all ECU Manifests were extracted from Vehicle
      Manifests which are also saved in full in global vehicle_manifests.

      All known ECU Serials should be in this dictionary.

      e.g. {'ecuserial1': [<ecumanifest>, <ecumanifest>], 'ecuserial2': []}


    primary_ecus_by_vin

      A dictionary mapping VIN of a vehicle (uptane.formats.VIN_SCHEMA) to the
      ECU Serial (uptane.formats.ECU_SERIAL_SCHEMA) of the vehicle's Primary
      ECU.

      All known vehicles should be in this dictionary. If a vehicle has no
      registered Primary ECU for some reason, the value should be set to None.

      e.g. {'vin1': 'ecuserial1', 'vin2': 'ecuserial2'}


    ecus_by_vin

      A dictionary mapping VIN of a vehicle (uptane.formats.VIN_SCHEMA) to a
      list of the ECU Serials (uptane.formats.ECU_SERIAL_SCHEMA) of all ECUs
      associated with that vehicle.

      All known vehicles should have their VIN in this dictionary.

      e.g.
          {'vin1': ['ecuserial1', 'ecuserial9'],
           'vin2': ['ecuserial2']}

      This is used to both identify known VINs and associate ECUs with VINs.
      Identifying known ECUs is generally done instead by checking the
      ecu_public_keys field, since that is flat.


    ecu_public_keys

      A dictionary mapping ECU Serial (uptane.formats.ECU_SERIAL_SCHEMA) of an
      ECU to the public key (conforming to uptane.formats.ANYKEY_SCHEMA) that
      corresponds to the signing key we expect that ECU to use.

      All known ECUs should have their ECU Serial in this dictionary.

      e.g. {'ecuserial1': <key>, 'ecuserial2': <key>, ...}


<Public Functions>

  Registration:
    register_ecu(is_primary, vin, ecu_serial, public_key, overwrite=True)
    check_ecu_registered(ecu_serial)
    check_vin_registered(vin)

  Get Public Key:
    get_ecu_public_key(ecu_serial)

  Save Manifests:
    save_vehicle_manifest(vin, signed_vehicle_manifest)
    save_ecu_manifest(vin, ecu_serial, signed_ecu_manifest)

  Get Manifests:
    get_vehicle_manifests(vin)
    get_last_vehicle_manifest(vin)
    get_ecu_manifests(ecu_serial)
    get_last_ecu_manifest(ecu_serial)
    get_all_ecu_manifests_from_vehicle(vin)

"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open

import uptane # Import before TUF modules; may change tuf.conf values.
import uptane.formats
import tuf

# Global dictionaries
vehicle_manifests = {}
ecu_manifests = {}
primary_ecus_by_vin = {}
ecus_by_vin = {}
ecu_public_keys = {}


def get_ecu_public_key(ecu_serial):
  """
  Returns the public key that a particular ECU was registered with.

  <Exceptions>
    uptane.FormatError
      if ecu_serial is not a valid ecu_serial per
      uptane.formats.ECU_SERIAL_SCHEMA

    uptane.UnknownECU
      if the given ECU Serial has not been registered with a public key
  """

  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)

  if ecu_serial not in ecu_public_keys:
    raise uptane.UnknownECU('The given ECU Serial, ' + repr(ecu_serial) +
        ' is not known. It must be registered.')

  return ecu_public_keys[ecu_serial]





def get_vehicle_manifests(vin):
  check_vin_registered(vin)
  return vehicle_manifests[vin]





def get_last_vehicle_manifest(vin):
  check_vin_registered(vin)
  if not vehicle_manifests[vin]:
    return None
  else:
    return vehicle_manifests[vin][-1]





def get_ecu_manifests(ecu_serial):
  check_ecu_registered(ecu_serial)
  return ecu_manifests[ecu_serial]





def get_last_ecu_manifest(ecu_serial):
  check_ecu_registered(ecu_serial)
  if not ecu_manifests[ecu_serial]:
    return None
  else:
    return ecu_manifests[ecu_serial][-1]




def save_vehicle_manifest(vin, signed_vehicle_manifest):
  """
  Given a manifest of form
  uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA, save it in an index
  by vin, and save the individual ecu attestations in an index by ecu serial.
  """
  check_vin_registered(vin) # check arg format and registration

  uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
       signed_vehicle_manifest)

  vehicle_manifests[vin].append(signed_vehicle_manifest)


  # Not doing it this way because the Director is going to pass through a
  # correctly-signed vehicle manifest even if some of the ECU Manifests within
  # it are *not* correctly signed. The Director will instead issue a
  # save_ecu_manifest call for each validly-signed ECU Manifest.
  # # Save all the contained ECU manifests.
  # all_contained_ecu_manifests = signed_vehicle_manifest['signed'][
  #     'ecu_version_manifests']

  # for ecu_serial in all_contained_ecu_manifests:
  #   for signed_ecu_manifest in all_contained_ecu_manifests[ecu_serial]:
  #     save_ecu_manifest(ecu_serial, signed_ecu_manifest)





def get_all_ecu_manifests_from_vehicle(vin):
  """
  Returns a dictionary of lists of manifests, indexed by the ECU Serial of each
  ECU associated with the given VIN. (This is the same format as the
  ecu_manifests global, but only includes those ECUs associated with the
  vehicle.)

  e.g.
    {'ecuserial1': [<ecumanifest>, <ecumanifest>],
     'ecuserial9': []}
  """

  check_vin_registered(vin) # check arg format and registration

  ecus_in_vehicle = ecus_by_vin[vin]

  return {serial: ecu_manifests[serial] for serial in ecus_in_vehicle}





def save_ecu_manifest(vin, ecu_serial, signed_ecu_manifest):

  check_ecu_registered(ecu_serial) # check format and registration

  uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
       signed_ecu_manifest)

  ecu_manifests[ecu_serial].append(signed_ecu_manifest)





def register_ecu(is_primary, vin, ecu_serial, public_key, overwrite=True):
  """
  Registers the ECU with the given ECU Serial, saving its public key, making
  note of the vehicle with which it is associated, and, if is_primary is True,
  marks it as the Primary ECU for the vehicle.

  Also registers the given VIN if it was not previously known (creating
  appropriate entries in the global dictionaries).

  If overwrite is False:
    if it is given an already-known ECU Serial, or if is_primary is True and
    the given VIN is already associated with a Primary ECU, raises an
    uptane.Spoofing exception.

  If overwrite is True:
    if given an already-known ECU Serial, will overwrite the previously
    registered public key and delete existing ECU Manifests for that ECU Serial.
    if given an already-known VIN that is already associated with a Primary
    ECU, it will associate the new ECU as the VIN's Primary.
    This can orphan previously-Primary ECUs:
    If a new ECU is registered as the Primary for a known vehicle that already
    had a Primary, the old Primary ECU will still be kept as a known ECU,
    along with all its ECU Manifests, and its association with the VIN is not
    removed, but it is no longer marked as the Primary for that VIN.

  Will not add the same ECU Serial to a vehicle's list of ECUs
  (ecus_by_vin[vin]) twice.
  """

  tuf.formats.BOOLEAN_SCHEMA.check_match(is_primary)
  uptane.formats.VIN_SCHEMA.check_match(vin)
  uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
  tuf.formats.ANYKEY_SCHEMA.check_match(public_key)

  assert (ecu_serial in ecu_public_keys) == (ecu_serial in ecu_manifests), \
      'Programming error: ECU registration is not consistent.'

  if not overwrite:

    # If we aren't supposed to be overwriting public keys or Primary
    # associations, make sure we don't.

    if is_primary and vin in primary_ecus_by_vin and \
        primary_ecus_by_vin[vin] is not None:
      raise uptane.Spoofing('The given VIN, ' + repr(vin) + ', is already '
          'associated with a Primary ECU.')

    if ecu_serial in ecu_public_keys:

      # Demo website hack.
      # TODO: Get rid of this hack and resume raising the Spoofing error.
      print('The given ECU Serial, ' + repr(ecu_serial) +
          ', is already associated with a public key.')
      return

      # raise uptane.Spoofing('The given ECU Serial, ' + repr(ecu_serial) +
      #     ', is already associated with a public key.')


  # Register the VIN if it is unknown.
  # No VIN should ever be in only one or the other of ecus_by_vin or
  # vehicle_manifests, or there is a bug.
  if vin not in ecus_by_vin:
    register_vehicle(vin, overwrite=overwrite)


  # Associate the ECU with the vehicle.
  if ecu_serial not in ecus_by_vin[vin]:
    ecus_by_vin[vin].append(ecu_serial)

  if is_primary:
    # Set the ECU as the vehicle's Primary ECU.
    primary_ecus_by_vin[vin] = ecu_serial


  # Save the ECU's public key.
  ecu_public_keys[ecu_serial] = public_key


  # Create an entry in the ecu_manifests dictionary for future manifests from
  # the ECU.
  ecu_manifests[ecu_serial] = []





def register_vehicle(vin, primary_ecu_serial=None, overwrite=True):

  _check_registration_is_sane(vin)

  if not overwrite and vin in ecus_by_vin:
    raise uptane.Spoofing('The given VIN, ' + repr(vin) + ', is already '
        'registered.')

  ecus_by_vin[vin] = []
  vehicle_manifests[vin] = []
  primary_ecus_by_vin[vin] = primary_ecu_serial






def check_vin_registered(vin):

  _check_registration_is_sane(vin)

  if vin not in vehicle_manifests:
    # TODO: Should we also log here? Review logging before exceptions
    # throughout the reference implementation.
    raise uptane.UnknownVehicle('The given VIN, ' + repr(vin) + ', is not '
        'known.')





def _check_registration_is_sane(vin):
  """
  Asserts that a data structure invariant remains correct. A vehicle must be
  in all three of the relevant global dictionaries if it is registered, and in
  none of them if it is not.
  """

  uptane.formats.VIN_SCHEMA.check_match(vin)

  # # A VIN may be in either none or all three of these dictionaries, and nowhere
  # # in between, or there is a bug.
  # if vin in vehicle_manifests != vin in ecus_by_vin or vin in ecus_by_vin != \
  #     vin in primary_ecus_by_vin:

  assert (vin in vehicle_manifests) == (vin in ecus_by_vin) == (
      vin in primary_ecus_by_vin), 'Programming error.'





def check_ecu_registered(ecu_serial):

  if ecu_serial not in ecu_public_keys:
    raise uptane.UnknownECU('The given ECU serial, ' + repr(ecu_serial) +
        ', is not known.')
