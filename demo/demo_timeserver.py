"""
<Program Name>
  demo_timeserver.py

<Purpose>
  Acts as an Uptane-compliant Timeserver:
   -Listens for requests from vehicles over XML-RPC.
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

import threading
from six.moves import xmlrpc_server
from six.moves import xmlrpc_client # for Binary data encapsulation
import uptane.services.timeserver as timeserver

# These two imports are used solely for testing relevant to DER encoding.
import uptane.encoding.asn1_codec as asn1_codec
import hashlib

from uptane.encoding.asn1_codec import DATATYPE_TIME_ATTESTATION

# Tell the reference implementation that we're in demo mode.
# (Provided for consistency.) Currently, primary.py in the reference
# implementation uses this to display banners for defenses that would otherwise
# be hard to notice. No other reference implementation code (secondary.py,
# director.py, etc.) currently uses this setting, but it could.
uptane.DEMO_MODE = True

LOG_PREFIX = uptane.WHITE + 'Timeserver:' + uptane.ENDCOLORS + ' '

timeserver_listener_thread = None

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





def get_signed_time_der_wrapper(nonces):
  """
  Encapsulates the binary data of the DER encoding of the timeserver attestation
  in an XMLPRC Binary object, for delivery via XMLRPC within the demo.

  This is only necessary when using DER format instead of the standard
  Uptane Python dictionary format.
  """

  der_attestation = timeserver.get_signed_time_der(nonces)

  return xmlrpc_client.Binary(der_attestation)





def listen(use_new_keys=False):
  """
  Listens on TIMESERVER_PORT for xml-rpc calls to functions:
   - get_signed_time(nonces)
  """

  global timeserver_listener_thread

  # Set the timeserver's signing key.
  print(LOG_PREFIX + 'Loading timeserver signing key.')
  timeserver.set_timeserver_key(load_timeserver_key(use_new_keys))
  print(LOG_PREFIX + 'Timeserver signing key loaded.')


  # Test locally before opening the XMLRPC port.
  test_demo_timeserver()


  # Create server
  server = xmlrpc_server.SimpleXMLRPCServer(
      (demo.TIMESERVER_HOST, demo.TIMESERVER_PORT),
      requestHandler=RequestHandler)#, allow_none=True)
  #server.register_introspection_functions()


  # Add a function to the Timeserver's xml-rpc interface.
  # Register function that can be called via XML-RPC, allowing a Primary to
  # request the time for its Secondaries.
  server.register_function(timeserver.get_signed_time, 'get_signed_time')
  server.register_function(
      get_signed_time_der_wrapper, 'get_signed_time_der')


  print(LOG_PREFIX + 'Timeserver will now listen on port ' +
      str(demo.TIMESERVER_PORT))

  timeserver_listener_thread = threading.Thread(target=server.serve_forever)
  timeserver_listener_thread.setDaemon(True)
  timeserver_listener_thread.start()





def test_demo_timeserver():
  """
  Test the demo timeserver.
  # TODO: Consider moving these tests into a demo integration test module.
  """
  # Prepare to validate signatures.
  timeserver_key_pub = demo.import_public_key('timeserver')
  tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_key_pub)


  # Fetch a normal signed time attestation, without ASN.1 format or DER
  # encoding, and validate the signature.
  signed_time = timeserver.get_signed_time([1, 2])

  assert len(signed_time['signatures']) == 1, 'Unexpected number of signatures.'
  assert uptane.common.verify_signature_over_metadata(
      timeserver_key_pub,
      signed_time['signatures'][0],
      signed_time['signed'],
      DATATYPE_TIME_ATTESTATION,
      metadata_format='json'
      ), 'Demo Timeserver self-test fail: unable to verify signature over JSON.'



  # Fetch a DER-encoded converted-to-ASN.1 signed time attestation, with a
  # signature over the DER encoding.
  der_signed_time = timeserver.get_signed_time_der([2, 9, 151])

  # Encapsulate that in a Binary object for XML-RPC.
  xb_der_signed_time = xmlrpc_client.Binary(der_signed_time)
  assert der_signed_time == xb_der_signed_time.data, \
      'Demo Timeserver self-test fail: xmlrpc Binary encapsulation issue'


  # Validate that signature.
  for pydict_again in [
      asn1_codec.convert_signed_der_to_dersigned_json(
          der_signed_time, DATATYPE_TIME_ATTESTATION),
      asn1_codec.convert_signed_der_to_dersigned_json(
          xb_der_signed_time.data, DATATYPE_TIME_ATTESTATION)]:

    assert uptane.common.verify_signature_over_metadata(
        timeserver_key_pub,
        pydict_again['signatures'][0],
        pydict_again['signed'],
        DATATYPE_TIME_ATTESTATION,
        metadata_format='der'
        ), 'Demo Timeserver self-test fail: unable to verify signature over DER'





if __name__ == '__main__':
  listen()
  timeserver_listener_thread.join()
