"""
<Program Name>
  test_director.py

<Purpose>
  Unit testing for uptane/services/director.py

<Copyright>
  See LICENSE for licensing information.
"""
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

import unittest
import os.path
import shutil

import tuf
import tuf.formats
import tuf.conf

import uptane.formats
import uptane.services.director as director
# import uptane.common # verify sigs, create client dir structure, convert key
# import uptane.encoding.asn1_codec as asn1_codec

# For temporary convenience:
import demo # for generate_key, import_public_key, import_private_key

keys_pri = {'root': None, 'timestamp': None, 'snapshot': None, 'targets': None}
keys_pub = {'root': None, 'timestamp': None, 'snapshot': None, 'targets': None}

TEST_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'tests', 'test_data')
TEST_DIRECTOR_DIR = os.path.join(TEST_DATA_DIR, 'temp_test_director')



def destroy_temp_dir():
  # Clean up anything that may currently exist in the temp test directory.
  if os.path.exists(TEST_DIRECTOR_DIR):
    shutil.rmtree(TEST_DIRECTOR_DIR)





class TestDirector(unittest.TestCase):
  """
  "unittest"-style test class for the Director module in the reference
  implementation

  Please note that these tests are NOT entirely independent of each other.
  Several of them build on the results of previous tests. This is an unusual
  pattern but saves runtime and code.
  """
  # Class variables
  # key_timeserver_pub = None
  # key_timeserver_pri = None
  # initial_time = None
  # I'll initialize instance in the first test, and use it for later tests so
  # as to avoid repeated initialization.
  instance = None



  @classmethod
  def setUpClass(cls):
    """
    This is run once for the class, before all tests. Since there is only one
    class, this runs once. It prepares some variables and stores them in the
    class.
    """

    destroy_temp_dir()

    # Create a directory for the Director's files.
    os.makedirs(TEST_DIRECTOR_DIR)

    # Load public and private keys for the Director into module dictionaries
    # to use in testing.
    for role in ['root', 'timestamp', 'snapshot']:
      keys_pri[role] = demo.import_private_key('director' + role)
      keys_pub[role] = demo.import_public_key('director' + role)

    # Because the demo's Director targets key is not named correctly....
    # TODO: Remove this and add 'targets' back to the role list above when
    #       the key is correctly renamed.
    keys_pub['targets'] = demo.import_public_key('director')
    keys_pri['targets'] = demo.import_private_key('director')






  @classmethod
  def tearDownClass(cls):
    """
    This is run once for the class, after all tests. Since there is only one
    class, this runs once.
    """
    destroy_temp_dir()





  def test_01_init(self):
    """
    Unit test the Director() class constructor.
    """
    GOOD_ARGS = [
        TEST_DIRECTOR_DIR,      # director_repos_dir
        keys_pri['root'],       # key_root_pri
        keys_pub['root'],       # key_root_pub
        keys_pri['timestamp'],  # key_timestamp_pri
        keys_pub['timestamp'],  # key_timestamp_pub
        keys_pri['snapshot'],   # key_snapshot_pri
        keys_pub['snapshot'],   # key_snapshot_pub
        keys_pri['targets'],    # key_targets_pri
        keys_pub['targets']]    # key_targets_pub

    # None of those arguments may be integers, so:
    INVALID_ARG = 42

    # Try creating Director instances with invalid values, expecting errors.
    for i in range(len(GOOD_ARGS)):

      arguments = GOOD_ARGS[:i] + [INVALID_ARG] + GOOD_ARGS[i+1:]

      with self.assertRaises(tuf.FormatError):
        director.Director(*arguments)

    # TODO: Add interesting bad argument cases:
    #       - public key in place of private key and vice versa
    #       - nonexistent directory


    # Create a Director instance properly, expecting it to work. Save the
    # result as a class variable for future tests, to save time and code.
    TestDirector.instance = director.Director(*GOOD_ARGS)


    # Check the fields initialized in the instance to make sure they're correct.

    # Check values copied from parameters.
    self.assertEqual(TEST_DIRECTOR_DIR, TestDirector.instance.director_repos_dir)
    self.assertEqual(keys_pri['root'], TestDirector.instance.key_dirroot_pri)
    self.assertEqual(keys_pub['root'], TestDirector.instance.key_dirroot_pub)
    self.assertEqual(keys_pri['timestamp'], TestDirector.instance.key_dirtime_pri)
    self.assertEqual(keys_pub['timestamp'], TestDirector.instance.key_dirtime_pub)
    self.assertEqual(keys_pri['snapshot'], TestDirector.instance.key_dirsnap_pri)
    self.assertEqual(keys_pub['snapshot'], TestDirector.instance.key_dirsnap_pub)
    self.assertEqual(keys_pri['targets'], TestDirector.instance.key_dirtarg_pri)
    self.assertEqual(keys_pub['targets'], TestDirector.instance.key_dirtarg_pub)

    # Check values not copied from parameters.
    self.assertEqual({}, TestDirector.instance.vehicle_repositories)





  def test_05_register_ecu_serial(self):
    pass





  def test_10_validate_ecu_manifest(self):
    pass





  def test_15_register_vehicle_manifest(self):
    pass





  def test_20_validate_primary_certification_in_vehicle_manifest(self):
    pass





  def test_25_register_ecu_manifest(self):
    pass





  def test_30_add_new_vehicle(self):
    pass





  def test_35_create_director_repo_for_vehicle(self):
    pass





  def test_40_add_target_for_ecu(self):
    pass





# Run unit test.
if __name__ == '__main__':
  unittest.main()
