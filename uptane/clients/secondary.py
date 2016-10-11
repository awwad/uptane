# Rewrite of secondaries.

import uptane.formats
import tuf.formats
import uptane.ber_encoder as ber_encoder
from uptane.common import sign_signable


import xmlrpc.client
import uptane.director.newdirector as director

import os # For paths and makedirs
import shutil # For copyfile
import tuf.client.updater
import tuf.repository_tool as rt
import tuf.keys

class Secondary(object):

  """
  Fields:
    
    self.director_proxy:
      An xmlrpc proxy for the director server, used to submit manifests.

    self.updater:
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the director and supplier repositories.

    self.client_dir:
      The directory in the working directory where all client data is stored
      for this secondary.

  """

  def __init__(self, client_dir):
    
    tuf.formats.RELPATH_SCHEMA.check_match(client_dir)
    
    self.client_dir = client_dir
    self.director_proxy = None

    #self.director_host = director.DIRECTOR_SERVER_HOST
    #self.director_port = director.DIRECTOR_SERVER_PORT

    WORKING_DIR = os.getcwd()
    CLIENT_DIR = os.path.join(WORKING_DIR, client_dir)
    CLIENT_METADATA_DIR_MAINREPO_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'current')
    CLIENT_METADATA_DIR_MAINREPO_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'mainrepo', 'previous')
    CLIENT_METADATA_DIR_DIRECTOR_CURRENT = os.path.join(CLIENT_DIR, 'metadata', 'director', 'current')
    CLIENT_METADATA_DIR_DIRECTOR_PREVIOUS = os.path.join(CLIENT_DIR, 'metadata', 'director', 'previous')
    #CLIENT_STUBREPO_DIR = os.path.join(CLIENT_DIR, 'stubrepos', '')

    # Note that the hosts and ports are drawn from pinned.json now.
    #MAIN_REPO_HOST = 'http://localhost'
    #MAIN_REPO_PORT = 30300
    #DIRECTOR_REPO_HOST = 'http://localhost'
    #DIRECTOR_REPO_PORT = 30301

    # We use these to fetch the root.json files for those repositories.
    MAIN_REPO_DIR = os.path.join(WORKING_DIR, 'repomain')
    #TARGETS_DIR = os.path.join(MAIN_REPO_DIR, 'targets')
    DIRECTOR_REPO_DIR = os.path.join(WORKING_DIR, 'repodirector')

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
        os.path.join(MAIN_REPO_DIR, 'metadata.staged', 'root.json'),
        os.path.join(CLIENT_METADATA_DIR_MAINREPO_CURRENT, 'root.json'))

    # Get the root.json file from the director repo (would come with this client).
    shutil.copyfile(
        os.path.join(DIRECTOR_REPO_DIR, 'metadata.staged', 'root.json'),
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



  def refresh_toplevel_metadata_from_repositories(self):
    self.updater.refresh()




  def get_target_list_from_director(self):
    # TODO: <~> MUST FIX FOR PRODUCTION! Note that this assumes that the
    # director is conveying information to this secondary in its target role.
    # This is not something we can assume - director repo structure is not
    # required to be that flat.
    directed_targets = self.updater.targets_of_role(
        rolename='targets', repo_name='repodirector')

    return directed_targets




  def get_validated_target_info(self, target_filepath):
    """
    Raises tuf.UnknownTargetError if a given filepath is not listed by the
    consensus of Director and Supplier (or through whichever trusted path is
    specified by this client's pinned.json file.) If info is returned, it
    will match tuf.formats.TARGETFILE_SCHEMA and will have been validated by
    all required parties.
    """
    tuf.formats.RELPATH_SCHEMA.check_match(target_filepath)
    return self.updater.target(target_filepath)





  def submit_ecu_manifest_to_director(self, ecu_manifest):

    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        ecu_manifest)
    # TODO: <~> Be sure to update the previous line to indicate an ASN.1
    # version of the ecu_manifest after encoders have been implemented.


    server = xmlrpc.client.ServerProxy(
        'http://' + str(director.DIRECTOR_SERVER_HOST) + ':' +
        str(director.DIRECTOR_SERVER_PORT))
    if not server.system.listMethods():
      raise Exception('Unable to connect to server.')

    s.submit_ecu_manifest(ecu_manifest)




  def _create_nonce(self):
    """Returns a pseudorandom number for use in protecting from replay attacks
    from the timeserver (or an intervening party)."""
    return random.randint(formats.NONCE_LOWER_BOUND, formats.NONCE_UPPER_BOUND)




  def generate_signed_ecu_manifest(self, installed_firmware_targetinfo, keys):
    """
    Takes a tuf.formats.TARGETFILE_SCHEMA (the target info for the firmware on
    an ECU) and returns a signed ECU manifest indicating that target file info,
    encoded in BER (requires code added to two ber_* functions below).
    """

    import uptane.formats
    import tuf.repository_tool as rt

    # We'll construct a signed signable_ecu_manifest_SCHEMA from the
    # targetinfo.
    # First, construct and check an ECU_VERSION_MANIFEST_SCHEMA.
    ecu_manifest = {
        'ecu_serial': '1111',
        'installed_image': installed_firmware_targetinfo,
        'timeserver_time': '2016-10-10T11:37:30Z',
        'previous_timeserver_time': '2016-10-10T11:37:30Z',
        'attacks_detected': ''
    }
    uptane.formats.ECU_VERSION_MANIFEST_SCHEMA.check_match(ecu_manifest)

    # Now we'll convert it into a signable object and sign it with a key we
    # generate.


    # TODO: Once the ber encoder functions are done, do this:
    original_ecu_manifest = ecu_manifest
    ecu_manifest = ber_encoder.ber_encode_ecu_manifest(ecu_manifest)

    # Wrap the ECU version manifest object into an
    # uptane.formats.signable_ecu_manifest and check the format.
    # {
    #     'signed': ecu_version_manifest,
    #     'signatures': []
    # }
    signable_ecu_manifest = tuf.formats.make_signable(
        ecu_manifest)
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signable_ecu_manifest)

    # Now sign with that key. (Also do ber encoding of the signed portion.)
    signed_ecu_manifest = sign_signable(ecu_manifest, keys)
    tuf.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)

    # TODO: Once the ber encoder functions are done, do this:
    original_signed_ecu_manifest = signed_ecu_manifest
    ber_encoded_signed_ecu_manifest = ber_encoder.ber_encode_signable_object(
        signed_ecu_manifest)

    return ber_encoded_signed_ecu_manifest
