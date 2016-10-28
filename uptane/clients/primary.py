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

import uptane.director.director as director
import uptane.director.timeserver as timeserver

import os # For paths and makedirs
import shutil # For copyfile
import tuf.client.updater
import tuf.repository_tool as rt
import tuf.keys
#import random # for nonces

log = uptane.logging.getLogger('primary')



class Primary(object): # Consider inheriting from Secondary and refactoring.
  """
  Fields:

    self.ecu_manifests:
      A dictionary containing the manifests provided by all ECUs. Will include
      all manifests sent by all ECUs. The Primary does not verify signatures on
      ECU manifests according to the Implementation Specification.
      Compromised ECUs may send bogus ECU manifests, so we simply send all
      manifests to the Director, who will sort through and discern what is
      going on.

    self.updater:
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the Director and Supplier repositories.

    self.full_client_dir:
      The absolute directory where all client data is stored for the Primary.
      e.g. /Users/s/w/uptane/temp_primaryclient

    self.timeserver_public_key:
      The key we expect the timeserver to use.

    self.my_secondaries:
      A dictionary mapping ecu_serial to that ECU's number in the Primary's
      config file.

    self.nonces_sent
      The list of nonces sent to the Timeserver by our Secondaries,
      for an extra check.

  Use:
    import uptane.clients.primary as primary
    p = primary.Primary(
        full_client_dir='/Users/s/w/uptane/temp_primarymetadata',
        pinning_filename='/Users/s/w/uptane/pinned.json',
        vin='vin11111',
        ecu_serial='ecu00000',
        fname_root_from_mainrepo='/Users/s/w/uptane/repomain/metadata/root.json',
        fname_root_from_directorrepo='/Users/s/w/uptane/repodirector/metadata/root.json')

  """

  def __init__(self,
    full_client_dir,  # '/Users/s/w/uptane/temp_primarymetadata'
    pinning_filename, # '/Users/s/w/uptane/pinned.json'
    vin,              # 'vin11111'
    ecu_serial,       # 'ecu00000'
    fname_root_from_mainrepo,
    fname_root_from_directorrepo,
    timeserver_public_key=None,
    #director_public_key=None,
    my_secondaries=dict()):

    """
    See class docstring.
    """

    # Check arguments:
    tuf.formats.RELPATH_SCHEMA.check_match(full_client_dir)
    tuf.formats.PATH_SCHEMA.check_match(fname_root_from_mainrepo)
    tuf.formats.PATH_SCHEMA.check_match(fname_root_from_directorrepo)
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL_SCHEMA.check_match(ecu_serial)
    for key in [timeserver_public_key, director_public_key]:
      if key is not None:
        tuf.formats.ANYKEY_SCHEMA.check_match(key)

    self.vin = vin
    self.ecu_serial = ecu_serial
    self.full_client_dir = full_client_dir
    self.most_recent_timeserver_time = None
    self.previous_timeserver_time = None
    self.all_timeserver_attestations = []
    self.timeserver_public_key = timeserver_public_key
    self.director_public_key = director_public_key
    self.nonces_sent = []

    # Initialize the dictionary of manifests. This is a dictionary indexed
    # by ECU serial and with value being a list of manifests from that ECU, to
    # support the case in which multiple manifests have come from that ECU.
    self.ecu_manifests = {}

    #WORKING_DIR = os.getcwd()
    CLIENT_DIR = full_client_dir #os.path.join(WORKING_DIR, client_dir)
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

    # Create a TAP-4-compliant updater object. This will read pinning.json
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


