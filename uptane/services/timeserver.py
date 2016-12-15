"""
<Program Name>
  timeserver.py

<Purpose>
  Provides core functionality to be used by an Uptane-compliant Timeserver.
  Initialized with a key, the Timeserver will, when given a list of nonces,
  return a signed time attestation that includes those nonces.

"""
from __future__ import unicode_literals

import uptane
import uptane.formats
import uptane.common  # for sign_signable and canonical_key_from_pub_and_pri
import tuf
import tuf.repository_tool as rt
#import asn1_conversion as asn1
#from uptane import GREEN, RED, YELLOW, ENDCOLORS

import time
#log = uptane.logging.getLogger('timeserver')

timeserver_key = None



def set_timeserver_key(private_key):

  global timeserver_key

  tuf.formats.ANYKEY_SCHEMA.check_match(private_key)

  # TODO: Add check to make sure it's a private key, not a public key.

  timeserver_key = private_key




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
  signable_time_attestation_as_dict = get_signed_time(nonces)


  #from json2ber2json import *
  import timeservermetadata
  import timeserver

  signed_dict = signable_time_attestation_as_dict['signed']
  dict_signatures = signable_time_attestation_as_dict['signatures']
  asn_signed, ber_signed = timeserver.get_asn_and_ber_signed(timeservermetadata.get_asn_signed, signed_dict)
  ber_metadata = timeserver.json_to_ber_metadata(asn_signed, ber_signed, dict_signatures)
  # To decode on other side:
  # dict_again = timeserver.ber_to_json_metadata(timeservermetadata.get_json_signed, ber_metadata)

  #signable_time_attestation_in_ber = \
  #    time_to_ber.get_asn_signed(signable_time_attestation_as_dict)

  return ber_metadata

