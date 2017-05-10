"""
<Program Name>
  secondary.py

<Purpose>
  Provides core functionality for Uptane Secondary ECU clients:
  - Given an archive of metadata and an image file, performs full verification
    of both, employing TUF (The Update Framework), determining if this
    Secondary ECU has been instructed to install the image by the Director and
    if the image is also valid per the Image Repository.
  - Generates ECU Manifests describing the state of the Secondary for Director
    perusal
  - Generates nonces for time requests from the Timeserver, and validates
    signed times provided by the Timeserver, maintaining trustworthy times.
    Rotates nonces after they have appeared in Timeserver responses.

  A detailed explanation of the role of the Secondary in Uptane is available in
  the "Design Overview" and "Implementation Specification" documents, links to
  which are maintained at uptane.github.io
"""
from __future__ import print_function
from __future__ import unicode_literals
from io import open # TODO: Determine if this should be here.

import os # For paths and makedirs
import shutil # For copyfile
import random # for nonces
import zipfile # to expand the metadata archive retrieved from the Primary
import hashlib

import tuf.formats
import tuf.keys
import tuf.client.updater
import tuf.repository_tool as rt

import uptane
import uptane.formats
import uptane.common
import uptane.encoding.asn1_codec as asn1_codec


from uptane import GREEN, RED, YELLOW, ENDCOLORS


log = uptane.logging.getLogger('secondary')
log.addHandler(uptane.file_handler)
log.addHandler(uptane.console_handler)
log.setLevel(uptane.logging.DEBUG)



class Secondary(object):

  """
  <Purpose>
    This class contains the necessary code to perform Uptane validation of
    images and metadata. An implementation of Uptane should use code like this
    to perform full validation of images and metadata.

  <Fields>

    self.vin
      A unique identifier for the vehicle that contains this Secondary ECU.
      In this reference implementation, this conforms to
      uptane.formats.VIN_SCHEMA. There is no need to use the vehicle's VIN in
      particular; we simply need a unique identifier for the vehicle, known
      to the Director.

    self.ecu_serial
      A unique identifier for this Secondary ECU. In this reference
      implementation, this conforms to uptane.formats.ECU_SERIAL_SCHEMA.
      (In other implementations, the important point is that this should be
      unique.) The Director should be aware of this identifier.

    self.ecu_key:
      The signing key for this Secondary ECU. This key will be used to sign
      ECU Manifests that will then be sent along to the Primary (and
      subsequently to the Director). The Director should be aware of the
      corresponding public key, so that it can validate these ECU Manifests.
      Conforms to tuf.formats.ANYKEY_SCHEMA.

    self.updater:
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the Director and Image repositories.

    self.full_client_dir:
      The full path of the directory where all client data is stored for this
      secondary. This includes verified and unverified metadata and images and
      any temp files. Conforms to tuf.formats.PATH_SCHEMA.

    self.director_repo_name
      The name of the Director repository (e.g. 'director'), as listed in the
      map (or pinning) file (pinned.json). This value must appear in that file.
      Used to distinguish between the Image Repository and the Director
      Repository. Conforms to tuf.formats.REPOSITORY_NAME_SCHEMA.

    self.timeserver_public_key:
      The public key of the Timeserver, which will be used to validate signed
      time attestations from the Timeserver.
      Conforms to tuf.formats.ANYKEY_SCHEMA.

    self.partial_verifying:
      False if this client is to employ full metadata verification (the default)
      with all checks included in the Uptane Implementation Specification,
      else True if this instance is a partial verifier.
      A Partial Verification Secondary is programmed with the Director's
      Targets role public key and will only validate that signature on that
      file, leaving it susceptible to some attacks if the Director key
      is compromised or has to change.

    self.director_public_key
      If this is a partial verification secondary, we store the key that we
      expect the Director to use here. Full verification clients should have
      None in this field. If provided, this conforms to
      tuf.formats.ANYKEY_SCHEMA.

    self.firmware_fileinfo:
      The target file info for the image this Secondary ECU is currently using
      (has currently "installed"). This is generally filename, hash, and
      length. See tuf.formats.TARGETFILE_SCHEMA, which contains
      tuf.formats.FILEINFO_SCHEMA. This info is provided in ECU Manifests
      generated for the Director's consumption.

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
    director_repo_name,
    vin,
    ecu_serial,
    ecu_key,
    time,
    timeserver_public_key,
    firmware_fileinfo=None,
    director_public_key=None,
    partial_verifying=False):

    """
    <Purpose>
      Constructor for class Secondary

    <Arguments>

      full_client_dir       See class docstring above.

      director_repo_name    See class docstring above.

      vin                   See class docstring above.

      ecu_serial            See class docstring above.

      ecu_key               See class docstring above.

      timeserver_public_key See class docstring above.

      director_public_key   See class docstring above. (optional)

      partial_verifying     See class docstring above. (optional)

      time
        An initial time to set the Secondary's "clock" to, conforming to
        tuf.formats.ISO8601_DATETIME_SCHEMA.

      firmware_fileinfo (optional)
        See class docstring above. As provided here, this is the initial
        value, which will be provided in ECU Manifests generated for the
        Director's consumption until the firmware is updated.


    <Exceptions>

      tuf.FormatError
        if the arguments are not correctly formatted

      uptane.Error
        if arguments partial_verifying and director_public_key are inconsistent
          (partial_verifying True requires a director_public_key, and
           partial_verifying False requires no director_public_key)
        if director_repo_name is not a known repository based on the
        map/pinning file (pinned.json)

    <Side Effects>
      None.
    """

    # Check arguments:
    tuf.formats.PATH_SCHEMA.check_match(full_client_dir)
    tuf.formats.PATH_SCHEMA.check_match(director_repo_name)
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(time)
    tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_public_key)
    tuf.formats.ANYKEY_SCHEMA.check_match(ecu_key)
    if director_public_key is not None:
        tuf.formats.ANYKEY_SCHEMA.check_match(director_public_key)

    self.director_repo_name = director_repo_name
    self.ecu_key = ecu_key
    self.vin = vin
    self.ecu_serial = ecu_serial
    self.full_client_dir = full_client_dir
    self.director_proxy = None
    self.timeserver_public_key = timeserver_public_key
    self.director_public_key = director_public_key
    self.partial_verifying = partial_verifying
    self.firmware_fileinfo = firmware_fileinfo

    if not self.partial_verifying and self.director_public_key is not None:
      raise uptane.Error('Secondary not set as partial verifying, but a director ' # TODO: Choose error class.
          'key was still provided. Full verification secondaries employ the '
          'normal TUF verifications rooted at root metadata files.')

    elif self.partial_verifying and self.director_public_key is None:
      raise uptane.Error('Secondary set as partial verifying, but a director '
          'key was not provided. Partial verification Secondaries validate '
          'only the ')


    # Create a TAP-4-compliant updater object. This will read pinning.json
    # and create single-repository updaters within it to handle connections to
    # each repository.
    self.updater = tuf.client.updater.Updater('updater')

    if director_repo_name not in self.updater.pinned_metadata['repositories']:
      raise uptane.Error('Given name for the Director repository is not a '
          'known repository, according to the pinned metadata from pinned.json')

    # We load the given time twice for simplicity in later code.
    self.all_valid_timeserver_times = [time, time]

    self.last_nonce_sent = None
    self.nonce_next = self._create_nonce()





  def set_nonce_as_sent(self):
    """
    To be called when the ECU Version Manifest is submitted, as that
    includes the sending of this nonce.

    The most recent nonce sent (assigned here) is the nonce this Secondary
    expects to find in the next timeserver attestation it validates.
    """
    self.last_nonce_sent = self.nonce_next





  def change_nonce(self):
    """
    This should generally be called only by validate_time_attestation.

    To be called only when this Secondary has validated a timeserver
    attestation that lists the current nonce, when we know that nonce has been
    used. Rolls over to a new nonce.

    The result in self.nonce_next is the nonce that should be used in any
    future message to the Primary. Once it has been sent to the Primary,
    set_nonce_as_sent should be called.
    """
    self.nonce_next = self._create_nonce()





  def _create_nonce(self):
    """
    Returns a pseudorandom number for use in protecting from replay attacks
    from the timeserver (or an intervening party).
    """
    return random.randint(
        uptane.formats.NONCE_LOWER_BOUND, uptane.formats.NONCE_UPPER_BOUND)





  def generate_signed_ecu_manifest(self, description_of_attacks_observed=''):
    """
    Returns a signed ECU manifest indicating self.firmware_fileinfo.

    If the optional description_of_attacks_observed argument is provided,
    the ECU Manifest will include that in the ECU Manifest (attacks_detected).
    """

    uptane.formats.DESCRIPTION_OF_ATTACKS_SCHEMA.check_match(
        description_of_attacks_observed)

    # We'll construct a signed signable_ecu_manifest_SCHEMA from the
    # targetinfo.
    # First, construct and check an ECU_VERSION_MANIFEST_SCHEMA.
    ecu_manifest = {
        'ecu_serial': self.ecu_serial,
        'installed_image': self.firmware_fileinfo,
        'timeserver_time': self.all_valid_timeserver_times[-1],
        'previous_timeserver_time': self.all_valid_timeserver_times[-2],
        'attacks_detected': description_of_attacks_observed
    }
    uptane.formats.ECU_VERSION_MANIFEST_SCHEMA.check_match(ecu_manifest)

    # Now we'll convert it into a signable object and sign it with a key we
    # generate.

    # Wrap the ECU version manifest object into an
    # uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA and check the format.
    # {
    #     'signed': ecu_version_manifest,
    #     'signatures': []
    # }
    signable_ecu_manifest = tuf.formats.make_signable(ecu_manifest)
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signable_ecu_manifest)

    if tuf.conf.METADATA_FORMAT == 'der':
      der_signed_ecu_manifest = asn1_codec.convert_signed_metadata_to_der(
          signable_ecu_manifest, resign=True,
          private_key=self.ecu_key, datatype='ecu_manifest')
      # TODO: Consider verification of output here.
      return der_signed_ecu_manifest

    # Else use standard Python dictionary format specified in uptane.formats.

    # Now sign with that key.
    uptane.common.sign_signable(
        signable_ecu_manifest, [self.ecu_key], datatype='ecu_manifest')
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signable_ecu_manifest)

    return signable_ecu_manifest





  def validate_time_attestation(self, timeserver_attestation):
    """
    Given a timeserver attestation, validate it (checking that the signature is
    valid and from the expected key) and ensure that the nonce we expect the
    attestation to contain is included.

    If validation is successful, switch to a new nonce for next time.
    """
    # Check format.
    uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
        timeserver_attestation)

    # Assume there's only one signature.
    assert len(timeserver_attestation['signatures']) == 1

    valid = uptane.common.verify_signature_over_metadata(
        self.timeserver_public_key,
        timeserver_attestation['signatures'][0],
        timeserver_attestation['signed'],
        datatype='time_attestation')

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
    self.validated_targets_for_this_ecu if Director and Image repositories
    indicate the same file info for targets A.

    If, target info would not be saved for target A if Director and Image
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
    # TODO: Refactor later.
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
    tuf.formats.RELPATH_SCHEMA.check_match(metadata_archive_fname)

    self._expand_metadata_archive(metadata_archive_fname)

    # This entails using the local metadata files as a repository.
    self.fully_validate_metadata()





  def _expand_metadata_archive(self, metadata_archive_fname):
    """
    Given the filename of an archive of metadata files validated and zipped by
    primary.py, unzip it into the contained metadata files, to be used as a
    local repository and validated by this Secondary.

    Note that attacks are possible against zip files. The particulars of the
    distribution of these metadata files from Primary to Secondary will vary
    greatly based on one's implementation and setup, so this is offered for
    instruction. The mechanism employed in particular should not obviate the
    protections provided by Uptane and TUF. It should time out rather than be
    susceptible to slow retrieval, and not introduce vulnerabilities in the
    face of a malicious Primary.
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

    <Arguments>

      image_fname
        This is the filename of the image file to validate. It is expected
        to match the filepath in the target file info (except without any
        leading '/' character). It should, therefore, not include any
        directory names except what is required to specify it within the
        target namespace.
        This file is expected to exist in the client directory
        (self.full_client_dir), in a subdirectory called 'unverified_targets'.

    <Exceptions>

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
        if the given image_fname is not a path.

    <Returns>
      None.

    <Side-Effects>
      None.
    """
    tuf.formats.PATH_SCHEMA.check_match(image_fname)

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

