"""
<Program Name>
  timeserver.py

<Purpose>
  Acts as an Uptane-compliant Timeserver:
   -Listens for requests from vehicles.
   -Receives a list of nonces and responds with a signed time attestation
    that lists those nonces.

  Currently, this module contains both core and demo code.

"""


import tuf
import time # for sleep
import uptane
import uptane.director.inventorydb as inventorydb
import uptane.formats
import json
import time
#import asn1_conversion as asn1

import tuf.repository_tool as rt
# CONSTANTS
TIMESERVER_HOST = 'localhost'
TIMESERVER_PORT = 30601


import xmlrpc.server
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import uptane.common  # for sign_signable and canonical_key_from_pub_and_pri

timeserver_key = None

# Restrict director requests to a particular path.
# Must specify RPC2 here for the XML-RPC interface to work.
class RequestHandler(SimpleXMLRPCRequestHandler):
  rpc_paths = ('/RPC2',)



# For the demo
def listen(use_new_keys=False):
  """
  Listens on TIMESERVER_PORT for xml-rpc calls to functions:
   - get_signed_time(nonces)
  """

  print('Loading timeserver signing key.')
  load_timeserver_key(use_new_keys)
  print('Timeserver signing key loaded.')

  # Create server
  server = SimpleXMLRPCServer((TIMESERVER_HOST, TIMESERVER_PORT),
      requestHandler=RequestHandler)#, allow_none=True)
  server.register_introspection_functions()

  # Add a function to the Director's xml-rpc interface.
  # Register function that can be called via XML-RPC, allowing a Primary to
  # request the time for its Secondaries.
  server.register_function(get_signed_time, 'get_signed_time')
  server.register_function(get_signed_time_ber, 'get_signed_time_ber')

  print('Timeserver will now listen on port ' + str(TIMESERVER_PORT))
  server.serve_forever()



def load_timeserver_key(use_new_keys=False):

  global timeserver_key

  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('timeserver', password='pw')

  # Load in from the generated files.
  timeserver_key = rt.import_ed25519_privatekey_from_file(
      'timeserver', password='pw')

  #timeserver_key = uptane.common.canonical_key_from_pub_and_pri(
  #    key_pub, key_pri)
  tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_key) # Is this redundant?



def get_signed_time(nonces):
  uptane.formats.NONCE_LIST_SCHEMA.check_match(nonces)

  # Get the time, format it appropriately, and check the resulting format.
  # e.g. '2016-10-10T11:37:30Z'
  clock = tuf.formats.unix_timestamp_to_datetime(int(time.time()))
  clock = clock.isoformat() + 'Z'
  tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(clock)

  time_attestation = {
    'time': clock,
    'nonces': nonces
  }

  signable_time_attestation = tuf.formats.make_signable(time_attestation)
  uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
      signable_time_attestation)

  signable_time_attestation = uptane.common.sign_signable(
      signable_time_attestation, [timeserver_key])

  return signable_time_attestation



def get_signed_time_ber(nonces):
  """
  Same as get_signed_time, but re-encodes the resulting JSON into a BER
  file.
  """
  signable_time_attestation_in_json = get_signed_time(nonces)


  #from json2ber2json import *
  import timeservermetadata
  import timeserver

  json_signed = signable_time_attestation_in_json['signed']
  json_signatures = signable_time_attestation_in_json['signatures']
  asn_signed, ber_signed = timeserver.get_asn_and_ber_signed(timeservermetadata.get_asn_signed, json_signed)
  ber_metadata = timeserver.json_to_ber_metadata(asn_signed, ber_signed, json_signatures)
  # To decode on other side:
  # after_json = timeserver.ber_to_json_metadata(timeservermetadata.get_json_signed, ber_metadata)

  #signable_time_attestation_in_ber = \
  #    time_to_ber.get_asn_signed(signable_time_attestation_in_json)

  return ber_metadata



if __name__ == '__main__':
  listen()
