"""
<Program Name>
  secondary.py

<Purpose>
  An Uptane client modeling the full behavior of a secondary ECU performing
  full metadata verification, as would be performed during ECU boot.
  Also includes some partial verification functionality.

"""
import uptane
import uptane.formats
import uptane.ber_encoder as ber_encoder
import uptane.common
import tuf.formats
import tuf.keys
import tuf.repository_tool as rt

import os # For paths and makedirs
import shutil # For copyfile
import random # for nonces

#log = uptane.logging.getLogger('secondary')

class Secondary(object):

  """
  Fields:

    self.updater:
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the Director and Supplier repositories.

    self.client_dir:
      The directory in the working directory where all client data is stored
      for this secondary.

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

    self.nonce_sent
      The last nonce the ECU sent to the Timeserver (via the Primary).


  Methods, as called: ("self" arguments excluded):

    __init__(...)

    rotate_nonces()

    generate_signed_ecu_manifest()

    _create_nonce()


  """

  def __init__(
    self,
    client_dir,
    ecu_serial,
    fname_root_from_mainrepo,
    fname_root_from_directorrepo,
    ecu_key,
    firmware_fileinfo=None,
    timeserver_public_key=None,
    director_public_key=None,
    partial_verifying=False,
    vin='vin1111'):

    # Check arguments:
    tuf.formats.RELPATH_SCHEMA.check_match(client_dir)
    tuf.formats.PATH_SCHEMA.check_match(fname_root_from_mainrepo)
    tuf.formats.PATH_SCHEMA.check_match(fname_root_from_directorrepo)
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    for key in [timeserver_public_key, director_public_key]:
      if key is not None:
        tuf.formats.ANYKEY_SCHEMA.check_match(key)

    self.ecu_key = ecu_key
    self.vin = vin
    self.ecu_serial = ecu_serial
    self.client_dir = client_dir
    self.director_proxy = None
    self.most_recent_timeserver_time = None
    self.previous_timeserver_time = None
    self.timeserver_public_key = timeserver_public_key
    self.director_public_key = director_public_key
    self.partial_verifying = partial_verifying
    self.attacks_detected = ''
    self.firmware_fileinfo = firmware_fileinfo

    if not self.partial_verifying and self.director_public_key is not None:
      raise Exception('Secondary not set as partial verifying, but a director ' # TODO: Choose error class.
          'key was still provided. Full verification secondaries employ the '
          'normal TUF verifications rooted at root metadata files.')

    WORKING_DIR = os.getcwd()
    CLIENT_DIR = os.path.join(WORKING_DIR, client_dir)
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

    # Add a pinned.json to this client (softlink it from a saved copy).
    os.symlink(
        os.path.join(WORKING_DIR, 'pinned.json'),
        os.path.join(CLIENT_DIR, 'metadata', 'pinned.json'))

    # Configure tuf with the client's metadata directories (where it stores the
    # metadata it has collected from each repository, in subdirectories).
    tuf.conf.repository_directory = CLIENT_DIR # This setting should probably be called client_directory instead, post-TAP4.

    # Create a TAP-4-compliant updater object. This will read pinning.json
    # and create single-repository updaters within it to handle connections to
    # each repository.
    self.updater = tuf.client.updater.Updater('updater')


    self.nonce_sent = None
    self.nonce_next = self._create_nonce()




  def rotate_nonces(self):
    self.nonce_sent = self.nonce_next
    self.nonce_next = self._create_nonce()


  def _create_nonce(self):
    """Returns a pseudorandom number for use in protecting from replay attacks
    from the timeserver (or an intervening party)."""
    return random.randint(
        uptane.formats.NONCE_LOWER_BOUND, uptane.formats.NONCE_UPPER_BOUND)



  # # This function will be split between the Primary and Secondary once the
  # # Primary is ready, and we will instead be retrieving this time from the
  # # Primary.
  # def update_time_from_timeserver(self, nonce):

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
        'timeserver_time': self.most_recent_timeserver_time,
        'previous_timeserver_time': self.previous_timeserver_time,
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
        signable_ecu_manifest, self.ecu_key)
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)

    # TODO: Once the ber encoder functions are done, do this:
    original_signed_ecu_manifest = signed_ecu_manifest
    ber_encoded_signed_ecu_manifest = ber_encoder.ber_encode_signable_object(
        signed_ecu_manifest)

    return ber_encoded_signed_ecu_manifest






  # def validate_new_image(self):
  #   """
  #   Given file_info for a new image, validate it against signed metadata.
  #   """
  #   raise NotImplementedError('Not yet written.')
