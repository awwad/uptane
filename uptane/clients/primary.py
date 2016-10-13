"""
<Program Name>
  primary.py

<Purpose>
  An Uptane client modeling the behavior of a Primary ECU to distribute updates
  to Secondaries, collect ECU manifests, generate timeserver requests, etc.

"""

PRIMARY_SERVER_PORT = 30300

class Primary(object): # Consider inheriting from Secondary and refactoring.
  """
  Fields:
    
    self.ecu_manifests:
      A dictionary containing the manifests provided by all ECUs. Will include
      only the most recent copy. The Primary does not verify signatures on
      ECU manifests according to the Implementation Specification, and so
      these reports are succeptible to denial attacks from other, compromised
      ECUs (who can send bogus ECU manifests and replace a valid manifest from
      another ECU).
      
      There are deployment design choices that an OEM should consider. If
      assymmetric encryption is being used and the Primary has a public key for
      each ECU, the Primary may provide additional security by only storing ECU
      manifests if the signature matches the Primary's expectations, and so the
      most recent manifest is likely adequate. In other circumstances, it may
      be necessary to include a list of all manifests (excluding complete
      duplicates with the same time, etc, perhaps) and provide this to the
      Director. That would not match the Implementation Specification, however,
      which assumes that vehicle manifests contain one ECU manifest per ECU.
      
      # TODO: <~> Consider.

    self.director_proxy:
      An xmlrpc proxy for the director server, used to submit manifests.

    self.updater:
      A tuf.client.updater.Updater object used to retrieve metadata and
      target files from the Director and Supplier repositories.

    self.full_client_dir:
      The absolute directory where all client data is stored for the Primary.
      e.g. /Users/s/w/uptane/temp_primaryclient

    self.timeserver_public_key:
      The key we expect the timeserver to use.

    # self.nonces_sent
    #   The list of nonces sent to the Timeserver by our Secondaries,
    #   for an extra check.
  """

  def __init__(self,
        full_client_dir,  # '/Users/s/w/uptane/temp_primarymetadata'
        pinning_filename, # '/Users/s/w/uptane/pinned.json'
        vin,              # 'vin11111'
        ecu_serial,       # 'ecu00000'
        timeserver_public_key=None,
        director_public_key=None)

    # Check arguments:
    tuf.formats.RELPATH_SCHEMA.check_match(client_dir)
    uptane.formats.VIN_SCHEMA.check_match(vin)
    uptane.formats.ECU_SERIAL.check_match(ecu_serial)
    for key in [timeserver_public_key, director_public_key]:
      if key is not None:
        tuf.formats.ANYKEY_SCHEMA.check_match(key)

    self.vin = vin
    self.ecu_serial = ecu_serial
    self.full_client_dir = full_client_dir
    self.director_proxy = None
    self.most_recent_timeserver_time = None
    self.previous_timeserver_time = None
    self.all_timeserver_attestations = []
    self.timeserver_public_key = timeserver_public_key
    self.director_public_key = director_public_key

    # Initialize the dictionary of manifests. Since this is a dictionary indexed
    # by ECU serial and with value being a single manifest, we aren't keeping
    # multiple manifests per ECU. This has implications. See above, in the class
    # docstring's fields section.
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
        os.path.join(MAIN_REPO_DIR, 'metadata.staged', 'root.json'),
        os.path.join(CLIENT_METADATA_DIR_MAINREPO_CURRENT, 'root.json'))

    # Get the root.json file from the director repo (would come with this client).
    shutil.copyfile(
        os.path.join(DIRECTOR_REPO_DIR, 'metadata.staged', 'root.json'),
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






  def listen(self):
    """
    Listens on PRIMARY_SERVER_PORT for xml-rpc calls to functions:
      - get_test_value
      - submit_vehicle_manifest
    """

    # Create server
    server = SimpleXMLRPCServer((DIRECTOR_SERVER_HOST, DIRECTOR_SERVER_PORT),
        requestHandler=RequestHandler, allow_none=True)
    #server.register_introspection_functions()

    # # Register function that can be called via XML-RPC, allowing a Primary to
    # # submit a vehicle version manifest.
    # server.register_function(
    #     self.register_vehicle_manifest, 'submit_vehicle_manifest')

    # In the longer term, this won't be exposed: it will only be reached via
    # register_vehicle_manifest. For now, during development, however, this is
    # exposed.
    server.register_function(
      self.register_ecu_manifest, 'submit_ecu_manifest')

    print('Director will now listen on port ' + str(DIRECTOR_SERVER_PORT))
    server.serve_forever()




  def refresh_toplevel_metadata_from_repositories(self):
    self.updater.refresh()





  def get_target_list_from_director(self):
    # TODO: <~> MUST FIX FOR PRODUCTION! Note that this assumes that the
    # director is conveying information to this secondary in its target role.
    # This is not something we can assume - director repo structure is not
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





