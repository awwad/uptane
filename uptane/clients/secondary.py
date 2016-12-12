"""
<Program Name>
  secondary.py

<Purpose>
  A module providing functionality for an Uptane Secondary ECU client
  performing full metadata verification, as would be performed during ECU boot.
  Also includes some partial verification functionality.

"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open

import uptane
import uptane.formats
import uptane.ber_encoder as ber_encoder
import uptane.common

import tuf.client.updater
import tuf.formats
import tuf.keys
import tuf.repository_tool as rt

import os # For paths and makedirs
import shutil # For copyfile
import random # for nonces
import zipfile # to expand the metadata archive retrieved from the Primary
from uptane import GREEN, RED, YELLOW, ENDCOLORS


log = uptane.logging.getLogger('secondary')
log.addHandler(uptane.file_handler)
log.addHandler(uptane.console_handler)
log.setLevel(uptane.logging.DEBUG)



class Secondary(object):

  """
  Fields:

    self.updater:
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the Director and Supplier repositories.

    self.full_client_dir:
      The full path of the directory where all client data is stored for this
      secondary.

    self.timeserver_public_key:
      The key we expect the timeserver to use.

    self.partial_verifying:
      True if this instance is a partial verifier, False if it employs full
      metadata verification.

    self.director_public_key
      If this is a partial verification secondary, we store the key that we
      expect the Director to use here. Full verification clients should have
      None in this field.

    self.attacks_detected
      A string representing whatever attacks the secondary wishes to alert the
      Director about. Empty string indicates no alerts.

    self.ecu_key:
      The signing key this ECU will use to sign manifests.

    self.firmware_fileinfo:
        The image the ecu is currently using, identified by filename in the
        repo, hash of the file, and file size. This is an object matching
        tuf.formats.TARGETFILE_SCHEMA

    self.nonce_next
      Next nonce the ECU will send to the Timeserver (via the Primary).

    self.last_nonce_sent
      The latest nonce this ECU sent to the Timeserver (via the Primary).

    all_valid_timeserver_times:
      A list of all times extracted from all Timeserver attestations that have
      been validated by validate_time_attestation.
      Items are appended to the end.


  Methods, as called: ("self" arguments excluded):

    __init__(...)

    Nonce handling:
      set_nonce_as_sent()
      change_nonce()
      _create_nonce()

    Manifest handling:
      generate_signed_ecu_manifest()

    Metadata handling and validation of metadata and data
      validate_time_attestation(timeserver_attestation)
      process_metadata(metadata_archive_fname)
      _expand_metadata_archive(metadata_archive_fname)
      fully_validate_metadata()
      get_validated_target_info(target_filepath)
      validate_image(image_fname)



  """

  def __init__(
    self,
    full_client_dir,
    director_repo_name, # e.g. 'director'; value must appear in pinning file
    vin,
    ecu_serial,
    ecu_key,
    time,
    timeserver_public_key,
    firmware_fileinfo=None,
    director_public_key=None,
    partial_verifying=False):

    # Check arguments:
    tuf.formats.PATH_SCHEMA.check_match(full_client_dir)
    tuf.formats.PATH_SCHEMA.check_match(director_repo_name)
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(time)
    for key in [timeserver_public_key, director_public_key]:
      if key is not None:
        tuf.formats.ANYKEY_SCHEMA.check_match(key)

    self.director_repo_name = director_repo_name
    self.ecu_key = ecu_key
    self.vin = vin
    self.ecu_serial = ecu_serial
    self.full_client_dir = full_client_dir
    self.director_proxy = None
    self.timeserver_public_key = timeserver_public_key
    self.director_public_key = director_public_key
    self.partial_verifying = partial_verifying
    self.attacks_detected = ''
    self.firmware_fileinfo = firmware_fileinfo

    if not self.partial_verifying and self.director_public_key is not None:
      raise uptane.Error('Secondary not set as partial verifying, but a director ' # TODO: Choose error class.
          'key was still provided. Full verification secondaries employ the '
          'normal TUF verifications rooted at root metadata files.')


    # Create a TAP-4-compliant updater object. This will read pinning.json
    # and create single-repository updaters within it to handle connections to
    # each repository.
    self.updater = tuf.client.updater.Updater('updater')

    # We load the given time twice for simplicity in later code.
    self.all_valid_timeserver_times = [time, time]

    self.last_nonce_sent = None
    self.nonce_next = self._create_nonce()





  def set_nonce_as_sent(self):
    """
    To be called when the ECU Version Manifest is submitted, as that
    includes the sending of this nonce.
    """
    self.last_nonce_sent = self.nonce_next





  def change_nonce(self):
    """
    To be called only when a timeserver attestation is validated, when we
    know this nonce has been used.
    """
    self.nonce_next = self._create_nonce()





  def _create_nonce(self):
    """Returns a pseudorandom number for use in protecting from replay attacks
    from the timeserver (or an intervening party)."""
    return random.randint(
        uptane.formats.NONCE_LOWER_BOUND, uptane.formats.NONCE_UPPER_BOUND)





  def generate_signed_ecu_manifest(self):
    """
    Returns a signed ECU manifest indicating self.firmware_fileinfo,
    encoded in BER (requires code added to two ber_* functions below).
    """

    # We'll construct a signed signable_ecu_manifest_SCHEMA from the
    # targetinfo.
    # First, construct and check an ECU_VERSION_MANIFEST_SCHEMA.
    ecu_manifest = {
        'ecu_serial': self.ecu_serial,
        'installed_image': self.firmware_fileinfo,
        'timeserver_time': self.all_valid_timeserver_times[-1],
        'previous_timeserver_time': self.all_valid_timeserver_times[-2],
        'attacks_detected': self.attacks_detected
    }
    uptane.formats.ECU_VERSION_MANIFEST_SCHEMA.check_match(ecu_manifest)

    # Now we'll convert it into a signable object and sign it with a key we
    # generate.


    # TODO: Once the ber encoder functions are done, do this:
    original_ecu_manifest = ecu_manifest
    ecu_manifest = ber_encoder.ber_encode_ecu_manifest(ecu_manifest)

    # Wrap the ECU version manifest object into an
    # uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA and check the format.
    # {
    #     'signed': ecu_version_manifest,
    #     'signatures': []
    # }
    signable_ecu_manifest = tuf.formats.make_signable(ecu_manifest)
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signable_ecu_manifest)

    # Now sign with that key. (Also do ber encoding of the signed portion.)
    signed_ecu_manifest = uptane.common.sign_signable(
        signable_ecu_manifest, [self.ecu_key])
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)

    # TODO: Once the ber encoder functions are done, do this:
    original_signed_ecu_manifest = signed_ecu_manifest
    ber_encoded_signed_ecu_manifest = ber_encoder.ber_encode_signable_object(
        signed_ecu_manifest)

    return ber_encoded_signed_ecu_manifest





  def validate_time_attestation(self, timeserver_attestation):
    """
    Given a timeserver attestation, validate it and ensure that the nonce we
    expect it to contain is included.

    If validation is successful, switch to a new nonce for next time.
    """
    # Check format.
    uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
        timeserver_attestation)

    # Assume there's only one signature.
    assert len(timeserver_attestation['signatures']) == 1

    valid = tuf.keys.verify_signature(
        self.timeserver_public_key,
        timeserver_attestation['signatures'][0],
        timeserver_attestation['signed'])

    if not valid:
      raise tuf.BadSignatureError('Timeserver returned an invalid signature. '
          'Time is questionable, so not saved. If you see this persistently, '
          'it is possible that there is a Man in the Middle attack underway.')


    # If the most recent nonce we sent is not in the timeserver attestation,
    # then we don't trust the timeserver attestation.
    if self.last_nonce_sent is None:
      # This ECU is fresh and hasn't actually ever sent a nonce to the Primary
      # yet. It would be impossible to validate a timeserver attestation.
      log.warning(YELLOW + 'Cannot validate a timeserver attestation yet: '
          'this fresh Secondary ECU has never communicated a nonce and ECU '
          'Version Manifest to the Primary.' + ENDCOLORS)
      return

    elif self.last_nonce_sent not in timeserver_attestation['signed']['nonces']:
      # TODO: Create a new class for this Exception in this file.
      raise uptane.BadTimeAttestation('Primary provided a time attestation '
          'that did not include any of the nonces this Secondary has sent '
          'recently. This Secondary cannot trust the time provided and will '
          'not register it. Because of the asynchrony in the Primary-Secondary '
          'communications, this can happen occasionally. If this occurs '
          'repeatedly for a sustained amount of time, it is possible that the '
          'Primary is compromised or that there is a Man in the Middle attack '
          'underway between the vehicle and the servers, or within the '
          'vehicle.')
      # TODO: Determine whether or not to add something to self.attacks_detected
      # to indicate this problem. It's probably not certain enough? But perhaps
      # we should err on the side of reporting.

    # Extract actual time from the timeserver's signed attestation.
    new_timeserver_time = timeserver_attestation['signed']['time']

    # Save validated time.
    self.all_valid_timeserver_times.append(new_timeserver_time)

    # Use a new nonce next time, since the nonce we were using has now been
    # used to successfully validate a timeserver attestation.
    self.change_nonce()





  def fully_validate_metadata(self):
    """
    Treats the unvalidated metadata obtained from the Primary (which the
    Secondary does not fully trust) like a set of local TUF repositories,
    validating it against the older metadata this Secondary already has and
    already validated.

    All operations here are against the local files expected to be downloaded
    from the Primary, locations specified per pinned.json.

    Saves the validated, trustworthy target info as
    self.get_validated_target_info.

    Raises an exception if the role metadata itself cannot be validated. Does
    not raise an exception if some target file information indicated by the
    Director cannot be validated: instead, simply does not save that target
    file info as validated.


    For example, no exception is raised if:
      - All top-level role files are signed properly in each repository.
      - Target file A has custom fileinfo indicating the ECU Serial of the
        ECU for which it is intended, this ECU.

    Further, target info is saved for target A in
    self.validated_targets_for_this_ecu if Director and Supplier repositories
    indicate the same file info for targets A.

    If, target info would not be saved for target A if Director and Supplier
    repositories indicate different file info for target A.

    """

    # Refresh the top-level metadata first (all repositories).
    self.updater.refresh()

    validated_targets_for_this_ecu = []

    # Comb through the Director's direct instructions, picking out only the
    # target(s) earmarked for this ECU (by ECU Serial)
    for target in self.updater.targets_of_role(
        rolename='targets', repo_name=self.director_repo_name):

      # Ignore target info not marked as being for this ECU.
      if 'custom' not in target['fileinfo'] or \
          'ecu_serial' not in target['fileinfo']['custom'] or \
          self.ecu_serial != target['fileinfo']['custom']['ecu_serial']:
        continue

      # Fully validate the target info for our target(s).
      try:
        validated_targets_for_this_ecu.append(
            self.get_validated_target_info(target['filepath']))
      except tuf.UnknownTargetError:
        log.error(RED + 'Unable to validate target ' +
            repr(target['filepath']) + ', which the Director assigned to this '
            'Secondary ECU, using the validation rules in pinned.json' +
            ENDCOLORS)
        continue


    self.validated_targets_for_this_ecu = validated_targets_for_this_ecu





  def get_validated_target_info(self, target_filepath):
    """
    COPIED EXACTLY, MINUS COMMENTS, from primary.py.
    # TODO: <~> Refactor later.
    Throws tuf.UnknownTargetError if unable to find/validate a target.
    """
    tuf.formats.RELPATH_SCHEMA.check_match(target_filepath)

    validated_target_info = self.updater.target(
        target_filepath, multi_custom=True)

    if self.director_repo_name not in validated_target_info:

      raise tuf.Error('Unexpected behavior: did not receive target info from '
          'Director repository (' + repr(self.director_repo_name) + ') for '
          'a target (' + repr(target_filepath) + '). Is pinned.json configured '
          'to allow some targets to validate without Director approval, or is'
          'the wrong repository specified as the Director repository in the '
          'initialization of this primary object?')

    tuf.formats.TARGETFILE_SCHEMA.check_match(
        validated_target_info[self.director_repo_name])

    return validated_target_info[self.director_repo_name]





  def process_metadata(self, metadata_archive_fname):
    """
    Expand the metadata archive using _expand_metadata_archive()
    Validate metadata files using fully_validate_metadata()
    Select the Director targets.json file
    Pick out the target file(s) with our ECU serial listed
    Fully validate the metadata for the target file(s)
    """
    #
    tuf.formats.RELPATH_SCHEMA.check_match(metadata_archive_fname)

    self._expand_metadata_archive(metadata_archive_fname)

    # This entails using the local metadata files as a repository.
    self.fully_validate_metadata()





  def _expand_metadata_archive(self, metadata_archive_fname):
    """
    """
    tuf.formats.RELPATH_SCHEMA.check_match(metadata_archive_fname)
    if not os.path.exists(metadata_archive_fname):
      raise uptane.Error('Indicated metadata archive does not exist. '
          'Filename: ' + repr(metadata_archive_fname))

    z = zipfile.ZipFile(metadata_archive_fname)

    z.extractall(os.path.join(self.full_client_dir, 'unverified'))





  def validate_image(self, image_fname):
    """

    Determines if the image with filename provided matches the expected file
    properties, based on the metadata we have previously validated (with
    fully_validate_metadata, stored in self.validated_targets_for_this_ecu). If
    this method completes without raising an exception, the image file is
    valid.

    Arguments:

      image_fname
        This is the filename of the image file to validate. It is expected
        to match the filepath in the target file info (except without any
        leading '/' character). It should, therefore, not include any
        directory names except what is required to specify it within the
        target namespace.
        This file is expected to exist in the client directory, in a
        subdirectory called 'unverified_targets'.


    Exceptions:

      uptane.Error
        if the given filename does not match a filepath in the list of
        validated targets for this ECU (that is, the target(s) for which we
        have received validated instructions from the Director addressed to
        this ECU to install, and for which target info (file size and hashes)
        has been retrieved and fully validated)

      tuf.DownloadLengthMismatchError
        if the file does not have the expected length based on validated
        target info.

      tuf.BadHashError
        if the file does not have the expected hash based on validated target
        info

      tuf.FormatError
        if arguments somewhere down the line do not match expectations
        or if the given image_fname is not a path.
        (# TODO: Clarify, expand, or remove comment.)
    """
    tuf.formats.PATH_SCHEMA.check_match(image_fname)

    print('# TODO: <~> WORKING HERE on image validation in the Secondary')

    full_image_fname = os.path.join(
        self.full_client_dir, 'unverified_targets', image_fname)

    # Get target info by looking up fname (filepath).

    relevant_targetinfo = None

    for targetinfo in self.validated_targets_for_this_ecu:
      filepath = targetinfo['filepath']
      if filepath[0] == '/':
        filepath = filepath[1:]
      if filepath == image_fname:
        relevant_targetinfo = targetinfo

    if relevant_targetinfo is None:
      # TODO: Consider a more specific error class.
      raise uptane.Error('Unable to find validated target info for the given '
          'filename: ' + repr(image_fname) + '. Either metadata was not '
          'successfully updated, or the Primary is providing the wrong image '
          'file, or there was a very unlikely update to data on the Primary '
          'that had updated metadata but not yet updated images (The window '
          'for this is extremely small between two individually-atomic '
          'renames), or there has been a programming error....')


    # Check file length against trusted target info.
    with open(full_image_fname, 'rb') as fobj:
      tuf.client.updater.hard_check_file_length(
          fobj,
          relevant_targetinfo['fileinfo']['length'])

      # # Read the entire contents of 'file_object', a 'tuf.util.TempFile' file-
      # # like object that ensures the entire file is read.
      # observed_length = len(fobj.read())

      # trusted_file_length = relevant_targetinfo['fileinfo']['length']

      # if observed_length != trusted_file_length:
      #   raise tuf.DownloadLengthMismatchError(
      #       trusted_file_length, observed_length)

      # else:
      #   log.debug('Observed length (' + repr(observed_length) +
      #       ') == trusted length (' + repr(trusted_file_length) + ')')

    # Check file hashes against trusted target info.
    with open(full_image_fname, 'rb') as fobj:
      tuf.client.updater.check_hashes(
          fobj, # FIX
          relevant_targetinfo['fileinfo']['hashes'],
          reset_fpointer=True) # Important for multiple hashes


    # If no error has been raised at this point, the image file is fully
    # validated and we can return.
    log.debug('Delivered target file has been fully validated: ' +
        repr(full_image_fname))



