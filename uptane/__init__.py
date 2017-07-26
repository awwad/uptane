"""
<Program Name>
  __init__.py

<Purpose>
  Defines Uptane common constants, exceptions, etc.
"""
from __future__ import print_function
from __future__ import unicode_literals

import logging, time # both for logging

 # Configure TUF to use DER format instead of Python dictionaries / JSON.
import tuf.conf
tuf.conf.METADATA_FORMAT = 'der'

# FIXME: I actually think other modules rely on the `os` imported here and
# not just for getcwd
import os # for getcwd only

from six.moves import getcwd
WORKING_DIR = getcwd()

### Exceptions
class Error(Exception):
  """
  Base class for all Uptane-specific exceptions.
  """
  pass

class UnknownVehicle(Error):
  """Received a message from an Vehicle with an unrecognized VIN."""
  pass

class UnknownECU(Error):
  """Received a message from an ECU with an unrecognized ECU Serial."""
  pass

class Spoofing(Error):
  """
  Received a message from an ECU that contains conflicting indications of
  what the source ECU's unique identifier is, or received an attempt to register
  an ECU that was already registered.
  """
  pass

class HardwareIDMismatch(Error):
  """
  Received an image install directed by director that doesn't match the HardwareID of the ECU.
  """
  pass

class ImageRollBack(Error):
  """
  Received an image to download with the Release Counter value lower than the one already installed.
  """
  pass

class BadTimeAttestation(Error):
  """
  Received a time attestation from a Timeserver that is not as expected. It may
  be missing an expected nonce in the nonce list, or it may be signed by am
  unrecognized key, for example.
  """
  pass

class FailedToDecodeASN1DER(Error):
  """
  Attempted to decode DER-encoded ASN.1 data and failed. It may be that the
  data has been corrupted, or that the decoding is attempting to use the
  wrong data type, or that the DER data is encoded with an outdated data
  definition (an older, incompatible version of Uptane's asn1_definitions.py).
  """
  pass

class FailedToEncodeASN1DER(Error):
  """
  Attempted to encode a Python dictionary as DER-encoded ASN.1 data and failed.
  It may be that the data has been corrupted, or that the decoding is
  attempting to use the wrong data type, or that the DER data is encoded with
  an outdated data definition (an older, incompatible version of Uptane's
  asn1_definitions.py).
  """
  pass


# Logging configuration

## General logging configuration:
_FORMAT_STRING = '[%(asctime)sUTC] [%(name)s] %(levelname)s '+\
    '[%(filename)s:%(funcName)s():%(lineno)s]\n%(message)s\n'
_TIME_STRING = "%Y.%m.%d %H:%M:%S"

## File logging configuration:
LOG_FILENAME = 'uptane.log'
file_handler = logging.FileHandler(LOG_FILENAME)
file_handler.setLevel(logging.DEBUG)
logging.Formatter.converter = time.gmtime
file_handler.setFormatter(logging.Formatter(_FORMAT_STRING, _TIME_STRING))

## Console logging configuration:
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(_FORMAT_STRING, _TIME_STRING))

## Logger instantiation
logger = logging.getLogger('uptane')
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

# Colorful printing for the logger for now.
RED = '\033[41m\033[30m' # black on red
GREEN = '\033[42m\033[30m' # black on green
YELLOW = '\033[93m' # yellow on black
ENDCOLORS = '\033[0m'

