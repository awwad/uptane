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

suite = defaultTestLoader.discover(start_dir="tests")
result = TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
