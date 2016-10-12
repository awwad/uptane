"""
<Program Name>
  director.py

<Purpose>
  Acts as the Uptane Director:
   -Listens for requests from vehicles.
   -Receives vehicle version manifests and stores them in an inventory database
   -Signs a piece of metadata indicating what a particular vehicle is to
    install and returns it to the vehicle

  Currently, this module contains both core and demo code.

"""


import tuf
import time # for sleep
import uptane
import uptane.director.inventorydb as inventorydb
import uptane.formats
import json
#import asn1_conversion as asn1

import tuf.repository_tool as rt
#import tuf.client.updater
#import uptane_tuf_server
#import os # for chdir
#import shutil # for copying
#import subprocess # to play a sound from the system

#from uptane_tuf_server import SERVER_PORT, ROOT_PATH, REPO_NAME, REPO_PATH
#from uptane_tuf_server import METADATA_LIVE_PATH
#from uptane_tuf_server import CLEAN_REPO_NAME, CLEAN_REPO_PATH, CLEAN_KEYS_DIR
#from uptane_tuf_server import CLEAN_METADATA_PATH, CLEAN_IMAGES_DIR


# CONSTANTS
DIRECTOR_SERVER_HOST = 'localhost'
DIRECTOR_SERVER_PORT = 30111

import xmlrpc.server
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler


# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)



# class DirectorCore:
#   """
#   Foundational part of the reference implementation, CAN remain largely
#   unchanged in real use. It is upon this that a full director is built to
#   OEM specifications. A sample of such a Director is in the class
#   Director below.

#   The DirectorCore class basically exists to:
#    - Translate a list of vehicle software assignments (roughly mapping ECU IDs
#      to targets, but not quite: multiple possible images per ECU) into signed
#      piece of metadata in the form of a director.json file suitable for sending
#      to a vehicle.
#      This is defined by uptane.formats.VEHICLE_SOFTWARE_ASSIGNMENTS_SCHEMA.
#    - 

#   (Does this need to be a class? Probably not. Probably clearer in the
#   reference implementation, though. Could be that this class should be
#   implemented by Director (class Director(DirectorCore):))

#   """
#   def write_director_metadata(self, vehicle_software_assignments):

#     uptane.formats.VEHICLE_SOFTWARE_ASSIGNMENTS_SCHEMA.check_match(
#         vehicle_software_assignments) # Check argument.

#     raise NotImplementedError('Not yet written')

#     #repo = tuf.repository_tool.load_repo(   )

#     # load director keys only (grab code from uptane_tuf_server.py)
#     # Call repository_tool internal functions to produce metadata
#     # file.  /:  Ugly.
#     # 



class Director:
  """
  This class is an example of Director functionality that an OEM may design.
  It employs DirectorCore (as they should).
  """


  def __init__(self, inventorydb = None):
    # if inventorydb is None:
    #   inventorydb = json.load()
    # self.inventorydb = {}

    self.load_keys()

    pass


  # For the demo
  def listen(self):
    """
    Listens on DIRECTOR_SERVER_PORT for xml-rpc calls to functions:
      - get_test_value
      - submit_vehicle_manifest
    """

    # Create server
    server = SimpleXMLRPCServer((DIRECTOR_SERVER_HOST, DIRECTOR_SERVER_PORT),
        requestHandler=RequestHandler, allow_none=True)
    #server.register_introspection_functions()

    # Register function that can be called via XML-RPC, allowing a Primary to
    # submit a vehicle version manifest.
    server.register_function(
        self.register_vehicle_manifest, 'submit_vehicle_manifest')

    # In the longer term, this won't be exposed: it will only be reached via
    # register_vehicle_manifest. For now, during development, however, this is
    # exposed.
    server.register_function(
      self.register_ecu_manifest, 'submit_ecu_manifest')

    print('Director will now listen on port ' + str(DIRECTOR_SERVER_PORT))
    server.serve_forever()







  def load_keys(self):
    """
    """
    self.key_dirroot_pub = rt.import_ed25519_publickey_from_file('directorroot.pub')
    self.key_dirroot_pri = rt.import_ed25519_privatekey_from_file('directorroot', password='pw')
    self.key_dirtime_pub = rt.import_ed25519_publickey_from_file('directortimestamp.pub')
    self.key_dirtime_pri = rt.import_ed25519_privatekey_from_file('directortimestamp', password='pw')
    self.key_dirsnap_pub = rt.import_ed25519_publickey_from_file('directorsnapshot.pub')
    self.key_dirsnap_pri = rt.import_ed25519_privatekey_from_file('directorsnapshot', password='pw')
    self.key_dirtarg_pub = rt.import_ed25519_publickey_from_file('director.pub')
    self.key_dirtarg_pri = rt.import_ed25519_privatekey_from_file('director', password='pw')





  def validate_ecu_manifest(self, ecu_serial, signed_ecu_manifest):
    """
    Arguments:
      ecuid: uptane.formats.ECU_SERIAL_SCHEMA
      manifest: uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA
    """
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        signed_ecu_manifest)

    # If it doesn't match expectations, error out here.

    # TODO: <~> COMPLETE ME. Process ECU signature here.
    #   - Get public (or symmetric) key from inventorydb
    #   - Call tuf.keys.validate_signature to validate the signature.
    print('Validation of manifests not yet fully implemented.')

    if ecu_serial != signed_ecu_manifest['signed']['ecu_serial']:
      # TODO: Choose an exception class.
      raise Exception('Received a spoofed or mistaken manifest: supposed '
          'origin ECU (' + repr(ecu_serial) + ') is not the same as what is '
          'signed in the manifest itself (' +
          repr(signed_ecu_manifest['signed']['ecu_serial']) + ').')





  def validate_vehicle_manifest(self, vin, signed_vehicle_manifest):
    """
    Arguments:
      vin: uptane.formats.VIN
      manifest: uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA
    """
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        signed_vehicle_manifest)

    # TODO: <~> COMPLETE ME.
    print('Validation of manifests not yet fully implemented.')

    # Process Primary's signature on full manifest here.
    # If it doesn't match expectations, error out here.

    # Validate individual ECU signatures on their version attestations.





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

    # Alert if there's been a detected attack.
    if signed_ecu_manifest['signed']['attacks_detected']:
      print('Attacks have been reported by the Secondary!')
      print('Attacks listed by ECU ' + repr(ecu_serial) + ':')
      print(signed_ecu_manifest['signed']['attacks_detected'])



  # This is called by the primary through an XMLRPC interface, currently.
  def register_vehicle_manifest(self, vin, signed_vehicle_manifest):

    # Check argument format.

    # Error out if the signature isn't valid and from the expected party.
    # Also checks argument format.
    self.validate_vehicle_manifest(vin, signed_vehicle_manifest)

    inventorydb.save_vehicle_manifest(vin, signed_vehicle_manifest)





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
    WORKING_DIR = os.getcwd()
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





  def analyze_vehicle(self, vin):
    """
    Make note of any unusual properties of the vehicle data and manifests.
    For example, try to detect freeze attacks and mix-and-match attacks.
    """
    pass


  def write_metadata(self):
    raise NotImplementedError('Not yet written.')
    # Perform repo.write() on repo for the vehicle.


  def create_keypair(self):
    raise NotImplementedError('Not yet written.')
    # Create a key pair or be provided one.







def main():
  d = Director()
  d.listen()



if __name__ == '__main__':
  main()
