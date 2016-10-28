"""
<Program Name>
  demo_timeserver.py

<Purpose>
  Acts as an Uptane-compliant Timeserver:
   -Listens for requests from vehicles.
   -Receives a list of nonces and responds with a signed time attestation
    that lists those nonces.

  Currently, this module contains both core and demo code.

  Use:
    python demo_timeserver.py

    A bash script is also provided, so you could alternatively:
    ./run_timeserver.sh

"""

import uptane
import uptane.common
from demo_globals import *

import xmlrpc.server
import uptane.director.timeserver as timeserver


# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(xmlrpc.server.SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)





def load_timeserver_key(use_new_keys=False):
  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('timeserver', password='pw')
  # Load in from the generated files (whether new or old).
  timeserver_key = rt.import_ed25519_privatekey_from_file(
      'timeserver', password='pw')
  tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_key) # Is this redundant?





def listen(use_new_keys=False):
  """
  Listens on TIMESERVER_PORT for xml-rpc calls to functions:
   - get_signed_time(nonces)
  """

  # Set the timeserver's signing key.
  print('Loading timeserver signing key.')
  timeserver.set_timeserver_key(load_timeserver_key(use_new_keys))
  print('Timeserver signing key loaded.')

  # Create server
  server = xmlrpc.server.SimpleXMLRPCServer(
      (TIMESERVER_HOST, TIMESERVER_PORT),
      requestHandler=RequestHandler)#, allow_none=True)
  #server.register_introspection_functions()

  # Add a function to the Timeserver's xml-rpc interface.
  # Register function that can be called via XML-RPC, allowing a Primary to
  # request the time for its Secondaries.
  server.register_function(timeserver.get_signed_time, 'get_signed_time')
  server.register_function(timeserver.get_signed_time_ber, 'get_signed_time_ber')

  print('Timeserver will now listen on port ' + str(TIMESERVER_PORT))
  server.serve_forever()




if __name__ == '__main__':
  listen()
