"""
<Program Name>
  director.py

<Purpose>
  Acts as the Uptane Director:
   -Listens for requests from vehicles.
   -Receives vehicle version manifests and stores them in an inventory database
   -Signs a piece of metadata indicating what a particular vehicle is to
    install and returns it to the vehicle

"""


import tuf
import time # for sleep
import uptane.director.inventorydb
import uptane.formats
import json
import xmlrpc.server
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
#import tuf.repository_tool as repotool
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
DIRECTOR_SERVER_PORT = 30101


# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)





class DirectorCore:
  """
  Foundational part of the reference implementation, CAN remain largely
  unchanged in real use. It is upon this that a full director is built to
  OEM specifications. A sample of such a Director is in the class
  Director below.

  The DirectorCore class basically exists to:
   - Translate a list of vehicle software assignments (roughly mapping ECU IDs
     to targets, but not quite: multiple possible images per ECU) into signed
     piece of metadata in the form of a director.json file suitable for sending
     to a vehicle.
     This is defined by uptane.formats.VEHICLE_SOFTWARE_ASSIGNMENTS_SCHEMA.
   - 

  (Does this need to be a class? Probably not. Probably clearer in the
  reference implementation, though. Could be that this class should be
  implemented by Director (class Director(DirectorCore):))

  """
  def write_director_metadata(self, vehicle_software_assignments):

    uptane.formats.VEHICLE_SOFTWARE_ASSIGNMENTS_SCHEMA.check_match(
        vehicle_software_assignments) # Check argument.

    raise NotImplementedError('Not yet written')

    #repo = tuf.repository_tool.load_repo(   )

    # load director keys only (grab code from uptane_tuf_server.py)
    # Call repository_tool internal functions to produce metadata
    # file.  /:  Ugly.
    # 



class Director:
  """
  This class is an example of Director functionality that an OEM may design.
  It employs DirectorCore (as they should).
  """



  def __init__(self, inventorydb = None):
    # if inventorydb is None:
    #   inventorydb = json.load()
    # self.inventorydb = {}
    pass




  def listen(self):
    """
    Listens on DIRECTOR_SERVER_PORT for xml-rpc calls to functions:
      - get_test_value
      - submit_vehicle_manifest
    """

    # Create server
    server = SimpleXMLRPCServer((DIRECTOR_SERVER_HOST, DIRECTOR_SERVER_PORT),
        requestHandler=RequestHandler)
    server.register_introspection_functions()

    # Add a function to the Director's xml-rpc interface.
    # This is just for debugging for now. We are not the timeserver.
    def get_test_value():
      return 'one million'
    server.register_function(get_test_value)

    # Register function that can be called via XML-RPC, allowing 
    server.register_function(uptane.director.inventorydb.save_vehicle_manifest,
        'submit_vehicle_manifest')

    print('Director will now listen on port ' + str(DIRECTOR_SERVER_PORT))
    server.serve_forever()




  def register_vehicle_manifest(self, manifest):
    raise NotImplementedError('Not yet written.')

  def write_metadata(self):
    raise NotImplementedError('Not yet written.')
    # Create a repo and partial write?
    # Has to be a more sensible way to do this, no.

  def create_keypair(self):
    raise NotImplementedError('Not yet written.')
    # Create a key pair or be provided one.







def main():
  d = Director()
  d.listen()



if __name__ == '__main__':
  main()
