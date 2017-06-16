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

import uptane.encoding.asn1_codec as asn1_codec
import uptane.formats
import uptane.services.director as director
import uptane.services.inventorydb as inventory
# import uptane.common # verify sigs, create client dir structure, convert key
# import uptane.encoding.asn1_codec as asn1_codec

# For temporary convenience:
import demo # for generate_key, import_public_key, import_private_key

# The public and private keys to use during testing, including the Director
# repository keys (public and private) as well as client keys (public).
keys_pri = {}
keys_pub = {}

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

    # Load public keys for a Primary and some Secondaries and Primary, for use
    # in testing registration of ECUs and validation of manifests.
    for keyname in ['primary', 'secondary', 'secondary2']:
      keys_pub[keyname] = demo.import_public_key(keyname)





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

      arguments = GOOD_ARGS[:i] + [INVALID_ARG] + GOOD_ARGS[i + 1:]

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

    # Expect that the inventory db is currently empty.
    self.assertFalse(inventory.ecus_by_vin)
    self.assertFalse(inventory.ecu_public_keys)
    self.assertFalse(inventory.primary_ecus_by_vin)
    self.assertFalse(inventory.vehicle_manifests)
    self.assertFalse(inventory.ecu_manifests)





  def test_03_add_new_vehicle(self):

    vin = 'democar'

    # Expect that the inventory db is currently empty.
    # These checks are redundant (test_01_init tested this) and defensive.
    self.assertFalse(inventory.ecus_by_vin)
    self.assertFalse(inventory.ecu_public_keys)
    self.assertFalse(inventory.primary_ecus_by_vin)
    self.assertFalse(inventory.vehicle_manifests)
    self.assertFalse(inventory.ecu_manifests)

    # Register a new vehicle and expect success.
    # This also creates a TUF repository to provide Director metadata for
    # that vehicle.
    TestDirector.instance.add_new_vehicle(vin)
    os.chdir(uptane.WORKING_DIR)

    # Check resulting contents of inventorydb.
    self.assertIn(vin, inventory.ecus_by_vin)
    self.assertIn(vin, inventory.primary_ecus_by_vin)

    # Check resulting contents of Director - specifically, the new repository
    # for the vehicle.
    self.assertIn(vin, TestDirector.instance.vehicle_repositories)
    repo = TestDirector.instance.vehicle_repositories[vin]
    self.assertEqual(1, len(repo.root.keys))
    self.assertEqual(1, len(repo.timestamp.keys))
    self.assertEqual(1, len(repo.snapshot.keys))
    self.assertEqual(1, len(repo.targets.keys))
    # The repo hasn't been written yet, so the metadata file versions are 0.
    self.assertEqual(0, repo.root.version)
    self.assertEqual(0, repo.timestamp.version)
    self.assertEqual(0, repo.snapshot.version)
    self.assertEqual(0, repo.targets.version)
    self.assertEqual(keys_pub['root']['keyid'], repo.root.keys[0])
    self.assertEqual(keys_pub['timestamp']['keyid'], repo.timestamp.keys[0])
    self.assertEqual(keys_pub['snapshot']['keyid'], repo.snapshot.keys[0])
    self.assertEqual(keys_pub['targets']['keyid'], repo.targets.keys[0])

    # TODO: Consider delving into the TUF repository for tests.
    #       Probably shouldn't.





  def test_05_register_ecu_serial(self):

    vin = 'democar'

    # Expect no registered ECUs or manifests yet.
    self.assertFalse(inventory.ecu_public_keys)
    self.assertFalse(inventory.vehicle_manifests[vin])
    self.assertFalse(inventory.ecu_manifests)
    self.assertIsNone(inventory.primary_ecus_by_vin[vin])

    primary_serial = 'INFOdemocar'
    secondary_serial = 'TCUdemocar'

    GOOD_PRIMARY_ARGS = [
        primary_serial,        # ecu_serial
        keys_pub['primary'],   # ecu_key
        vin,                   # vin
        True]                  # is_primary

    GOOD_SECONDARY_ARGS = [
        secondary_serial,      # ecu_serial
        keys_pub['secondary'], # ecu_key
        vin,                   # vin
        False]                 # is_primary


    # Expect these calls to fail due to invalid argument format.
    # Note that none of the arguments should be integers.
    for i in range(4):

      bad_args = GOOD_PRIMARY_ARGS[:i] + [42] + GOOD_PRIMARY_ARGS[i + 1 :]
      with self.assertRaises(tuf.FormatError):
        TestDirector.instance.register_ecu_serial(*bad_args)

      bad_args = GOOD_SECONDARY_ARGS[:i] + [42] + GOOD_SECONDARY_ARGS[i + 1 :]
      with self.assertRaises(tuf.FormatError):
        TestDirector.instance.register_ecu_serial(*bad_args)


    # Expect this call to fail because the vehicle is not known to the Director
    with self.assertRaises(uptane.UnknownVehicle):
      bad_args = \
          GOOD_PRIMARY_ARGS[:2] + ['not_a_real_vin'] + GOOD_PRIMARY_ARGS[3:]
      TestDirector.instance.register_ecu_serial(*bad_args)



    # Register a Primary.
    TestDirector.instance.register_ecu_serial(*GOOD_PRIMARY_ARGS)

    # Test result of Primary registration in inventory.
    self.assertIn(vin, inventory.ecus_by_vin)
    self.assertIn(primary_serial, inventory.ecus_by_vin[vin])

    self.assertIn(vin, inventory.primary_ecus_by_vin)
    self.assertEqual(primary_serial, inventory.primary_ecus_by_vin[vin])

    self.assertIn(primary_serial, inventory.ecu_public_keys)
    self.assertEqual(
        keys_pub['primary'], inventory.ecu_public_keys[primary_serial])


    # Register a Secondary.
    TestDirector.instance.register_ecu_serial(*GOOD_SECONDARY_ARGS)

    # Test result of Secondary registration in inventory.
    # (The next two checks are redundant and defend possible future changes.)
    self.assertIn(vin, inventory.ecus_by_vin)
    self.assertIn(secondary_serial, inventory.ecus_by_vin[vin])

    self.assertIn(secondary_serial, inventory.ecu_public_keys)
    self.assertEqual(
        keys_pub['secondary'], inventory.ecu_public_keys[secondary_serial])


    # Due to a workaround for the demo website, the next checks will not work,
    # so we skip them. Currently, re-registering the same ECU is simply
    # ignored.
    # TODO: Resolve this issue: allow Spoofing errors to rise if an attempt is
    #       made to register an ECU Serial that is already registered, instead
    #       of ignoring the attempt.
    # # Expect these attempts to re-register the same ECUs to raise spoofing
    # # errors.
    # with self.assertRaises(uptane.Spoofing):
    #   TestDirector.instance.register_ecu_serial(*GOOD_PRIMARY_ARGS)
    # with self.assertRaises(uptane.Spoofing):
    #   TestDirector.instance.register_ecu_serial(*GOOD_SECONDARY_ARGS)





  def test_10_validate_ecu_manifest(self):

    # Load the sample manifest from ECU 'ecu11111'.

    if tuf.conf.METADATA_FORMAT == 'der':
      # Load the sample manifest from ECU 'ecu11111'.
      der_data = open(os.path.join('samples', 'sample_ecu_manifest_ecu11111.' +
          tuf.conf.METADATA_FORMAT), 'rb').read()

      # Use asn1_codec to convert to a JSON-compatible dictionary.
      sample_manifest = asn1_codec.convert_signed_der_to_dersigned_json(
          der_data, datatype='ecu_manifest')

    else:
      sample_manifest = tuf.util.load_file(os.path.join('samples',
          'sample_ecu_manifest_ecu11111.' + tuf.conf.METADATA_FORMAT))

    # Try validating with incorrectly formatted arguments, expecting error.
    for serial, manifest in [(42, 42), ('ecu11111', 42), (42, sample_manifest)]:
      with self.assertRaises(tuf.FormatError):
        TestDirector.instance.validate_ecu_manifest(serial, manifest)

    # Try validating a manifest that doesn't match the serial passed in as an
    # argument, expecting error.
    with self.assertRaises(uptane.Spoofing):
      TestDirector.instance.validate_ecu_manifest(
          'not_the_real_ecu_serial', sample_manifest)

    # Try validating the manifest now, before ECU 'ecu11111' is registered,
    # expecting an error.
    with self.assertRaises(uptane.UnknownECU):
      TestDirector.instance.validate_ecu_manifest('ecu11111', sample_manifest)

    # TODO: Try validating a manifest with a bad signature, expecting
    #       tuf.BadSignatureError.
    #       Using JSON, we can just tweak any value and try validating, but
    #       using DER we have to be more careful.
    #       The best answer is probably to change the public key listed for
    #       the ECU in the inventorydb so that the signed manifest signature
    #       is regarded as invalid because it's signed with the wrong key.

    # Register the ECU whose sample manifest we'll try to validate.
    TestDirector.instance.register_ecu_serial(
        'ecu11111', keys_pub['secondary'], 'democar', is_primary=False)

    # Attempt validation. If no error is raised, it was valid as expected.
    TestDirector.instance.validate_ecu_manifest('ecu11111', sample_manifest)





  def test_15_register_vehicle_manifest(self):
    pass





  def test_20_validate_primary_certification_in_vehicle_manifest(self):
    pass





  def test_25_register_ecu_manifest(self):
    pass





  def test_35_create_director_repo_for_vehicle(self):
    pass





  def test_40_add_target_for_ecu(self):
    pass





# Run unit test.
if __name__ == '__main__':
  unittest.main()
