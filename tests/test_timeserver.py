"""
<Program Name>
  test_timeserver.py

<Purpose>
  Unit testing for uptane/services/timeserver.py

<Copyright>
  See LICENSE for licensing information.
"""
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

import unittest
import time

import tuf
import tuf.formats

import uptane.formats
import uptane.encoding.asn1_codec as asn1_codec
import uptane.services.timeserver as timeserver

import demo # for generate_key, import_public_key, import_private_key



class TestTimeserver(unittest.TestCase):
  """
  "unittest"-style test class for the Timeserver module in the reference
  implementation
  """

  @classmethod
  def setUpClass(cls):
    """
    This is run once for the full class (and so the full module, which contains
    only one class), before all tests. It prepares some variables and stores
    them in the class.
    """

    # Load the keys for the test Timeserver.
    # cls.key_timeserver_pub = demo.import_public_key('timeserver')
    # cls.key_timeserver_pri = demo.import_private_key('timeserver')
    cls.timeserver_key = demo.import_private_key('timeserver')

    tuf.formats.ANYKEY_SCHEMA.check_match(cls.timeserver_key) # Is this redundant?

    timeserver.set_timeserver_key(cls.timeserver_key)





  def test_get_time(self):
    """ Test get_time, which returns an unsigned time attestation body. """

    basic_time_tests(
        timeserver.get_time, uptane.formats.TIMESERVER_ATTESTATION_SCHEMA, self)

    # TODO: Expand tests?





  def test_get_signed_time(self):

    basic_time_tests(
        timeserver.get_signed_time,
        uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA, self)

    # TODO: Check signature on time.





  def test_get_signed_time_der(self):

    basic_time_tests(
        timeserver.get_signed_time_der, uptane.formats.DER_DATA_SCHEMA, self)

    # TODO: Check encoding on time.

    # TODO: Check signature on time.

    # Now manually switch off PYASN1 support (for ASN.1/DER) and try again,
    # expecting an uptane.Error. Switch the setting back when finished.
    if timeserver.PYASN1_EXISTS:
      timeserver.PYASN1_EXISTS = False
      with self.assertRaises(uptane.Error):
        timeserver.get_signed_time_der([5])
      timeserver.PYASN1_EXISTS = True





  def test_set_timeserver_key(self):

    new_key_pub = demo.import_public_key('directorsnapshot')

    new_key = uptane.common.canonical_key_from_pub_and_pri(
        new_key_pub, demo.import_private_key('directorsnapshot'))

    tuf.formats.ANYKEY_SCHEMA.check_match(new_key)

    timeserver.set_timeserver_key(new_key)

    # Repeat two of the tests with the new key.
    t = self.test_get_signed_time()
    t_der = self.test_get_signed_time_der()

    # TODO: Check the signatures produced using the new public key,
    # new_key_pub.





def basic_time_tests(func, output_schema, cls): # cls: clunky
  """
  This non-class helper function takes as a third parameter the
  unittest.TestCase object whose functions (assertTrue etc) it can use. This is
  awkward and inappropriate. :P Find a different means of providing modularity
  instead of this one. (Can't just have this method in the class above because
  it would be run as a test. Could have default parameters and do that, but
  that's clunky, too.) Does unittest allow/test private functions in UnitTest
  classes?
  """


  nonces = [42, 93, 9010, 3, 6732319, 15, 1]

  t = func(nonces)

  output_schema.check_match(t)

  # Make sure we're using an actual clock (new time)
  time.sleep(1)
  t2 = func(nonces)
  cls.assertNotEqual(t, t2)

  # Try with an empty list of nonces provided.
  # Not clear if this should be acceptable behavior, but it should at least
  # not raise an error unless there is an appropriate error for it.
  t = func([])
  output_schema.check_match(t)

  # Try with list of nonces containing duplicates.
  # Not clear if this should be acceptable behavior, but it should at least
  # not raise an error unless there is an appropriate error for it.
  t = func([1, 42, 1])
  output_schema.check_match(t)
  t = func([1, 1])
  output_schema.check_match(t)


  # Make sure the function is testing its arguments.
  with cls.assertRaises(tuf.FormatError):
    t = func(None)
  with cls.assertRaises(tuf.FormatError):
    t = func('string_instead_of_list_of_integers')
  with cls.assertRaises(tuf.FormatError):
    t = func(42)





# Run unit tests.
if __name__ == '__main__':
  unittest.main()
