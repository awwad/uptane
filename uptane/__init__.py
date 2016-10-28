"""
<Program Name>
  __init__.py

<Purpose>
  Defines Uptane common constants, exceptions, etc.
"""

import logging, time # both for logging
import os # for getcwd only

WORKING_DIR = os.getcwd()

### Exceptions




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
console_handler.setLevel(logging.INFO)
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
