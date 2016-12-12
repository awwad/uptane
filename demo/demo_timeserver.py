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
from __future__ import print_function
from __future__ import unicode_literals

import demo
import uptane
import uptane.common
import tuf.formats

from six.moves import xmlrpc_server
import uptane.services.timeserver as timeserver


# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(xmlrpc_server.SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)





def load_timeserver_key(use_new_keys=False):
  if use_new_keys:
    demo.generate_key('timeserver')
  # Load in from the generated files (whether new or old).
  timeserver_key = demo.import_private_key('timeserver')
  tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_key) # Is this redundant?

  return timeserver_key




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
  server = xmlrpc_server.SimpleXMLRPCServer(
      (demo.TIMESERVER_HOST, demo.TIMESERVER_PORT),
      requestHandler=RequestHandler)#, allow_none=True)
  #server.register_introspection_functions()

  # Add a function to the Timeserver's xml-rpc interface.
  # Register function that can be called via XML-RPC, allowing a Primary to
  # request the time for its Secondaries.
  server.register_function(timeserver.get_signed_time, 'get_signed_time')
  server.register_function(timeserver.get_signed_time_ber, 'get_signed_time_ber')

  print('Timeserver will now listen on port ' + str(demo.TIMESERVER_PORT))
  server.serve_forever()




if __name__ == '__main__':
  listen()
