#!/usr/bin/env python
"""
  <name>
    runtests.py

  <description>
    Test aggregator for the uptane tests

  <author>
    Santiago Torres-Arias <santiago@nyu.edu>

  <date>
    March 17, 2017
"""

from unittest import defaultTestLoader, TextTestRunner
import sys
import uptane

# Here, we can override the value of tuf.conf.METADATA_FORMAT for all tests we
# run. It can have values 'json' or 'der', and will change the TUF & Uptane
# configuration to cause TUF & Uptane to use this metadata format for the tests
# in this module (by setting tuf.conf.METADATA_FORMAT). When running these
# tests, it can be set by providing the argument 'json' or 'der' when calling
# this module:
# e.g.  python tests/runtests.py json
# or    python tests/runtests.py der
# Running this module without an argument will use the default format for
# Uptane, set in uptane/__init__.py to 'der'.
if len(sys.argv) > 2:
  raise uptane.Error('More arguments provided to runtests than allowed. Only '
      '0 or 1 command line arguments are supported. If provided, the sole '
      'command line argument for this test module is the metadata format to be '
      'used, "json" or "der".')
elif len(sys.argv) == 2:
  if sys.argv[1] in ['json', 'der']:
    uptane.tuf.conf.METADATA_FORMAT = sys.argv[1]
    print('Metadata Format set to ' + repr(sys.argv[1]))
  else:
    raise uptane.Error('Command-line argument not understood. Only '
        '"json" or "der" are allowed. Received: ' + repr(sys.argv[1]))



suite = defaultTestLoader.discover(start_dir="tests")
result = TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
