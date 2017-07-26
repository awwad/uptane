"""
<Program Name>
  primary.py

<Purpose>
  Provides core functionality for Uptane Primary ECU clients:
  - Obtains and performs full verification of metadata and images, employing
    TUF (The Update Framework)
  - Prepares metadata and images for distribution to Secondaries
  - Receives ECU Manifests and holds them for the next Vehicle Manifest
  - Generates Vehicle Manifests
  - Receives nonces from Secondaries; maintains and cycles a list of nonces
    for use in requests for signed time from the Timeserver

  A detailed explanation of the role of the Primary in Uptane is available in
  the "Design Overview" and "Implementation Specification" documents, links to
  which are maintained at uptane.github.io
"""
from __future__ import print_function
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

import os # For paths and makedirs
import shutil # For copyfile
import random # for nonces
import zipfile
import hashlib # if we're using DER encoding

import tuf.formats
import tuf.conf
import tuf.keys
import tuf.client.updater
import tuf.repository_tool as rt

import uptane.formats
import uptane.common
import uptane.services.director as director
import uptane.services.timeserver as timeserver
import uptane.encoding.asn1_codec as asn1_codec
from uptane import GREEN, RED, YELLOW, ENDCOLORS

# The following import is a temporary measure to facilitate demonstration.
# It does not ultimately belong here in the reference implementation.
from demo.uptane_banners import *


log = uptane.logging.getLogger('primary')
log.addHandler(uptane.file_handler)
log.addHandler(uptane.console_handler)
log.setLevel(uptane.logging.DEBUG)



class Primary(object): # Consider inheriting from Secondary and refactoring.
  """
  <Purpose>
    This class contains the necessary code to perform Uptane validation of
    images and metadata, and core functionality supporting distribution of
    metadata and images to Secondary ECUs, combining ECU Manifests into a
    Vehicle Manifest and signing it, combining tokens for a Timeserver request,
    validating the response, etc.

  <Fields>

    self.vin
      A unique identifier for the vehicle that contains this Secondary ECU.
      In this reference implementation, this conforms to
      uptane.formats.VIN_SCHEMA. There is no need to use the vehicle's VIN in
      particular; we simply need a unique identifier for the vehicle, known
      to the Director.

    self.ecu_serial
      A unique identifier for this Primary ECU. In this reference
      implementation, this conforms to uptane.formats.ECU_SERIAL_SCHEMA.
      (In other implementations, the important point is that this should be
      unique.) The Director should be aware of this identifier.

    self.hardware_id
      An identifier for a group of ECUs that helps ensure the installation
      of the right firmware is installed.
      Verified for installation if the value matches both in the
      Image Repository and Director Repository.
      Conforms to uptane.formats.HARDWARE_ID_SCHEMA.
      This is used to prevent a compromised director from causing an
      ECU to download an image not intended for it.

    self.release_counter
      An integer value to track the version number of the images installed.
      Ensures that an older image than the one currently installed is
      not installed.
      Conforms to uptane.formats.RELEASE_COUNTER_SCHEMA.
      This is used to prevent a compromised director from causing an ECU
      to download an outdated image or an older one with known vulnerabilities.

    self.primary_key
      The signing key for this Secondary ECU. This key will be used to sign
      Vehicle Manifests that will then be sent to the Director). The Director
      should be aware of the corresponding public key, so that it can validate
      these Vehicle Manifests. Conforms to tuf.formats.ANYKEY_SCHEMA.

    self.updater
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the Director and Supplier repositories.

    self.full_client_dir
      The full path of the directory where all client data is stored for this
      Primary. This includes verified and unverified metadata and images and
      any temp files. Conforms to tuf.formats.PATH_SCHEMA.

    self.director_repo_name
      The name of the Director repository (e.g. 'director'), as listed in the
      map (or pinning) file (pinned.json). This value must appear in that file.
      Used to distinguish between the Image Repository and the Director
      Repository. Conforms to tuf.formats.REPOSITORY_NAME_SCHEMA.

    self.timeserver_public_key:
      The public key matching the private key that we expect the timeserver to
      use when signing attestations. Validation is against this key.

    self.ecu_manifests
      A dictionary containing the manifests provided by all ECUs. Will include
      all manifests sent by all ECUs. The Primary does not verify signatures on
      ECU manifests according to the Implementation Specification.
      Compromised ECUs may send bogus ECU manifests, so we simply send all
      manifests to the Director, who will sort through and discern what is
      going on.
      This is emptied every time the Primary produces a Vehicle Manifest
      (which will have included all of them). An implementer may wish to
      consider keeping these around until there is some likelihood that the
      Director has received them, as doing otherwise could deprive the
      Director of some historical and error/attack data. (Future ECU Manifests
      will provide current information, but useful diagnostic information may
      be lost.)

    self.my_secondaries:
      This is a list of all ECU Serials belonging to Secondaries of this
      Primary.

    self.assigned_targets:
      A dict mapping ECU Serial to the target file info that the Director has
      instructed that ECU to install.

    self.nonces_to_send:
      The list of nonces sent to us from Secondaries and not yet sent to the
      Timeserver.

    self.primary_exceptions
      A dictionary to track errors ECU encounter while trying to install 
      images. The mapping is in the following format:
      Image : ECU : Error
      Example ==>
      {'/BCU1.1.txt': {'BCUdemocar': <class 'uptane.ImageRollBack'>},
      '/BCU1.2.txt': {'BCUdemocar': <class 'uptane.HardwareIDMismatch'>}}

    self.nonces_sent:
      The list of nonces sent to the Timeserver by our Secondaries, which we
      have already sent to the Timeserver. Will be checked against the
      Timeserver's response.

    self.all_valid_timeserver_attestations:
      A list of all attestations received from Timeservers that have been
      validated by validate_time_attestation.
      Items are appended to the end.

    self.all_valid_timeserver_times:
      A list of all times extracted from all Timeserver attestations that have
      been validated by validate_time_attestation.
      Items are appended to the end.

    self.distributable_full_metadata_archive_fname:
      The filename at which the full metadata archive is stored after each
      update cycle. Path is relative to uptane.WORKING_DIR. This is atomically
      moved into place (renamed) after it has been fully written, to avoid
      race conditions.

    self.distributable_partial_metadata_fname:
      The filename at which the Director's targets metadata file is stored after
      each update cycle, once it is safe to use. This is atomically moved into
      place (renamed) after it has been fully written, to avoid race conditions.

  Methods organized by purpose: ("self" arguments excluded)

    High-level Methods for OEM/Supplier Primary code to use:
      __init__()
      primary_update_cycle()
      generate_signed_vehicle_manifest()
      get_nonces_to_send_and_rotate()
      save_distributable_metadata_files()
      validate_time_attestation(timeserver_attestation)

    Lower-level methods called by primary_update_cycle() to perform retrieval
    and validation of metadata and data from central services:
      refresh_toplevel_metadata_from_repositories()
      get_target_list_from_director()
      get_validated_target_info()

    Components of the interface available to a Secondary client:
      register_ecu_manifest(vin, ecu_serial, nonce, signed_ecu_manifest)
      get_last_timeserver_attestation()
      update_exists_for_ecu(ecu_serial)
      get_image_fname_for_ecu(ecu_serial)
      get_full_metadata_archive_fname()
      get_partial_metadata_fname()
      register_new_secondary(ecu_serial)

    Private methods:
      _check_ecu_serial(ecu_serial)


  Use:
    import uptane.clients.primary as primary
    p = primary.Primary(
        full_client_dir='/Users/s/w/uptane/temp_primarymetadata',
        vin='vin11111',
        ecu_serial='ecu00000',
        timeserver_public_key=<some key>)

    p.register_ecu_manifest(vin, ecu_serial, nonce, <a signed ECU manifest>)
    p.register_ecu_manifest(...)
    ...

    nonces = p.get_nonces_to_send_and_rotate()

    <submit the nonces to the Timeserver and save the returned time attestation>

    p.validate_time_attestation(<the returned time attestation>)

    <metadata> = p.get_metadata_for_ecu(ecu_serial)
    <secondary firmware> = p.get_image_for_ecu(ecu_serial)
    <metadata> = p.get_metadata_for_ecu(<some other ecu serial>)
    ...

    And so on, with ECUs requesting images and metadata and registering ECU
    manifests (and providing nonces thereby).
  """

  def __init__(
    self,
    full_client_dir,  # '/Users/s/w/uptane/temp_primarymetadata'
    director_repo_name, # e.g. 'director'; value must appear in pinning file
    vin,              # 'vin11111'
    ecu_serial,       # 'ecu00000'
    primary_key,
    time,
    timeserver_public_key,
    hardware_id,
    release_counter = 0,  # Sample image has version 0
    my_secondaries=[]):

    """
    <Purpose>
      Constructor for class Primary

    <Arguments>

      full_client_dir       See class docstring above.

      director_repo_name    See class docstring above.

      vin                   See class docstring above.

      ecu_serial            See class docstring above.

      primary_key           See class docstring above.

      timeserver_public_key See class docstring above.

      my_secondaries        See class docstring above. (optional)

      time
        An initial time to set the Primary's "clock" to, conforming to
        tuf.formats.ISO8601_DATETIME_SCHEMA.


    <Exceptions>

      tuf.FormatError
        if the arguments are not correctly formatted

      uptane.Error
        if director_repo_name is not a known repository based on the
        map/pinning file (pinned.json)

    <Side Effects>
      None.
    """

    # Check arguments:
    tuf.formats.PATH_SCHEMA.check_match(full_client_dir)
    tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(time)
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    uptane.formats.HARDWARE_ID_SCHEMA.check_match(hardware_id)
    uptane.formats.RELEASE_COUNTER_SCHEMA.check_match(release_counter)
    tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_public_key)
    tuf.formats.ANYKEY_SCHEMA.check_match(primary_key)
    # TODO: Should also check that primary_key is a private key, not a
    # public key.

    self.vin = vin
    self.ecu_serial = ecu_serial
    self.hardware_id = hardware_id
    self.release_counter = release_counter
    self.full_client_dir = full_client_dir
    self.all_valid_timeserver_times = [time]
    self.all_valid_timeserver_attestations = []
    self.timeserver_public_key = timeserver_public_key
    self.primary_key = primary_key
    self.my_secondaries = my_secondaries
    self.director_repo_name = director_repo_name
    self.primary_exceptions = dict()

    self.temp_full_metadata_archive_fname = os.path.join(
        full_client_dir, 'metadata', 'temp_full_metadata_archive.zip')
    self.distributable_full_metadata_archive_fname = os.path.join(
        full_client_dir, 'metadata', 'full_metadata_archive.zip')

    # TODO: Some of these assumptions are unseemly. Reconsider.
    self.temp_partial_metadata_fname = os.path.join(
        full_client_dir, 'metadata', 'temp_director_targets.' +
        tuf.conf.METADATA_FORMAT)
    self.distributable_partial_metadata_fname = os.path.join(
        full_client_dir, 'metadata', 'director_targets.' +
        tuf.conf.METADATA_FORMAT)

    # Initializations not directly related to arguments.
    self.nonces_to_send = []
    self.nonces_sent = []
    self.assigned_targets = dict()

    # Initialize the dictionary of manifests. This is a dictionary indexed
    # by ECU serial and with value being a list of manifests from that ECU, to
    # support the case in which multiple manifests have come from that ECU.
    self.ecu_manifests = {}


    # Create a TUF-TAP-4-compliant updater object. This will read pinning.json
    # and create single-repository updaters within it to handle connections to
    # each repository.
    self.updater = tuf.client.updater.Updater('updater')

    if director_repo_name not in self.updater.pinned_metadata['repositories']:
      raise uptane.Error('Given name for the Director repository is not a '
          'known repository, according to the pinned metadata from pinned.json')


  def __str__(self):
    return("VIN: {}, ECU_SERIAL: {}, HARDWARE_ID: {}, \
        RELEASE_COUNTER: {}".format(self.vin, self.ecu_serial, \
        self.hardware_id, self.release_counter))


  def refresh_toplevel_metadata_from_repositories(self):
    """
    Refreshes client's metadata for the top-level roles:
      root, targets, snapshot, and timestamp

    See tuf.client.updater.Updater.refresh() for details, or the
    Uptane Implementation Specification, section 8.3.2 (Full Verification of
    Metadata).
    """
    self.updater.refresh()





  def get_target_list_from_director(self):
    """
    This method extracts the Director's instructions from the targets role in
    the Director repository's metadata. These must still be validated against
    the Image Repository in further calls.
    """
    # TODO: This will have to be changed (along with the functions that depend
    # on this function's output) once multi-role delegations can yield multiple
    # targetfile_info objects. (Currently, we only yield more than one at the
    # multi-repository delegation level.)
    directed_targets = self.updater.targets_of_role(
        rolename='targets', repo_name=self.director_repo_name)

    return directed_targets





  def get_validated_target_info(self, target_filepath):
    """
    (Could be called: get Director's version of the fully validated target info)

    <Purpose>

      Returns trustworthy target information for the given target file
      (specified by its file path), from the Director, validated against the
      Image Repository (or whichever repositories are required per the
      pinned.json file).

      The returned information has been cleared according to the trust
      requirements of the pinning file (pinned.json) that this client is
      equipped with. Assuming typical pinned.json configuration for Uptane,
      this means that there is a multi-repository delegation to [the Director
      Repository plus the Image Repository]. The target file info received
      within this method is that from all repositories in the multi-repository
      delegation, and each is guaranteed to be identical to the others in all
      respects (e.g. crytographic hash and length) except for the "custom"
      metadata field, since the Director includes an additional piece of
      information in the fileinfo: the ECU Serial to which the target file is
      assigned.

      This method returns only the Director's version of this target file info,
      which includes that "custom" field with ECU Serial assignments.

    <Returns>
      Target file info compliant with tuf.formats.TARGETFILE_INFO_SCHEMA,


    <Exceptions>

      tuf.UnknownTargetError
        if a given filepath is not listed by the consensus of Director and
        Image Repository (or through whichever trusted path is specified by
        this client's pinned.json file.) If info is returned, it will match
        tuf.formats.TARGETFILE_SCHEMA and will have been validated by all
        required parties.

      tuf.NoWorkingMirrorError
        will be raised by the updater.target() call here if we are unable to
        validate reliable target info for the target file specified (if the
        repositories do not agree, or we could not reach them, or so on).

      uptane.Error
        if the Director targets file has not provided information about the
        given target_filepath, but target_filepath has nevertheless been
        validated. This could happen if the map/pinning file for some reason
        incorrectly set to not require metadata from the Director.

    """
    tuf.formats.RELPATH_SCHEMA.check_match(target_filepath)

    validated_target_info = self.updater.target(
        target_filepath, multi_custom=True)

    # validated_target_info will now look something like this:
    # {
    #   'Director': {
    #     filepath: 'django/django.1.9.3.tgz',
    #     fileinfo: {hashes: ..., length: ..., custom: {'ecu_serial': 'ECU1010101'} } },
    #   'ImageRepo': {
    #     filepath: 'django/django.1.9.3.tgz',
    #     fileinfo: {hashes: ..., length: ... } } }
    # }

    # We expect there to be an entry in the dict with key name equal to the
    # name of the Director repository (specified in pinned.json).

    if self.director_repo_name not in validated_target_info:
      # TODO: Consider a different exception class. This seems more like an
      # assert statement, though.... If this happens, something is wrong in
      # code, or pinned.json is misconfigured (to allow target validation
      # whereby the Director is not specified in some multi-repository
      # delegations) or the value of director_repo_name passed to the
      # initialization of this object was wrong. Those are the edge cases I can
      # come up with that could cause this.

      # If the Director repo specified as self.director_repo_name is not in
      # pinned.json at all, we'd have thrown an error during __init__. If the
      # repos couldn't provide validated target file info, we'd have caught an
      # error earlier instead.

      raise uptane.Error('Unexpected behavior: did not receive target info from'
          ' Director repository (' + repr(self.director_repo_name) + ') for '
          'a target (' + repr(target_filepath) + '). Is pinned.json configured '
          'to allow some targets to validate without Director approval, or is'
          'the wrong repository specified as the Director repository in the '
          'initialization of this primary object?')

    director_target = validated_target_info[self.director_repo_name]
    temp_release_counter = None
    temp_hardware_id = None

    for repository_name in validated_target_info.keys():
      current_target = validated_target_info[repository_name]

      if 'custom' not in validated_target_info[repository_name]['fileinfo']:
        raise uptane.Error('{} repo failed to include the custom field in a \
            target. \nTarget metadata was: {}'.format(repository_name, \
            repr(current_target)))
        continue

      custom_target_metadata = \
          validated_target_info[repository_name]['fileinfo']['custom']
      current_target_hardware_id = custom_target_metadata['hardware_id']
      current_target_release_counter = custom_target_metadata['release_counter']
      if 'hardware_id' in custom_target_metadata:
        if temp_hardware_id == None:
          temp_hardware_id = current_target_hardware_id
        elif temp_hardware_id != current_target_hardware_id:
          raise uptane.HardwareIDMismatch('Bad value for the field \
              hardware_ID in the that did not correspond the value in \
              the other repos. Value did not match between the director \
              and the other repos. The value of director target is {}'.format(
              repr(director_target)))
          continue
      else:
        raise uptane.Error('{} repo failed to include the hardware ID field \
            in the custom field of the target. \nTarget metadata was:\
            {}'.format(repository_name, repr(current_target)))
        continue

      if 'release_counter' in custom_target_metadata:
        if temp_release_counter == None:
          temp_release_counter = current_target_release_counter
        elif temp_release_counter != current_target_release_counter:
          raise uptane.ImageRollBack('Bad value for the field release_counter \
             that did not correspond the value in the other repos. Value \
             did not match between the director and the other repos. \
             The value of director target is {}'.format(repr(director_target)))
          continue
      else:
        raise uptane.Error('{} repo failed to include the release counter \
            field in the custom field of the target. \nTarget metadata was:\
            {}'.format(repository_name, repr(current_target)))
        continue

    # Defensive coding: this should already have been checked.
    tuf.formats.TARGETFILE_SCHEMA.check_match(
        validated_target_info[self.director_repo_name])

    return validated_target_info[self.director_repo_name]





  def primary_update_cycle(self):
    """
    Download fresh metadata and images for this vehicle, as instructed by the
    Director and validated by the Image Repository.

    Begin by obtaining trustworthy target file metadata from the repositories,
    then instruct TUF to download matching files.

    Assign the target files to ECUs and keep that mapping in memory for
    later distribution.

    Package up the validated metadata into a zip archive for distribution.
    (Normally, we wouldn't want to include such details as packaging in the
    reference implementation, but in this case, it is the most convenient way
    to maintain the existing interfaces with TUF and with demonstration code.)


    <Exceptions>
      uptane.Error
        - If Director repo fails to include an ECU Serial in the custom metadata
          for a given target file.
        - If a file exists in the metadata directory in which validated files
          are deposited by TUF that does not have an extension that befits a
          file of type tuf.conf.METADATA_FORMAT.
    """
    log.debug('Refreshing top level metadata from all repositories.')
    self.refresh_toplevel_metadata_from_repositories()

    # Get the list of targets the director expects us to download and update to.
    # Note that at this line, this target info is not yet validated with the
    # Image Repository: that is done a few lines down.
    directed_targets = self.get_target_list_from_director()

    if not directed_targets:
      log.info('A correctly signed statement from the Director indicates that '
          'this vehicle has NO updates to install.')
    else:
      log.info('A correctly signed statement from the Director indicates that '
          'this vehicle has updates to install:' +
          repr([targ['filepath'] for targ in directed_targets]))


    log.debug('Retrieving validated image file metadata from Image and '
        'Director Repositories.')

    # This next block employs get_validated_target_info calls to determine what
    # the right fileinfo (hash, length, etc) for each target file is. This
    # begins by matching paths/patterns in pinned.json to determine which
    # repository to connect to. Since pinned.json will generally assigns all
    # targets to a multi-repository delegation requiring consensus between the
    # two repositories, one for the Director and one for the Image Repository,
    # this call will retrieve metadata from both repositories and compare it to
    # each other, and only return fileinfo if it can be retrieved from both
    # repositories and is identical (the metadata in the "custom" fileinfo
    # field need not match, and should not, since the Director will include
    # ECU IDs in this field, and the Image Repository cannot.

    # This will contain a list of tuf.formats.TARGETFILE_SCHEMA objects.
    verified_targets = []
    for targetinfo in directed_targets:
      target_filepath = targetinfo['filepath'].encode(
          'ascii', 'ignore')
      target_ecu = targetinfo \
          ['fileinfo']['custom']['ecu_serial'].encode(
            'ascii', 'ignore')
      try:
        # targetinfos = self.get_validated_target_info(target_filepath)
        # for repo in targetinfos:
        #   tuf.formats.TARGETFILE_SCHEMA.check_match(targetinfos[repo])
        verified_targets.append(self.get_validated_target_info(target_filepath))

      except tuf.UnknownTargetError:
        log.warning(RED + 'Director has instructed us to download a target (' +
            target_filepath + ') that is not validated by the combination of '
            'Image + Director Repositories. That update IS BEING SKIPPED. It '
            'may be that files have changed in the last few moments on the '
            'repositories. Try again, but if this happens often, you may be '
            'connecting to an untrustworthy Director, or there may be an '
            'untrustworthy Image Repository, or the Director and Image '
            'Repository may be out of sync.' + ENDCOLORS)

        temp_exception_dict={target_ecu : uptane.HardwareIDMismatch}

        self.primary_exceptions[target_filepath] = \
            temp_exception_dict

        # The following is code intended for a demonstration, inserted here
        # into the reference implementation as a temporary measure.
        print_banner(BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
            text='The Director has instructed us to download a file that does '
            ' does not exactly match the Image Repository metadata. '
            'File: ' + repr(target_filepath), sound=TADA)

        import time
        time.sleep(3)
        # End demo code.
      except uptane.HardwareIDMismatch:
        log.warning(RED + 'Dorector has instructed us to download a target (' +
            target_filepath + ') that is not validated by the combination of '
            'Image + Director Repositories. That update IS BEING SKIPPED. It '
            'the hardware IDs do not match between image and director '
            'repositories. Try again, but if this happens often, you may be '
            'connecting to an untrustworthy Director, or there may be an '
            'untrustworthy Image Repository, or the Director and Image '
            'Repository may be out of sync.' + ENDCOLORS)

        temp_exception_dict={target_ecu : uptane.HardwareIDMismatch}

        self.primary_exceptions[target_filepath] = \
            temp_exception_dict

        #Commenting out the following because unsure if banners should
        # be in the reference implementation of pimraries or not
        #print_banner(BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
        #      text='The Director has instructed us to download an image'
        #      ' that is not meant for the stated ECU. HardwareIDdoes not'
        #      ' match with other repositorie. This image has'
        #      ' been rejected.', sound=TADA)

      except uptane.ImageRollBack:
        log.warning(RED + 'Dorector has instructed us to download a target (' +
            target_filepath + ') that is not validated by the combination of '
            'Image + Director Repositories. That update IS BEING SKIPPED. It '
            'the release counters do not match between image and director '
            'repositories. Try again, but if this happens often, you may be '
            'connecting to an untrustworthy Director, or there may be an '
            'untrustworthy Image Repository, or the Director and Image '
            'Repository may be out of sync.' + ENDCOLORS)

        temp_exception_dict={target_ecu : uptane.ImageRollBack}

        self.primary_exceptions[target_filepath] = \
            temp_exception_dict

        #print_banner(BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
        #      text='The Director has instructed us to download an image'
        #      ' that has a bad release counter and does not match with '
        #      ' other repositories. This image has'
        #      ' been rejected.', sound=TADA)

    # # Grab a filepath from each of the dicts of target file infos. (Each dict
    # # corresponds to one file, and the filepaths in all the infos in that dict
    # # will be the same - only the 'custom' field can differ within a given
    # # dict).
    # verified_target_filepaths = \
    #     [next(six.itervalues(targ))['filepath'] for targ in verified_targets]
    # get_validated_target_info() above returns only the Director's fileinfo,
    # and only after validating it fully as configured in pinned.json (i.e.
    # with the Image Repo or whatever other repository/ies specified in
    # pinned.json).
    verified_target_filepaths = [targ['filepath'] for targ in verified_targets]

    log.info('Metadata for the following Targets has been validated by both '
        'the Director and the Image repository. They will now be downloaded:' +
        repr(verified_target_filepaths))


    # For each target for which we have verified metadata:
    for target in verified_targets:

      tuf.formats.TARGETFILE_SCHEMA.check_match(target) # redundant, defensive

      if 'custom' not in target['fileinfo'] or \
          'ecu_serial' not in target['fileinfo']['custom']:
        raise uptane.Error('Director repo failed to include an ECU Serial for '
            'a target. Target metadata was: ' + repr(target))
      # Get the ECU Serial listed in the custom file data.
      assigned_ecu_serial = target['fileinfo']['custom']['ecu_serial']
      # Checking the formats
      uptane.formats.ECU_SERIAL_SCHEMA.check_match(assigned_ecu_serial)
      # Make sure it's actually an ECU we know about.
      if assigned_ecu_serial not in self.my_secondaries:
        log.warning(RED + 'Received a target from the Director with '
            'instruction to provide it to a Secondary ECU ' + repr(assigned_ecu_serial) +
            ' that is not known '
            'to this Primary! Disregarding / not downloading target or saving '
            'fileinfo!' + ENDCOLORS)
        continue

      # Save the target info as an update assigned to that ECU.
      self.assigned_targets[assigned_ecu_serial] = target


      # Make sure the resulting filename is actually in the client directory.
      # (In other words, enforce a jail.)
      # TODO: Do a proper review of this, and determine if it's necessary and
      # how to do it properly.
      full_targets_directory = os.path.abspath(os.path.join(
          self.full_client_dir, 'targets'))
      filepath = target['filepath']
      if filepath[0] == '/':
        filepath = filepath[1:]
      full_fname = os.path.join(full_targets_directory, filepath)
      enforce_jail(filepath, full_targets_directory)

      # TODO: Remove this. It's here for convenience during dev & testing.
      # Considerations on the ground by implementers / users of the reference
      # implementation will decide what to do with target files after they've
      # been used.
      # Delete existing targets.
      if os.path.exists(full_fname):
        os.remove(full_fname)

      # Download each target.
      # Now that we have fileinfo for all targets listed by both the Director and
      # the Image Repository -- which should include file2.txt in this test --
      # we can download the target files and only keep each if it matches the
      # verified fileinfo. This call will try every mirror on every repository
      # within the appropriate delegation in pinned.json until one of them works.
      # In this case, both the Director and Image Repo are hosting the
      # file, just for my convenience in setup. If you remove the file from the
      # Director before calling this, it will still work (assuming Image Repo
      # still has it). (The second argument here is just where to put the
      # files.)
      try:
        self.updater.download_target(target, full_targets_directory)

      except tuf.NoWorkingMirrorError as e:
        print('')
        print(YELLOW + 'In downloading target ' + repr(filepath) + ', am unable '
            'to find a mirror providing a trustworthy file.\nChecking the mirrors'
            ' resulted in these errors:')
        for mirror in e.mirror_errors:
          print('    ' + type(e.mirror_errors[mirror]).__name__ + ' from ' + mirror)
        print(ENDCOLORS)

        print_banner(BANNER_DEFENDED, color=WHITE+DARK_BLUE_BG,
            text='No image was found that exactly matches the signed metadata '
            'from the Director and Image Repositories. Not keeping '
            'untrustworthy files. ' + repr(target_filepath), sound=TADA)
        import time
        time.sleep(3)


        # # If this was our firmware, notify that we're not installing.
        # if filepath.startswith('/') and filepath[1:] == firmware_filename or \
        #   not filepath.startswith('/') and filepath == firmware_filename:

        print()
        print(YELLOW + ' While the Director and Image Repository provided '
            'consistent metadata for new firmware,')
        print(' mirrors we contacted provided only untrustworthy images. ')
        print(GREEN + 'We have rejected these. Firmware not updated.\n' + ENDCOLORS)

      else:
        assert(os.path.exists(full_fname)), 'Programming error: no download ' + \
            'error, but file still does not exist.'
        print(GREEN + 'Successfully downloaded a trustworthy ' + repr(filepath) +
            ' image.' + ENDCOLORS)


        # TODO: <~> There is an attack vector here, potentially, for a minor
        # attack, but it's pretty strange. Finish thinking through it with a
        # test case later. If the Director specifies two target files with the
        # same path (which shouldn't really be possible with TUF, but people
        # will be reimplementing things), the second one to be downloaded can
        # replace the first file, and then we may distribute that to both
        # Secondaries (which will still validate the files and catch the
        # mistake, but... we will still potentially have disrupted one of them
        # if it receives an update that wasn't right in the first place.... It
        # may perhaps end up in limp-home mode or something....)

        # In any case, there may also be race conditions. The point is that
        # we are storing a downloaded file and we are also, separately storing
        # the verified file info. Perhaps we should check the file against the
        # fileinfo at the last moment, before we send it on to the Secondary.
        # That should provide some prophylaxis?




    # Package the consistent and validated metadata we have now into two
    # locations for Secondaries that will request it.
    # For Full-Verification Secondaries, we keep an archive of all the valid
    # metadata, in a separate location that we only move (rename) files to
    # when we have validated all the files and have a self-consistent set.
    # For Partial-Verification Secondaries, we save just the Director's targets
    # metadata file in a separate location.


    # Copy the Director's targets file and then rapidly move it into place,
    # since requests for this file from Secondaries will arrive asynchronously.

    # Put the new metadata into place for distribution.
    # This entails archiving all metadata for full-metadata-verifying
    # Secondaries and copying just the Director's targets.json metadata file
    # for partial-verifying Secondaries. In both cases, the files are swapped
    # into place atomically after being constructed or copied. Secondaries
    # may be requesting these files live.
    self.save_distributable_metadata_files()





  def get_image_fname_for_ecu(self, ecu_serial):
    """
    Given an ECU serial, returns:
      - None if there is no image file to be distributed to that ECU
      - Else, a filename for the image file to distribute to that ECU
    """

    if not self.update_exists_for_ecu(ecu_serial):
      return None

    # Else, there is data to provide to the Secondary.

    # Get the full filename of the image file on disk.
    filepath = self.assigned_targets[ecu_serial]['filepath']
    if filepath[0] == '/': # Prune / at start. It's relative to the targets dir.
      filepath = filepath[1:]

    return os.path.join(self.full_client_dir, 'targets', filepath)





  def get_full_metadata_archive_fname(self):
    """
    Returns the absolute-path filename of an archive file (currently zip)
    containing all metadata from repositories necessary for a Full-Verification
    Secondary ECU to validate target files.

    The file is continuously available to asynchronous requests; it is
    replaced by atomic rename on POSIX-compliant systems, only once a new
    file is completely written. If this Primary has never completed an update
    cycle, it will not exist yet.

    Normally, for a reference implementation, it would be preferable to deal in
    the data itself, in memory, but for the time being, it is more convenient in
    maintaining the interfaces with TUF and demonstration code to do this with
    an archive file.
    """
    return self.distributable_full_metadata_archive_fname





  def get_partial_metadata_fname(self):
    """
    Returns the absolute-path filename of the Director's targets.json metadata
    file, necessary for performing partial validation of target files (as a
    weak - "partial validation" - Secondary ECU would.

    The file is continuously available to asynchronous requests; it is
    replaced by atomic rename on POSIX-compliant systems, only once a new
    file is completely written. If this Primary has never completed an update
    cycle, it will not exist yet.
    """
    return self.distributable_partial_metadata_fname





  def update_exists_for_ecu(self, ecu_serial):
    """
    Returns True if the Director has sent us instructions for the Secondary ECU
    specified, else returns False.

    <Exceptions>
      uptane.UnknownECU
        if the ecu_serial specified is not one known to this Primary (i.e. is
        not in self.my_secondaries).

      tuf.FormatError
        if ecu_serial does not match uptane.formats.ECU_SERIAL_SCHEMA

    <Side-effects>
      Ensures that ecu_serial has the right format.
    """

    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)

    if ecu_serial not in self.my_secondaries:
      raise uptane.UnknownECU(
          'Received a request for an update for a Secondary ECU (' +
          repr(ecu_serial) + ') of which this Primary is not aware.')

    elif ecu_serial not in self.assigned_targets:
      log.info(
          'Received request for an update for a Secondary ECU (' +
          repr(ecu_serial) + ') for which this Primary has no update '
          'instructions from the Director.')
      return False

    else:
      return True






  def get_last_timeserver_attestation(self):
    """
    Returns the most recent validated timeserver attestation.
    If the Primary has never received a valid timeserver attestation, this
    returns None.
    """
    if not self.all_valid_timeserver_attestations:
      return None

    most_recent_attestation = self.all_valid_timeserver_attestations[-1]

    # We've been storing the time attestation as a simple JSON-compatible
    # dictionary. If the format of transfered metadata is expected to be
    # ASN.1/DER, we convert the time attestation back to DER and return it in
    # that form.
    if tuf.conf.METADATA_FORMAT == 'der':
      converted_attestation = asn1_codec.convert_signed_metadata_to_der(
          most_recent_attestation, datatype='time_attestation')
      uptane.formats.DER_DATA_SCHEMA.check_match(converted_attestation)
      return converted_attestation

    elif tuf.conf.METADATA_FORMAT == 'json':
      uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
          most_recent_attestation)
      return most_recent_attestation

    else:
      raise uptane.Error('Unable to convert time attestation as configured. '
          'The settings supported for timeserver attestations are "json" and '
          '"der", but the value of tuf.conf.METADATA_FORMAT is: ' +
          repr(tuf.conf.METADATA_FORMAT))





  def generate_signed_vehicle_manifest(self):
    """
    Put ECU manifests into a vehicle manifest and sign it.
    Support multiple manifests from the same ECU.
    Output will comply with uptane.formats.VEHICLE_VERSION_MANIFEST_SCHEMA.
    """

    # Create the vv manifest:
    vehicle_manifest = {
        'vin': self.vin,
        'primary_ecu_serial': self.ecu_serial,
        'ecu_version_manifests': self.ecu_manifests
    }

    uptane.formats.VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(vehicle_manifest)

    # Wrap the vehicle version manifest object into an
    # uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA and check format.
    # {
    #     'signed': vehicle_manifest,
    #     'signatures': []
    # }
    signable_vehicle_manifest = tuf.formats.make_signable(vehicle_manifest)
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        signable_vehicle_manifest)
    if tuf.conf.METADATA_FORMAT == 'der':
      # Convert to DER and sign, replacing the Python dictionary.
      signable_vehicle_manifest = asn1_codec.convert_signed_metadata_to_der(
          signable_vehicle_manifest, private_key=self.primary_key,
          resign=True, datatype='vehicle_manifest')

    else:
      # If we're not using ASN.1, sign the Python dictionary in a JSON encoding.
      uptane.common.sign_signable(
          signable_vehicle_manifest,
          [self.primary_key],
          datatype='vehicle_manifest')

      uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
          signable_vehicle_manifest)

    # Now that the ECU manifests have been incorporated into a vehicle manifest,
    # discard the ECU manifests.

    self.ecu_manifests = dict()
    return signable_vehicle_manifest





  def register_new_secondary(self, ecu_serial):
    """
    Currently called by Secondaries, but one would expect that this would happen
    through some other mechanism when a new Secondary ECU is installed in the
    vehicle.
    """
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)

    if ecu_serial in self.my_secondaries:
      log.info('ECU Serial ' + repr(ecu_serial) + ' already registered with '
          'this Primary.')
      return

    self.my_secondaries.append(ecu_serial)
    log.debug('ECU Serial ' + repr(ecu_serial) + ' has been registered as '
        'a Secondary with this Primary.')





  def _check_ecu_serial(self, ecu_serial):
    """
    Make sure the given ecu_serial is correctly formatted and known.

    <Exceptions>

      tuf.FormatError
        if the given ecu_serial is not of the correct format

      uptane.UnknownECU
        if the given ecu_serial is not registered with this Primary

    """
    # Check argument format.
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)

    if ecu_serial not in self.my_secondaries:
      raise uptane.UnknownECU("The given ECU is not in this Primary's list of "
          "known Secondary ECUs. Register the ECU with this Primary first.")




  def register_ecu_manifest(
      self, vin, ecu_serial, nonce, signed_ecu_manifest, force_pydict=False):
    """
    Called by Secondaries (in the demo, this is via an XMLRPC interface, or
    through another interface and passed through the XMLRPC interface).

    The Primary need not track ECU serials, so calling this doesn't result in a
    verification of the ECU's signature on the ECU manifest. This information
    is bundled together in a single vehicle report to the Director service.

    Exceptions:
      uptane.Spoofing     if ECU Serials within the manifest are inconsistent
      uptane.UnknownECU   if the manifest is from an ECU that is not one of our
                          Secondaries
      uptane.Error        if the VIN for the report is not the same as our VIN
    """
    # check arg format and that serial is registered
    self._check_ecu_serial(ecu_serial)
    tuf.formats.BOOLEAN_SCHEMA.check_match(force_pydict)

    if vin != self.vin:
      raise uptane.Error('Received an ECU Manifest supposedly hailing from a '
          'different vehicle....')

    if tuf.conf.METADATA_FORMAT == 'der' and not force_pydict:
      # If we're working with ASN.1/DER, convert it into the format specified in
      # uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.
      signed_ecu_manifest = asn1_codec.convert_signed_der_to_dersigned_json(
          signed_ecu_manifest, datatype='ecu_manifest')

    # Else, we're working with standard Python dictionaries and no conversion
    # is necessary.

    if ecu_serial != signed_ecu_manifest['signed']['ecu_serial']:
      # TODO: Choose an exception class.
      raise uptane.Spoofing('Received a spoofed or mistaken manifest: supposed '
          'origin ECU (' + repr(ecu_serial) + ') is not the same as what is '
          'signed in the manifest itself (' +
          repr(signed_ecu_manifest['signed']['ecu_serial']) + ').')

    # If we haven't errored out above, then the format is correct, so save
    # the manifest to the Primary's dictionary of manifests.
    if ecu_serial in self.ecu_manifests:
      self.ecu_manifests[ecu_serial].append(signed_ecu_manifest)
    else:
      self.ecu_manifests[ecu_serial] = [signed_ecu_manifest]

    # And add the nonce the Secondary provided to the list of nonces to send
    # in the next Timeserver request.
    if nonce not in self.nonces_to_send:
      self.nonces_to_send.append(nonce)


    log.debug(GREEN + ' Primary received an ECU manifest from ECU ' +
        repr(ecu_serial) + ', along with nonce ' + repr(nonce) + ENDCOLORS)

    # Alert if there's been a detected attack.
    if signed_ecu_manifest['signed']['attacks_detected']:
      log.warning(YELLOW + ' Attacks have been reported by the Secondary! \n '
          'Attacks listed by ECU ' + repr(ecu_serial) + ':\n ' +
          signed_ecu_manifest['signed']['attacks_detected'] + ENDCOLORS)





  def get_nonces_to_send_and_rotate(self):
    """
    This should be called once when it is time to make a request for a signed
    attestation from the Timeserver.
    It:
     - returns the set of nonces to include in that request
     - registers those as sent (replaces self.nonces_sent with them)
     - empties self.nonces_to_send, to be populated from new messages from
       Secondaries.
    """
    self.nonces_sent = self.nonces_to_send
    self.nonces_to_send = []
    return self.nonces_sent





  def validate_time_attestation(self, timeserver_attestation):
    """
    This should be called after get_nonces_to_send_and_rotate has been called
    and the nonces returned from that have been sent in a request for a time
    attestation from the Timeserver.

    The response from the Timeserver should then be provided to this function
    to be validated.

    If timeserver_attestation is correctly signed by the expected Timeserver
    key, and it lists all the nonces we expected it to list (those returned
    by the previous call to get_nonces_to_send_and_rotate), then the Primary's
    time is updated and the attestation will be saved so that it can be provided
    to Secondaries.

    If the Primary is using ASN.1/DER metadata, then timeserver_attestation is
    expected to be in that format, as a byte string.
    Otherwise, we're using simple Python dictionaries and timeserver_attestation
    conforms to uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.
    """

    # If we're using DER format, convert the attestation into something
    # comprehensible instead.
    if tuf.conf.METADATA_FORMAT == 'der':
      timeserver_attestation = asn1_codec.convert_signed_der_to_dersigned_json(
          timeserver_attestation)

    # Check format.
    uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
        timeserver_attestation)


    # Assume there's only one signature. This assumption is made for simplicity
    # in this reference implementation. If the Timeserver needs to sign with
    # multiple keys for some reason, that can be accomodated.
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

    for nonce in self.nonces_sent:
      if nonce not in timeserver_attestation['signed']['nonces']:
        # TODO: Determine whether or not to add something to self.attacks_detected
        # to indicate this problem. It's probably not certain enough? But perhaps
        # we should err on the side of reporting.
        # TODO: Create a new class for this Exception in this file.
        raise uptane.BadTimeAttestation('Timeserver returned a time attestation'
            ' that did not include one of the expected nonces. This time is '
            'questionable and will not be registered. If you see this '
            'persistently, it is possible that there is a Man in the Middle '
            'attack underway.')


    # Extract actual time from the timeserver's signed attestation.
    new_timeserver_time = timeserver_attestation['signed']['time']

    # Save validated time.
    self.all_valid_timeserver_times.append(new_timeserver_time)

    # Save the attestation itself as well, to provide to Secondaries (who need
    # not trust us).
    self.all_valid_timeserver_attestations.append(timeserver_attestation)





  def save_distributable_metadata_files(self):
    """
    Generates a zip archive of the metadata files validated by this Primary,
    for distribution to full verifying Secondaries. The particular method of
    distributing this metadata to Secondaries will vary greatly depending on
    one's setup, and is left to implementers.
    """

    metadata_base_dir = os.path.join(self.full_client_dir, 'metadata')

    # Save a zipped version of all of the metadata.
    # Note that some stale metadata may be retained, but should never affect
    # security. Worth confirming.
    # What we want here, basically, is:
    #  <full_client_dir>/metadata/*/current/*.json
    with zipfile.ZipFile(self.temp_full_metadata_archive_fname, 'w') \
        as archive:
      # For each repository directory within the client metadata directory
      for repo_dir in os.listdir(metadata_base_dir):
        # Construct path to "current" metadata directory for that repository in
        # the client metadata directory, relative to Uptane working directory.
        abs_repo_dir = os.path.join(metadata_base_dir, repo_dir, 'current')
        if not os.path.isdir(abs_repo_dir):
          continue

        # Add each role metadata file to the archive.
        for role_fname in os.listdir(abs_repo_dir):
          # Reconstruct file path relative to Uptane working directory.
          role_abs_fname = os.path.join(abs_repo_dir, role_fname)

          # Make sure it's the right type of file. Should be a file, not a
          # directory. Symlinks are OK. Should end in an extension matching
          # tuf.conf.METADATA_FORMAT (presumably .json or .der, depending on
          # that setting).
          if not os.path.isfile(role_abs_fname) or not role_abs_fname.endswith(
              '.' + tuf.conf.METADATA_FORMAT):
            # Consider special error type.
            raise uptane.Error('Unexpected file type in a metadata '
                'directory: ' + repr(role_abs_fname) + ' Expecting only ' +
                tuf.conf.METADATA_FORMAT + 'files.')

          # Write the file to the archive, adjusting the path in the archive so
          # that when expanded, it resembles repository structure rather than
          # a client directory structure.
          archive.write(
              role_abs_fname,
              os.path.join(repo_dir, 'metadata', role_fname))


    # Copy the Director's targets file to a temp location for partial-verifying
    # Secondaries.
    director_targets_file = os.path.join(
        self.full_client_dir,
        'metadata',
        self.director_repo_name,
        'current',
        'targets.' + tuf.conf.METADATA_FORMAT)
    if os.path.exists(self.temp_partial_metadata_fname):
      os.remove(self.temp_partial_metadata_fname)
    shutil.copyfile(director_targets_file, self.temp_partial_metadata_fname)

    # Now move both files into place. For each file, this happens atomically
    # on POSIX-compliant systems and replaces any existing file.
    os.rename(
        self.temp_partial_metadata_fname,
        self.distributable_partial_metadata_fname)
    os.rename(
        self.temp_full_metadata_archive_fname,
        self.distributable_full_metadata_archive_fname)





def enforce_jail(fname, expected_containing_dir):
  """
  DO NOT ASSUME THAT THIS FUNCTION IS SECURE.
  """
  # Make sure it's in the expected directory.
  abs_fname = os.path.abspath(os.path.join(expected_containing_dir, fname))
  if not abs_fname.startswith(os.path.abspath(expected_containing_dir)):
    raise ValueError('Expected a filename in directory ' +
        repr(expected_containing_dir) + '. When appending ' + repr(fname) +
        ' to the given directory, the result was not in the given directory.')

  else:
    return abs_fname
