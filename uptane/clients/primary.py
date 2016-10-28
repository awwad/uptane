"""
<Program Name>
  primary.py

<Purpose>
  An Uptane client modeling the behavior of a Primary ECU to distribute updates
  to Secondaries, collect ECU manifests, generate timeserver requests, etc.

"""
import uptane.formats
import tuf.formats
import uptane.ber_encoder as ber_encoder
from uptane.common import sign_signable

import uptane.services.director as director
import uptane.services.timeserver as timeserver

import os # For paths and makedirs
import shutil # For copyfile
import tuf.client.updater
import tuf.repository_tool as rt
import tuf.keys
import random # for nonces
from uptane import GREEN, RED, YELLOW, ENDCOLORS

log = uptane.logging.getLogger('primary')



class Primary(object): # Consider inheriting from Secondary and refactoring.
  """
  Fields:

    vin:
      Vehicle identification, whether "VIN" or some other unique identifier.
      Compliant with uptane.formats.VIN_SCHEMA

    ecu_serial:
      The identification string for this Primary ECU.
      Compliant with uptane.formats.ECU_SERIAL_SCHEMA

    ecu_manifests:
      A dictionary containing the manifests provided by all ECUs. Will include
      all manifests sent by all ECUs. The Primary does not verify signatures on
      ECU manifests according to the Implementation Specification.
      Compromised ECUs may send bogus ECU manifests, so we simply send all
      manifests to the Director, who will sort through and discern what is
      going on.

    updater:
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the Director and Supplier repositories.

    full_client_dir:
      The absolute directory where all client data is stored for the Primary.
      e.g. /Users/s/w/uptane/temp_primaryclient

    timeserver_public_key:
      The public key matching the private key that we expect the timeserver to
      use when signing attestations. Validation is against this key.

    # TODO: <~> This next field makes assumptions that are not in the Uptane
    #           specification, to handle some Sam code. Remove the assumption
    #           at some point. (The Primary config enum is outside the spec.)
    my_secondaries:
      This is a dictionary with an entry for every Secondary that this Primary
      communicates with.
      The dictionary maps ecu_serial to that ECU's number in the enumeration
      in the Primary's config file, for communication purposes.
      e.g. {
          'ecuserial1234': 0,
          'ecuserial5678': 1}

    nonces_to_send:
      The list of nonces sent to us from Secondaries and not yet sent to the
      Timeserver.

    nonces_sent:
      The list of nonces sent to the Timeserver by our Secondaries, which we
      have already sent to the Timeserver. Will be checked against the
      Timeserver's response.

    all_valid_timeserver_attestations:
      A list of all attestations received from Timeservers that have been
      validated by validate_time_attestation.
      Items are appended to the end.

    all_valid_timeserver_times:
      A list of all times extracted from all Timeserver attestations that have
      been validated by validate_time_attestation.
      Items are appended to the end.

  Use:
    import uptane.clients.primary as primary
    p = primary.Primary(
        full_client_dir='/Users/s/w/uptane/temp_primarymetadata',
        pinning_filename='/Users/s/w/uptane/demo/pinned.json',
        vin='vin11111',
        ecu_serial='ecu00000',
        fname_root_from_mainrepo='/Users/s/w/uptane/repomain/metadata/root.json',
        fname_root_from_directorrepo='/Users/s/w/uptane/repodirector/metadata/root.json',
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
    pinning_filename, # '/Users/s/w/uptane/pinned.json'
    vin,              # 'vin11111'
    ecu_serial,       # 'ecu00000'
    fname_root_from_mainrepo,
    fname_root_from_directorrepo,
    time,
    timeserver_public_key,
    my_secondaries=dict()):

    """
    See class docstring.
    """

    # Check arguments:
    tuf.formats.PATH_SCHEMA.check_match(full_client_dir)
    tuf.formats.PATH_SCHEMA.check_match(pinning_filename)
    tuf.formats.PATH_SCHEMA.check_match(fname_root_from_mainrepo)
    tuf.formats.PATH_SCHEMA.check_match(fname_root_from_directorrepo)
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_public_key)

    self.vin = vin
    self.ecu_serial = ecu_serial
    self.full_client_dir = full_client_dir
    self.all_valid_timeserver_times = [time]
    self.all_valid_timeserver_attestations = []
    self.timeserver_public_key = timeserver_public_key
    self.nonces_sent = []

    # Initialize the dictionary of manifests. This is a dictionary indexed
    # by ECU serial and with value being a list of manifests from that ECU, to
    # support the case in which multiple manifests have come from that ECU.
    self.ecu_manifests = {}

    CLIENT_DIR = full_client_dir
    CLIENT_METADATA_DIR_MAINREPO_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'current')
    CLIENT_METADATA_DIR_MAINREPO_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'previous')
    CLIENT_METADATA_DIR_DIRECTOR_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'director', 'current')
    CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'director', 'previous')

    # Note that the hosts and ports for the repositories are drawn from
    # pinned.json now. The services (timeserver and the director's
    # submit-manifest service) are still addressed here, though, currently
    # by pulling the constants from their modules directly
    # e.g. timeserver.TIMESERVER_PORT and director.DIRECTOR_SERVER_PORT).
    # Note that despite the vague name, the latter is not the director
    # repository, but a service that receives manifests.

    # Set up the TUF client directories for the two repositories.
    if os.path.exists(CLIENT_DIR):
      shutil.rmtree(CLIENT_DIR)

    for d in [
        CLIENT_METADATA_DIR_MAINREPO_CURRENT,
        CLIENT_METADATA_DIR_MAINREPO_PREVIOUS,
        CLIENT_METADATA_DIR_DIRECTOR_CURRENT,
        CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS]:
      os.makedirs(d)

    # Get the root.json file from the mainrepo (would come with this client).
    shutil.copyfile(
        fname_root_from_mainrepo,
        os.path.join(CLIENT_METADATA_DIR_MAINREPO_CURRENT, 'root.json'))

    # Get the root.json file from the director repo (would come with this client).
    shutil.copyfile(
        fname_root_from_directorrepo,
        os.path.join(CLIENT_METADATA_DIR_DIRECTOR_CURRENT, 'root.json'))

    # Add a pinned.json to this client (softlink it from the indicated copy).
    os.symlink(
        pinning_filename, #os.path.join(WORKING_DIR, 'pinned.json'),
        os.path.join(CLIENT_DIR, 'metadata', 'pinned.json'))

    # Configure tuf with the client's metadata directories (where it stores the
    # metadata it has collected from each repository, in subdirectories).
    tuf.conf.repository_directory = CLIENT_DIR # This setting should probably be called client_directory instead, post-TAP4.

    # Create a TUF-TAP-4-compliant updater object. This will read pinning.json
    # and create single-repository updaters within it to handle connections to
    # each repository.
    self.updater = tuf.client.updater.Updater('updater')






  def refresh_toplevel_metadata_from_repositories(self):
    self.updater.refresh()





  def get_target_list_from_director(self):
    # TODO: <~> MUST FIX FOR PRODUCTION! Note that this assumes that the
    # Director is conveying information directly in its "targets" role.
    # This is not something we can assume - Director repo structure is not
    # required to be that flat.
    directed_targets = self.updater.targets_of_role(
        rolename='targets', repo_name='director')

    return directed_targets





  def get_validated_target_info(self, target_filepath):
    """
    Returns trustworthy target information for the given target file
    (specified by its file path). This information has been cleared according
    to the trust requirements of the pinning file (pinned.json) that this
    client is equipped with. In general, this means that the Director repository
    and the Supplier (mainrepo) repository have agreed on the file information
    (cryptographic hash and length).
    Raises tuf.UnknownTargetError if a given filepath is not listed by the
    consensus of Director and Supplier (or through whichever trusted path is
    specified by this client's pinned.json file.) If info is returned, it
    will match tuf.formats.TARGETFILE_SCHEMA and will have been validated by
    all required parties.
    """
    tuf.formats.RELPATH_SCHEMA.check_match(target_filepath)
    return self.updater.target(target_filepath)




  def send_image_to_secondary(self):
    """
    Send target file to the secondary through C intermediate
    """
    pass



  def get_image_for_ecu(self, ecu_serial):


    pass


  def get_metadata_for_ecu(self, ecu_serial):


    pass




  def generate_signed_vehicle_manifest(self, use_json=False):
    """
    Spool ECU manifests together into a vehicle manifest and sign it.
    Support multiple manifests from the same ECU.
    Output will comply with uptane.formats.VEHICLE_VERSION_MANIFEST_SCHEMA.
    """
    spooled_ecu_manifests = []

    for ecu_serial in self.ecu_manifests:
      for manifest in self.ecu_manifests[ecu_serial]:
        spooled_ecu_manifests.append(manifest)


    # Create the vv manifest:
    vehicle_manifest = {
        'vin': self.vin,
        'primary_ecu_serial': self.ecu_serial,
        'ecu_version_manifests': spooled_ecu_manifests
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

    # Now sign with that key. (Also do ber encoding of the signed portion.)
    signed_vehicle_manifest = sign_signable(signable_vehicle_manifest, keys)
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        signed_vehicle_manifest)

    if use_json:
      return signed_vehicle_manifest

    # TODO: Once the ber encoder functions are done, do this:
    original_signed_vehicle_manifest = signed_vehicle_manifest
    ber_signed_vehicle_manifest = ber_encoder.ber_encode_signable_object(
        signed_vehicle_manifest)

    return ber_signed_vehicle_manifest





  def register_ecu_manifest(self, vin, ecu_serial, nonce, signed_ecu_manifest):
    """
    Called by Secondaries through an XMLRPC interface, currently (or through
    another interface and passed through to this one).

    The Primary need not track ECU serials, so calling this doesn't result in a
    verification of the ECU's signature on the ECU manifest. This information
    is bundled together in a single vehicle report to the Director service.
    """
    # Check argument format.
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        signed_vehicle_manifest)

    if ecu_serial != signed_ecu_manifest['signed']['ecu_serial']:
      # TODO: Choose an exception class.
      raise Exception('Received a spoofed or mistaken manifest: supposed '
          'origin ECU (' + repr(ecu_serial) + ') is not the same as what is '
          'signed in the manifest itself (' +
          repr(signed_ecu_manifest['signed']['ecu_serial']) + ').')

    # If we haven't errored out above, then the format is correct, so save
    # the manifest to the Primary's dictionary of manifests.
    if ecu_serial in self.ecu_manifests:
      self.ecu_manifests[ecu_serial].append(signed_ecu_manifest)
    else:
      self.ecu_manifests[ecu_serial] = [signed_ecu_manifest]


    log.debug(GREEN + ' Primary received an ECU manifest from ECU ' +
        repr(ecu_serial) + ENDCOLORS)

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

    for nonce in self.nonces_sent:
      if nonce not in timeserver_attestation['signed']['nonces']:
        # TODO: Determine whether or not to add something to self.attacks_detected
        # to indicate this problem. It's probably not certain enough? But perhaps
        # we should err on the side of reporting.
        # TODO: Create a new class for this Exception in this file.
        raise Exception('Timeserver returned a time attestation that did not '
            'include one of the expected nonces. This time is questionable and'
            ' will not be registered. If you see this attack persistently, it '
            'is possible that there is a Man in the Middle attack underway.')


    # Extract actual time from the timeserver's signed attestation.
    new_timeserver_time = timeserver_attestation['signed']['time']

    # Save validated time.
    self.all_valid_timeserver_times.append(new_timeserver_time)

    # Save the attestation itself as well, to provide to Secondaries (who need
    # not trust us).
    self.all_valid_timeserver_attestations.append(timeserver_attestation)











  # def generate_timeserver_request(self):
  #   """
  #   Returns a request for a time attestation, to be sent to the Timeserver.
  #   This includes any nonces that Secondaries have sent to us.

  #   If we have no nonces from Secondaries, we abort and return None.
  #   """


  #   if not self.nonces_to_send:
  #     return None








  #   server = xmlrpc.client.ServerProxy(
  #       'http://' + str(timeserver.TIMESERVER_HOST) + ':' +
  #       str(timeserver.TIMESERVER_PORT))

  #   new_timeserver_attestation = server.get_signed_time([nonce]) # Primary

  #   # Check format.
  #   uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
  #       new_timeserver_attestation)

  #   # Assume there's only one signature.
  #   assert len(new_timeserver_attestation['signatures']) == 1


  #   # TODO: <~> Check timeserver signature using self.timeserver_public_key!
  #   valid = tuf.keys.verify_signature(
  #       self.timeserver_public_key,
  #       new_timeserver_attestation['signatures'][0],
  #       new_timeserver_attestation['signed'])

  #   if not valid:
  #     raise tuf.BadSignatureError('Timeserver returned an invalid signature. '
  #         'Time is questionable. If you see this persistently, it is possible '
  #         'that the Primary is compromised.')

  #   if not nonce in new_timeserver_attestation['signed']['nonces']:
  #     # TODO: Determine whether or not to add something to self.attacks_detected
  #     # to indicate this problem. It's probably not certain enough? But perhaps
  #     # we should err on the side of reporting.
  #     # TODO: Create a new class for this Exception in this file.
  #     raise Exception('Timeserver returned a time attestation that did not '
  #         'include our nonce. This time is questionable. Report to Primary '
  #         'may have been missed. If you see this persistently, it is possible '
  #         'that the Primary or Timeserver is compromised.')


  #   # Extract actual time from the timeserver's signed attestation.
  #   new_timeserver_time = new_timeserver_attestation['signed']['time']

  #   # Rotate last recorded times and save new time.
  #   self.previous_timeserver_time = self.most_recent_timeserver_time
  #   self.most_recent_timeserver_time = new_timeserver_time
