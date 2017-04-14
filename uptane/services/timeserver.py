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
import uptane.encoding.asn1_codec as asn1_codec
import tuf
PYASN1_EXISTS = False
try:
 import pyasn1.type
except ImportError:
 print('Minor: pyasn1 library not found. Proceeding using JSON only.')
else:
 #import uptane.ber_encoder as ber_encoder
 # TODO: Add the modules necessary to handle timeserver attestation ASN1
 # conversion to Uptane.
 PYASN1_EXISTS = True

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

  uptane.common.sign_signable(
      signable_time_attestation,
      [timeserver_key],
      datatype='time_attestation',
      metadata_format='json')

  return signable_time_attestation





def get_signed_time_der(nonces):
  """
  Same as get_signed_time, but converts the resulting Python dictionary into
  an ASN.1 representation, encodes it as DER (Distinguished Encoding Rules),
  replaces the signature with a signature over the hash of the DER encoding of
  the 'signed' portion of the data (the time and nonces).
  """
  if not PYASN1_EXISTS:
    raise uptane.Error('This Timeserver does not support DER: pyasn1 is not '
        'installed.')
  signable_time_attestation = get_signed_time(nonces)

  # Convert it, re-signing over the hash of the DER encoding of the attestation.
  der_attestation = asn1_codec.convert_signed_metadata_to_der(
      signable_time_attestation,
      private_key=timeserver_key,
      resign=True)


  return der_attestation
