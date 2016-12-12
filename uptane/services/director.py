"""
<Program Name>
  director.py

<Purpose>
  A core module that provides needed functionality for an Uptane-compliant
  Director. This CAN remain largely unchanged in real use. It is upon this that
  a full director is built to OEM specifications. A sample of such a Director
  is in demo_director_svc.py.

  Fundamentally, this code translates lists of vehicle software assignments
  (roughly mapping ECU IDs to targets) into signed metadata suitable for sending
  to a vehicle.

  In particular, this code supports:

    - Initialization of a director given vehicle info, ECU info, ECU public
      keys, Director private keys, etc.

    - Registration of new ECUs, given serial and public key

    - Validation of ECU manifests, supporting BER

    - Validation of ECU manifests, supporting BER

    - Writing of BER-encoded signed targets metadata for a given vehicle, given
      as input a map of ecu serials to target info (or filenames from which to
      extract target info), including BER encoding

"""
from __future__ import unicode_literals

import uptane
import uptane.formats
import uptane.services.inventorydb as inventorydb
import tuf
import tuf.formats
import tuf.repository_tool as rt
#import asn1_conversion as asn1
from uptane import GREEN, RED, YELLOW, ENDCOLORS

from six.moves import getcwd

log = uptane.logging.getLogger('director')
log.addHandler(uptane.file_handler)
log.addHandler(uptane.console_handler)
log.setLevel(uptane.logging.DEBUG)



class Director:
  """
  See file's docstring.

  Fields:
    ecu_public_keys
      A dictionary mapping ECU_SERIAL (uptane.formats.ECU_SERIAL_SCHEMA) to
      the public key for that ECU (tuf.formats.ANYKEY_SCHEMA) for each ECU that
      the Director knows about

    key_dirroot_pri
      Private signing key for the root role in the Director's repositories

    key_dirtime_pri
      Private signing key for the timestamp role in the Director's repositories

    key_dirsnap_pri
      Private signing key for the snapshot role in the Director's repositories

    key_dirtarg_pri
      Private signing key for the targets role in the Director's repositories

  """


  def __init__(self,
    #inventorydb = None,
    key_root,
    key_timestamp,
    key_snapshot,
    key_targets,
    ecu_public_keys=dict()):
    # if inventorydb is None:
    #   inventorydb = json.load()
    # self.inventorydb = {}

    self.key_dirroot_pri = key_root
    self.key_dirtime_pri = key_timestamp
    self.key_dirsnap_pri = key_snapshot
    self.key_dirtarg_pri = key_targets

    self.ecu_public_keys = ecu_public_keys





  def register_ecu_serial(self, ecu_serial, ecu_key):
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    tuf.formats.ANYKEY_SCHEMA.check_match(ecu_key)

    if ecu_serial in self.ecu_public_keys:
      log.error(RED + 'Rejecting an attempt to register a public key to an ECU '
          'Serial when that ECU Serial already has a public key registered to '
          'it.' + ENDCOLORS)
      raise uptane.Spoofing('This ecu_serial has already been registered. '
          'Rejecting registration request.')

    else:
      self.ecu_public_keys[ecu_serial] = ecu_key
      log.info(
          GREEN + ' Registered a new ECU:\n    ECU Serial: ' +
          repr(ecu_serial) + '\n    ECU Key: ' + repr(ecu_key) + '\n' +
          ENDCOLORS)





  def validate_ecu_manifest(self, ecu_serial, signed_ecu_manifest):
    """
    Arguments:
      ecuid: uptane.formats.ECU_SERIAL_SCHEMA
      manifest: uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA
    """
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)

    # If it doesn't match expectations, error out here.

    if ecu_serial != signed_ecu_manifest['signed']['ecu_serial']:
      raise uptane.Spoofing('Received a spoofed or mistaken manifest: supposed '
          'origin ECU (' + repr(ecu_serial) + ') is not the same as what is '
          'signed in the manifest itself (' +
          repr(signed_ecu_manifest['signed']['ecu_serial']) + ').')

    # TODO: Consider mechanism for fetching keys from inventorydb itself,
    # rather than always registering them after Director svc starts up.
    if ecu_serial not in self.ecu_public_keys:
      log.info(
          'Validation failed on an ECU Manifest: ECU ' + repr(ecu_serial) +
          ' is not registered.')
      # Raise a fault for the offending ECU's XMLRPC request.
      raise uptane.UnknownECU('The Director is not aware of the given ECU '
          'SERIAL (' + repr(ecu_serial) + '. Manifest rejected. If the ECU is '
          'new, Register the new ECU with its key in order to be able to '
          'submit its manifests.')

    ecu_public_key = self.ecu_public_keys[ecu_serial]

    valid = tuf.keys.verify_signature(
        ecu_public_key,
        signed_ecu_manifest['signatures'][0], # TODO: Fix assumptions.
        signed_ecu_manifest['signed'])

    if not valid:
      log.info(
          'Validation failed on an ECU Manifest: signature is not valid. It'
          'It must be correctly signed by the expected key for that ECU.')
      # Raise a fault for the offending ECU's XMLRPC request.
      raise tuf.BadSignatureError('Sender supplied an invalid signature. '
          'ECU Manifest is unacceptable. If you see this persistently, it is '
          'possible that the Primary is compromised or that there is a man in '
          'the middle attack or misconfiguration.')





  def register_vehicle_manifest(
      self, vin, primary_ecu_serial, signed_vehicle_manifest):
    """
    Saves the vehicle manifest in the InventoryDB, validating first the
    Primary's key on the full vehicle manifest, then each individual ECU
    Manifest's signature.

    If the Primary's signature over the whole Vehicle Manifest is invalid, then
    this raises an error (either tuf.BadSignatureError, uptane.Spoofing, or
    uptane.UnknownECU).

    Otherwise, if any of the individual ECU Manifests are invalid, those
    individual ECU Manifests are discarded, and others are processed. (No
    error is raised - only a warning.)

    Arguments:
      vin: vehicle's unique identifier, uptane.formats.VIN_SCHEMA
      primary_ecu_serial: Primary ECU's unique identifier,
                          uptane.formats.ECU_SERIAL_SCHEMA
      manifest: the vehicle manifest, as specified in the implementation
                specification and compliant with
                uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA

    Exceptions:
      If the Primary's signature on the vehicle manifest is invalid or the
      listed Primary ECU's serial is not recognized, raises one of the following
      as appropriate:
        tuf.BadSignatureError
        uptane.Spoofing
        uptane.UnknownECU
    """
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        signed_vehicle_manifest)

    # Process Primary's signature on full manifest here.
    # If it doesn't match expectations, error out here.
    self.validate_primary_certification_in_vehicle_manifest(
        vin, primary_ecu_serial, signed_vehicle_manifest)

    # If the Primary's signature is valid, save the whole vehicle manifest to
    # the inventorydb.
    inventorydb.save_vehicle_manifest(vin, signed_vehicle_manifest)

    log.info(GREEN + ' Received a Vehicle Manifest from Primary ECU ' +
        repr(primary_ecu_serial) + ', with a valid signature from that ECU.' +
        ENDCOLORS)
    # TODO: Note that the above hasn't checked that the signature was from
    # a Primary, just from an ECU. Fix.


    # Validate signatures on and register all individual ECU manifests for each
    # ECU (may have multiple manifests per ECU).
    all_ecu_manifests = \
        signed_vehicle_manifest['signed']['ecu_version_manifests']

    for ecu_serial in all_ecu_manifests:
      ecu_manifests = all_ecu_manifests[ecu_serial]
      for manifest in ecu_manifests:
        try:
          # This calls validate_ecu_manifest and raises appropriate errors,
          # caught below.
          self.register_ecu_manifest(vin, ecu_serial, manifest)
        except uptane.Spoofing as e:
          log.warning(
              RED + 'Discarding a spoofed or malformed ECU Manifest. Error '
              ' from validating that ECU manifest follows:\n' + ENDCOLORS +
              repr(e))
        except uptane.UnknownECU as e:
          log.warning(
              RED + 'Discarding an ECU Manifest from unknown ECU. Error from '
              'validation attempt follows:\n' + ENDCOLORS + repr(e))
        except tuf.BadSignatureError as e:
          log.warning(
              RED + 'Rejecting an ECU Manifest whose signature is invalid, '
              'from within an otherwise valid Vehicle Manifest. Error from '
              'validation attempt follows:\n' + ENDCOLORS + repr(e))





  def validate_primary_certification_in_vehicle_manifest(
      self, vin, primary_ecu_serial, vehicle_manifest):
    """
    Check the Primary's signature on the Vehicle Manifest and any other data
    the Primary is certifying, without diving into the individual ECU Manifests
    in the Vehicle Manifest.

    Raises an exception if there is an issue with the Primary's signature.
    No return value.
    """
    # If args don't match expectations, error out here.
    log.info('Beginning validate_primary_certification_in_vehicle_manifest')
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(primary_ecu_serial)
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        vehicle_manifest)


    if primary_ecu_serial != vehicle_manifest['signed']['primary_ecu_serial']:
      raise uptane.Spoofing('Received a spoofed or mistaken vehicle manifest: '
          'the supposed origin Primary ECU (' + repr(primary_ecu_serial) + ') '
          'is not the same as what is signed in the vehicle manifest itself ' +
          '(' + repr(vehicle_manifest['signed']['primary_ecu_serial']) + ').')

    # TODO: Consider mechanism for fetching keys from inventorydb itself,
    # rather than always registering them after Director svc starts up.
    if primary_ecu_serial not in self.ecu_public_keys:
      log.debug(
          'Rejecting a vehicle manifest from a Primary ECU whose '
          'key is not registered.')
      # Raise a fault for the offending ECU's XMLRPC request.
      raise uptane.UnknownECU('The Director is not aware of the given Primary '
          'ECU Serial (' + repr(primary_ecu_serial) + '. Manifest rejected. If '
          'the ECU is new, Register the new ECU with its key in order to be '
          'able to submit its manifests.')

    ecu_public_key = self.ecu_public_keys[primary_ecu_serial]

    valid = tuf.keys.verify_signature(
        ecu_public_key,
        vehicle_manifest['signatures'][0], # TODO: Fix assumptions.
        vehicle_manifest['signed'])

    if not valid:
      log.debug(
          'Rejecting a vehicle manifest because the Primary signature on it is '
          'not valid.It must be correctly signed by the expected Primary ECU '
          'key.')
      # Raise a fault for the offending ECU's XMLRPC request.
      raise tuf.BadSignatureError('Sender supplied an invalid signature. '
          'Vehicle Manifest is questionable; discarding. If you see this '
          'persistently, it is possible that there is a man in the middle '
          'attack or misconfiguration.')





  # This is called by the primary through an XMLRPC interface, currently.
  # It will later become unnecessary, as we will only save ecu manifests when
  # saving vehicle manifests.
  def register_ecu_manifest(self, vin, ecu_serial, signed_ecu_manifest):
    """
    """
    # Error out if the signature isn't valid and from the expected party.
    # Also checks argument format.
    self.validate_ecu_manifest(ecu_serial, signed_ecu_manifest)

    # Otherwise, we save it:
    inventorydb.save_ecu_manifest(vin, ecu_serial, signed_ecu_manifest)

    log.debug('Stored a valid ECU manifest from ECU ' + repr(ecu_serial))

    # Alert if there's been a detected attack.
    if signed_ecu_manifest['signed']['attacks_detected']:
      log.warning(
          YELLOW + 'Attacks have been reported by the Secondary ECU ' +
          repr(ecu_serial) + ':\n' +
          signed_ecu_manifest['signed']['attacks_detected'] + ENDCOLORS)



  # Replacing this: don't need separate validate and register calls for
  # vehicle manifests: it's too redundant and not useful enough.
  # # This is called by the primary through an XMLRPC interface, currently.
  # def register_vehicle_manifest(self,
  #     vin, primary_ecu_serial, signed_vehicle_manifest):

  #   # Check argument format.
  #   uptane.formats.VIN_SCHEMA.check_match(vin)
  #   uptane.formats.ECU_SERIAL_SCHEMA.check_match(primary_ecu_serial)

  #   # Error out if the signature isn't valid and from the expected party.
  #   # This call also checks argument format.
  #   self.validate_vehicle_manifest(
  #       vin, primary_ecu_serial, signed_vehicle_manifest)

  #   inventorydb.save_vehicle_manifest(vin, signed_vehicle_manifest)





  def choose_targets_for_vehicle(self, vin):
    """
    Returns a dictionary of target lists, indexed by ECU IDs.

      targets = {
        "ECUID2": [<target_21>],
        "ECUID5": [<target_51>, <target53>],
        ...
      }
      where <target*> is an object conforming to tuf.formats.TARGETFILE_SCHEMA
      and ECUIDs conform to uptane.formats.ECU_SERIAL_SCHEMA.
    """

    # Check the vehicle manifest(s) / data for anything alarming.
    # analyze_vehicle(self, vin)

    # Load the vehicle's repository.



    # ELECT TARGETS HERE.




    # Update the targets in the vehicle's repository
    # vehiclerepo.targets.add_target(...)

    # Write the metadata for this vehicle.
    # vehiclerepo.write()

    # Move the new metadata to the live repo...?
    # Or send straightaway?



  def create_director_repo_for_vehicle(self, vin):
    """
    """
    WORKING_DIR = getcwd()
    MAIN_REPO_DIR = os.path.join(WORKING_DIR, 'repomain')
    DIRECTOR_REPO_DIR = os.path.join(WORKING_DIR, 'repodirector')
    TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
    # DIRECTOR_REPO_HOST = 'http://localhost'
    # DIRECTOR_REPO_PORT = 30301

    vin = inventorydb.scrub_filename(vin, WORKING_DIR)

    self.repositories[vin] = rt.create_new_repository('repodirector_' + 'vin')

    repodirector.root.add_verification_key(self.key_dirroot_pub)
    repodirector.timestamp.add_verification_key(self.key_dirtime_pub)
    repodirector.snapshot.add_verification_key(self.key_dirsnap_pub)
    repodirector.targets.add_verification_key(self.key_dirtarg_pub)
    repodirector.root.load_signing_key(self.key_dirroot_pri)
    repodirector.timestamp.load_signing_key(self.key_dirtime_pri)
    repodirector.snapshot.load_signing_key(self.key_dirsnap_pri)
    repodirector.targets.load_signing_key(self.key_dirtarg_pri)

    # TODO: <~> Continue when course is decided. This may be outside of the
    # scope of the reference implementation, and best to put in the demo code.





  def analyze_vehicle(self, vin):
    """
    Make note of any unusual properties of the vehicle data and manifests.
    For example, try to detect freeze attacks and mix-and-match attacks.
    """
    pass





  def write_metadata(self):
    raise NotImplementedError('Not yet written.')
    # Perform repo.write() on repo for the vehicle.

    #   def write_director_metadata(self, vehicle_software_assignments):

    #     uptane.formats.VEHICLE_SOFTWARE_ASSIGNMENTS_SCHEMA.check_match(
    #         vehicle_software_assignments) # Check argument.

    #     #repo = tuf.repository_tool.load_repo(   )

    #     # load director keys only (grab code from uptane_tuf_server.py)
    #     # Call repository_tool internal functions to produce metadata
    #     # file.  /:  Ugly.
    #     #
