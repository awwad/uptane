"""
Demo-specific code
"""

# CONSTANTS
DIRECTOR_SERVER_HOST = 'localhost'
DIRECTOR_SERVER_PORT = 30101

import xmlrpc.server
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler


# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)


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
