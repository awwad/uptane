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

import os

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

    ecus_by_vin
      A dictionary mapping VIN - the identifier for a known vehicle for
      which this is responsible - to a list of ECU Serials associated with that
      vehicle.
      This is used to both identify known VINs and associate ECUs with VINs.
      Identifying known ECUs is generally done instead by checking the
      ecu_public_keys field, since that is flat.
      A dictionary of lists of ECU Serials, indexed by VIN.
      e.g.:
          {'vin111': ['ecuserial12345', 'ecuserial6789'],
           'vin112': ['serialabc', 'serialdef']}

    key_dirroot_pri
      Private signing key for the root role in the Director's repositories

    key_dirtime_pri
      Private signing key for the timestamp role in the Director's repositories

    key_dirsnap_pri
      Private signing key for the snapshot role in the Director's repositories

    key_dirtarg_pri
      Private signing key for the targets role in the Director's repositories

    vehicle_repositories
      A dictionary of tuf.repository_tool.Repository objects, indexed by VIN.
      Each holds the Director metadata geared toward that particular vehicle.

    director_repos_dir
      The root directory in which the repositories for each vehicle reside.

  """


  def __init__(self,
    director_repos_dir,
    key_root_pri,
    key_root_pub,
    key_timestamp_pri,
    key_timestamp_pub,
    key_snapshot_pri,
    key_snapshot_pub,
    key_targets_pri,
    key_targets_pub,
    ecu_public_keys=dict(),
    ecus_by_vin=dict()):

    # TODO: Consider allowing multiple keys per role for the Director.
    # github.com/awwad/uptane/issues/20

    # if inventorydb is None:
    #   inventorydb = json.load()
    # self.inventorydb = {}

    tuf.formats.RELPATH_SCHEMA.check_match(director_repos_dir)

    for key in [
        key_root_pri, key_root_pub, key_timestamp_pri, key_timestamp_pub,
        key_snapshot_pri, key_snapshot_pub, key_targets_pri, key_targets_pub]:
      tuf.formats.ANYKEY_SCHEMA.check_match(key)

    for key in ecu_public_keys:
      tuf.formats.ANYKEY_SCHEMA.check_match(key)

    self.director_repos_dir = director_repos_dir

    self.key_dirroot_pri = key_root_pri
    self.key_dirroot_pub = key_root_pub
    self.key_dirtime_pri = key_timestamp_pri
    self.key_dirtime_pub = key_timestamp_pub
    self.key_dirsnap_pri = key_snapshot_pri
    self.key_dirsnap_pub = key_snapshot_pub
    self.key_dirtarg_pri = key_targets_pri
    self.key_dirtarg_pub = key_targets_pub

    self.ecu_public_keys = ecu_public_keys

    self.vehicle_repositories = dict()
    self.ecus_by_vin = dict() # This will be populated with ecus_by_vin shortly.
    for vin in ecus_by_vin:
      uptane.formats.VIN_SCHEMA.check_match(vin)
      self.add_new_vehicle(vin, ecus_by_vin[vin])






  def register_ecu_serial(self, ecu_serial, ecu_key, vin):
    """
    Set the expected public key for signed messages from the ECU with the given
    ECU Serial. If signed messages purportedly coming from the ECU with that
    ECU Serial are not signed by the given key, they will not be trusted.

    This also associates the ECU Serial with the given VIN, so that the
    Director will treat this ECU as part of that vehicle.

    Exceptions
      uptane.UnknownVehicle
        if the VIN is not known.

      uptane.Spoofing
        if the given ECU Serial already has a registered public key.
        (That is, this public method is not how you should replace the public
        key a given ECU uses.)

      uptane.FormatError or tuf.FormatError
        if the arguments do not fit the correct format.
    """
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    tuf.formats.ANYKEY_SCHEMA.check_match(ecu_key)

    if vin not in self.ecus_by_vin:
      # TODO: Should we also log here? Review logging before exceptions
      # throughout the reference implementation.
      raise uptane.UnknownVehicle('The given VIN does not correspond to a '
          'vehicle known to this Director.')

    elif ecu_serial in self.ecu_public_keys:
      log.error(YELLOW + 'Rejecting an attempt to register a public key to an '
          'ECU Serial when that ECU Serial already has a public key registered '
          'to it.' + ENDCOLORS)
      raise uptane.Spoofing('This ecu_serial has already been registered. '
          'Rejecting registration request.')

    else:
      assert ecu_serial not in self.ecus_by_vin[vin], 'Programming error: ' + \
          'The given ECU Serial was not in ecu_public_keys but WAS in ' + \
          'ecus_by_vin. That should not be possible.'

      # Register the public key.
      self.ecu_public_keys[ecu_serial] = ecu_key

      # Associate this ECU with the given VIN's vehicle.
      self.ecus_by_vin[vin].append(ecu_serial)

      log.info(
          GREEN + 'Registered a new ECU, ' + repr(ecu_serial) + ' in '
          'vehicle ' + repr(vin) + ' with ECU public key: ' + repr(ecu_key) +
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

        tuf.BadSignatureError
          if the Primary's signature on the vehicle manifest is invalid
          (An individual Secondary's signature on an ECU Version Manifests
          being invalid does not raise an exception, but instead results in
          a warning and that ECU Version Manifest alone being discarded.)

        uptane.Spoofing
          if the primary_ecu_serial argument does not match the ECU Serial
          for the Primary in the signed Vehicle Version Manifest.
          (As above, an ECU Version Manifest that is wrong in this respect is
          individually discarded with only a warning.)

        uptane.UnknownECU
          if the ECU Serial provided for the Primary is not known to this
          Director.
          (As above, an unknown Secondary ECU in an ECU Version Manifest is
          individually discarded with only a warning.)

        uptane.UnknownVehicle
          if the VIN provided is not known to this Director

    """
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(primary_ecu_serial)
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        signed_vehicle_manifest)

    if vin not in self.ecus_by_vin:
      raise uptane.UnknownVehicle('Recieved a vehicle manifest purportedly '
          'from a vehicle with a VIN that is not known to this Director.')

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





  def add_new_vehicle(self, vin, ecu_serials=[]):
    """
    For adding vehicles whose VINs were not provided when this object was
    initialized.

    Note that individual ECUs should also be registered, providing their
    public keys.

    """
    # TODO: The VIN string is manipulated for create_director_repo_for_vehicle,
    # but the string is not manipulated for this addition to ecus_by_vin.
    # Treatment has to be made consistent. (In particular, things like slashes
    # are pruned - or an error is raised when they are detected.)
    uptane.formats.VIN_SCHEMA.check_match(vin)

    for serial in ecu_serials:
      uptane.formats.ECU_SERIAL_SCHEMA.check_match(serial)

    self.ecus_by_vin[vin] = ecu_serials

    self.create_director_repo_for_vehicle(vin)





  def create_director_repo_for_vehicle(self, vin):
    """
    Creates a separate repository object for a given vehicle identifier.
    Each uses the same keys.
    Ideally, each would use the same root.json file, but that will have to
    wait until TUF Augmentation Proposal 5 (when the hash of root.json ceases
    to be included in snapshot.json).

    The name of each repository is the VIN string.

    If the repository already exists, it is overwritten.

    Usage:

      d = uptane.services.director.Director(...)
      d.create_director_repo_for_vehicle(vin)
      d.add_target_for_ecu(vin, ecu, target_filepath)

    These repository objects can be manipulated as described in TUF
    documentation; for example, to produce metadata files afterwards for that
    vehicle:
      d.vehicle_repositories[vin].write()


    # TODO: This may be outside of the scope of the reference implementation,
    # and best to put in the demo code. It's not clear what should live in the
    # reference implementation itself for this....

    """

    uptane.formats.VIN_SCHEMA.check_match(vin)

    # Repository Tool expects to use the current directory.
    # Figure out if this is impactful and needs to be changed.
    os.chdir(self.director_repos_dir) # <~> Check to see if this edit was finished.

    # Generates absolute path for a subdirectory with name equal to vin,
    # in the current directory, making (relatively) sure that there isn't
    # anything suspect like "../" in the VIN.
    # Then I strip the common prefix back off the absolute path to get a
    # relative path and keep the guarantees.
    # TODO: Clumsy and hacky; fix.
    vin = inventorydb.scrub_filename(vin, self.director_repos_dir)
    vin = os.path.relpath(vin, self.director_repos_dir)

    self.vehicle_repositories[vin] = this_repo = rt.create_new_repository(
        vin, repository_name=vin)


    this_repo.root.add_verification_key(self.key_dirroot_pub)
    this_repo.timestamp.add_verification_key(self.key_dirtime_pub)
    this_repo.snapshot.add_verification_key(self.key_dirsnap_pub)
    this_repo.targets.add_verification_key(self.key_dirtarg_pub)
    this_repo.root.load_signing_key(self.key_dirroot_pri)
    this_repo.timestamp.load_signing_key(self.key_dirtime_pri)
    this_repo.snapshot.load_signing_key(self.key_dirsnap_pri)
    this_repo.targets.load_signing_key(self.key_dirtarg_pri)





  def add_target_for_ecu(self, vin, ecu_serial, target_filepath):
    """
    Add a target to the repository for a vehicle, marked as being for a
    specific ECU.

    The target file at the provided path will be analyzed, and its hashes
    and file length will be saved in target metadata in memory, which will then
    be signed with the appropriate Director keys and written to disk when the
    "write" method is called on the vehicle repository.
    """
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    tuf.formats.RELPATH_SCHEMA.check_match(target_filepath)

    if vin not in self.vehicle_repositories:
      raise uptane.UnknownVehicle('The VIN provided, ' + repr(vin) + ' is not '
          'that of a vehicle known to this Director.')

    elif ecu_serial not in self.ecu_public_keys:
      raise uptane.UnknownECU('The ECU Serial provided, ' + repr(ecu_serial) +
          ' is not that of an ECU known to this Director.')

    self.vehicle_repositories[vin].targets.add_target(
        target_filepath, custom={'ecu_serial': ecu_serial})





  def analyze_vehicle(self, vin):
    """
    Make note of any unusual properties of the vehicle data and manifests.
    For example, try to detect freeze attacks and mix-and-match attacks.
    """
    pass




