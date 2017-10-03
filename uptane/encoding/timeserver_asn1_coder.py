"""
<Name>
  uptane/encoding/timeserver_asn1_coder.py

<Purpose>
  This module contains conversion functions (get_asn_signed and get_json_signed)
  for converting Timeserver time attestation metadata to and from TUF's standard
  Python dictionary metadata format (usually serialized as JSON) and an ASN.1
  format that conforms to pyasn1 specifications and Uptane's ASN.1 definitions.

<Functions>
  get_asn_signed(pydict_signed)
  get_json_signed(asn_signed)    # TODO: Rename to get_pydict_signed in all mods

"""
from __future__ import print_function
from __future__ import unicode_literals

from pyasn1.type import tag

from uptane.encoding.asn1_definitions import *

import calendar
from datetime import datetime


def get_asn_signed(json_signed):
  signed = TokensAndTimestamp()
  numberOfTokens = 0
  tokens = Tokens()
  for token in json_signed['nonces']:
    # Some damned bug in pyasn1 I could not care less to fix right now.
    tokens.setComponentByPosition(numberOfTokens, token, False)
    numberOfTokens += 1
  signed['numberOfTokens'] = numberOfTokens
  signed['tokens'] = tokens
  signed['timestamp'] = calendar.timegm(datetime.strptime(
      json_signed['time'], "%Y-%m-%dT%H:%M:%SZ").timetuple())

  return signed


def get_json_signed(asn_metadata):
  asn_signed = asn_metadata['signed']

  json_signed = {
    'time': datetime.utcfromtimestamp(asn_signed['timestamp']).isoformat() + 'Z'
  }

  numberOfTokens = int(asn_signed['numberOfTokens'])
  tokens = asn_signed['tokens']
  json_tokens = []
  for i in range(numberOfTokens):
    json_tokens.append(int(tokens[i]))
  json_signed['nonces'] = json_tokens

  return json_signed
