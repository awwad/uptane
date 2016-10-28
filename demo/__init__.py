"""
__init__.py for the Uptane demo package
"""

import os

DEMO_KEYS_DIR = os.path.join(uptane.WORKING_DIR, 'demo', 'keys')

MAIN_REPO_HOST = 'http://192.168.1.124'
MAIN_REPO_PORT = 30301

DIRECTOR_REPO_HOST = 'http://192.168.1.124'
DIRECTOR_REPO_PORT = 30401

DIRECTOR_SERVER_HOST = '0.0.0.0' #'localhost'
DIRECTOR_SERVER_PORT = 30501

TIMESERVER_HOST = '0.0.0.0' #'localhost'
TIMESERVER_PORT = 30601

PRIMARY_SERVER_HOST = 'localhost' # demo stuff
PRIMARY_SERVER_PORT = 30701 # demo stuff

SECONDARY_SERVER_HOST = 'localhost' # demo stuff
SECONDARY_SERVER_PORT = 30801 # demo stuff

