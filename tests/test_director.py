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
import copy
import json

import tuf
import tuf.formats
import tuf.conf

import uptane.encoding.asn1_codec as asn1_codec
import uptane.formats
import uptane.services.director as director
import uptane.services.inventorydb as inventory
# import uptane.common # verify sigs, create client dir structure, convert key

from uptane.encoding.asn1_codec import DATATYPE_TIME_ATTESTATION
from uptane.encoding.asn1_codec import DATATYPE_ECU_MANIFEST
from uptane.encoding.asn1_codec import DATATYPE_VEHICLE_MANIFEST

# For temporary convenience:
import demo # for generate_key, import_public_key, import_private_key

# The public and private keys to use during testing, including the Director
# repository keys (public and private) as well as client keys (public).
keys_pri = {}
keys_pub = {}

TEST_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'tests', 'test_data')
TEST_DIRECTOR_DIR = os.path.join(TEST_DATA_DIR, 'temp_test_director')
SAMPLES_DIR = os.path.join(uptane.WORKING_DIR, 'samples')


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

    # The VIN should be unknown to the inventory db.
    with self.assertRaises(uptane.UnknownVehicle):
      inventory.get_last_vehicle_manifest(vin)

    # Register a new vehicle and expect success.
    # This also creates a TUF repository to provide Director metadata for
    # that vehicle.
    TestDirector.instance.add_new_vehicle(vin)
    os.chdir(uptane.WORKING_DIR)

    # Check resulting contents of inventorydb.
    self.assertIn(vin, inventory.ecus_by_vin)
    self.assertIn(vin, inventory.primary_ecus_by_vin)
    # The VIN is now known, but there should be no Vehicle Manifests yet
    self.assertIsNone(inventory.get_last_vehicle_manifest(vin))

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


    # Expect no registered ECUs or manifests yet.
    self.assertFalse(inventory.ecu_public_keys)
    self.assertFalse(inventory.vehicle_manifests[vin])
    self.assertFalse(inventory.ecu_manifests)
    self.assertIsNone(inventory.primary_ecus_by_vin[vin])
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_ecu_public_key(primary_serial)
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_ecu_public_key(secondary_serial)
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_ecu_manifests(primary_serial)
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_ecu_manifests(secondary_serial)
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_last_ecu_manifest(primary_serial)
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_last_ecu_manifest(secondary_serial)



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
    self.assertEqual(
        keys_pub['primary'], inventory.get_ecu_public_key(primary_serial))

    # This should be empty, but should not raise an UnknownECU error now.
    self.assertFalse(inventory.get_ecu_manifests(primary_serial))
    self.assertIsNone(inventory.get_last_ecu_manifest(primary_serial))

    # Try registering the Primary again, expecting a Spoofing error.
    with self.assertRaises(uptane.Spoofing):
      TestDirector.instance.register_ecu_serial(*GOOD_PRIMARY_ARGS)


    # Register a Secondary.
    TestDirector.instance.register_ecu_serial(*GOOD_SECONDARY_ARGS)

    # Test result of Secondary registration in inventory.
    # (The next two checks are redundant and defend possible future changes.)
    self.assertIn(vin, inventory.ecus_by_vin)

    self.assertIn(secondary_serial, inventory.ecus_by_vin[vin])

    self.assertIn(secondary_serial, inventory.ecu_public_keys)

    self.assertEqual(
        keys_pub['secondary'], inventory.ecu_public_keys[secondary_serial])

    self.assertEqual(
        keys_pub['secondary'], inventory.get_ecu_public_key(secondary_serial))

    # There should be no ECU Manifests listed for the freshly-registered
    # ECU, but because the ECU is registered, we should not get an UnknownECU
    # error now:
    self.assertFalse(inventory.get_ecu_manifests(secondary_serial))
    self.assertIsNone(inventory.get_last_ecu_manifest(secondary_serial))


    # Try registering the Secondary again. We expect a Spoofing error
    # as with the Primary. We'll also make sure the registration didn't happen
    # regardless of the error, for historical reasons.
    n_ecu_keys = len(inventory.ecu_public_keys)
    # If this next line fails, there's likely a coding error in this test code.
    self.assertEqual(
        keys_pub['secondary'], inventory.get_ecu_public_key(secondary_serial))

    with self.assertRaises(uptane.Spoofing):
      TestDirector.instance.register_ecu_serial(*GOOD_SECONDARY_ARGS)

    self.assertEqual(n_ecu_keys, len(inventory.ecu_public_keys))
    # Now, if this fails, the second registration attempt has succeeded, and it
    # should NOT have! Registered keys should not be accidentally overwritten
    # with new keys.
    self.assertEqual(
        keys_pub['secondary'], inventory.get_ecu_public_key(secondary_serial))


    # Expect these attempts to re-register the same ECUs to raise spoofing
    # errors.
    with self.assertRaises(uptane.Spoofing):
      TestDirector.instance.register_ecu_serial(*GOOD_PRIMARY_ARGS)
    with self.assertRaises(uptane.Spoofing):
      TestDirector.instance.register_ecu_serial(*GOOD_SECONDARY_ARGS)





  def test_10_validate_ecu_manifest(self):

    # Load the sample manifest from ECU 'ecu11111'.

    if tuf.conf.METADATA_FORMAT == 'der':
      # Load the sample manifest from ECU 'ecu11111'.
      der_data = open(os.path.join('samples', 'sample_ecu_manifest_ecu11111.' +
          tuf.conf.METADATA_FORMAT), 'rb').read()

      # Use asn1_codec to convert to a JSON-compatible dictionary.
      sample_manifest = asn1_codec.convert_signed_der_to_dersigned_json(
          der_data, DATATYPE_ECU_MANIFEST)

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

    manifest_json = {
       "signatures": [{
         "keyid": "9a406d99e362e7c93e7acfe1e4d6585221315be817f350c026bbee84ada260da",
         "method": "ed25519",
         "sig": "335272f77357dc0e9f1b74d72eb500e4ff0f443f824b83405e2b21264778d1610e0a5f2663b90eda8ab05a28b5b64fc15514020985d8a93576fe33b287e1380f"}],
       "signed": {
        "primary_ecu_serial": "INFOdemocar",
        "vin": "democar",
        "ecu_version_manifests": {
         "TCUdemocar": [{
           "signatures": [{
             "keyid": "49309f114b857e4b29bfbff1c1c75df59f154fbc45539b2eb30c8a867843b2cb",
             "method": "ed25519",
             "sig": "fd04c1edb0ddf1089f0d3fc1cd460af584e548b230d9c290deabfaf29ce5636b6b897eaa97feb64147ac2214c176bbb1d0fa8bb9c623011a0e48d258eb3f9108"}],
           "signed": {
            "attacks_detected": "",
            "ecu_serial": "TCUdemocar",
            "previous_timeserver_time": "2017-05-18T16:37:46Z",
            "timeserver_time": "2017-05-18T16:37:48Z",
            "installed_image": {
             "filepath": "/secondary_firmware.txt",
             "fileinfo": {
              "length": 37,
              "hashes": {
               "sha256": "6b9f987226610bfed08b824c93bf8b2f59521fce9a2adef80c495f363c1c9c44",
               "sha512": "706c283972c5ae69864b199e1cdd9b4b8babc14f5a454d0fd4d3b35396a04ca0b40af731671b74020a738b5108a78deb032332c36d6ae9f31fae2f8a70f7e1ce"}}}}}]}}}

    if tuf.conf.METADATA_FORMAT == 'json':
      manifest = manifest_json

    else: # Use ASN.1/DER
      assert tuf.conf.METADATA_FORMAT == 'der' # Or test code is broken/old.

      manifest_fname = os.path.join(SAMPLES_DIR, 'sample_vehicle_manifest.der')
      with open(manifest_fname, 'rb') as fobj:
        manifest = fobj.read()



    # Make sure we're starting off with no registered ECU or vehicle manifests,
    # for any vehicles or ECUs, before the next tests.
    # (If you move ECU Manifest tests before Vehicle Manifest tests, of course,
    # the ECU Manifest check here will have to move elsewhere, as the dict
    # of ECU Manifests registered probably won't be empty.)
    for ecu_serial in inventory.ecu_manifests:
      self.assertFalse(inventory.ecu_manifests[ecu_serial])
    for vin in inventory.vehicle_manifests:
      self.assertFalse(inventory.vehicle_manifests[vin])



    # TODO: Register a vehicle manifest with NO ECU Manifests (unlike the one
    # above) and run these tests after it:
    # self.assertIn('democar', inventory.vehicle_manifests)
    # self.assertTrue(inventory.get_vehicle_manifests('democar'))
    # # No ECU Manifests have been registered yet, since the
    # self.assertIsNone(inventory.get_last_ecu_manifest('TCUdemocar'))
    # # This next one is a little subtle: even if there were no ECU Manifests
    # # submitted in any vehicle manifests yet, the dictionary of ECU Manifests
    # # provided should still not be totally empty if a Vehicle Manifest has been
    # # received: it will look something like this, listing an empty list of
    # # ECU Manifests for each ECU in the car:
    # # {'ecu1_in_car': [], 'ecu2_in_car': [], ...}
    # self.assertTrue(inventory.get_all_ecu_manifests_from_vehicle('democar'))



    # Try a normal vehicle manifest submission, expecting success.
    TestDirector.instance.register_vehicle_manifest(
        'democar', 'INFOdemocar', manifest)

    # Make sure that the vehicle manifest now shows up in the
    # inventorydb, that the various get functions return its data, and that
    # the ECU Manifest within now shows up in the inventorydb.
    self.assertIn('democar', inventory.vehicle_manifests)
    self.assertTrue(inventory.get_vehicle_manifests('democar'))

    # TODO: Check that the value of the Vehicle Manifest retrieved from the
    # inventory db is equivalent to the Vehicle Manifest submitted. This is
    # fairly easy for JSON, but a little trickier for ASN.1/DER, because it is
    # stored in the inventory db as JSON-compatible (not as DER, because there
    # is no longer a particularly good reason to store it as DER at that point).



    # Try reporting the wrong Primary ECU Serial, expecting a spoofing error.
    with self.assertRaises(uptane.Spoofing):
      TestDirector.instance.register_vehicle_manifest(
          'democar', 'TCUdemocar', manifest)
    with self.assertRaises(uptane.Spoofing):
      TestDirector.instance.register_vehicle_manifest(
          'democar', 'nonexistent_ecu_serial', manifest)

    # Try reporting an unknown VIN.
    with self.assertRaises(uptane.UnknownVehicle):
      TestDirector.instance.register_vehicle_manifest(
          'nonexistent_vin', 'INFOdemocar', manifest)



    # Send a partial or badly formatted manifest.
    if tuf.conf.METADATA_FORMAT == 'json':
      # Exclude the signatures portion.
      manifest_bad = copy.deepcopy(manifest['signed'])
      with self.assertRaises(tuf.FormatError):
        TestDirector.instance.register_vehicle_manifest(
            'democar', 'INFOdemocar', manifest_bad)

    else:
      assert tuf.conf.METADATA_FORMAT == 'der' # Or test code is broken/old

      # Send a corrupted manifest. Expect decoding error.
      manifest = b'\x99\x99\x99\x99\x99' + manifest[5:]
      with self.assertRaises(uptane.FailedToDecodeASN1DER):
        TestDirector.instance.register_vehicle_manifest(
            'democar', 'INFOdemocar', manifest)

      # Send an empty manifest. Expect decoding error.
      manifest = bytes()
      with self.assertRaises(uptane.FailedToDecodeASN1DER):
        TestDirector.instance.register_vehicle_manifest(
            'democar', 'INFOdemocar', manifest)


    # Prepare a manifest with a bad signature.

    if tuf.conf.METADATA_FORMAT == 'json':
      # If using JSON, just corrupt the signature value.
      manifest_bad = copy.deepcopy(manifest_json)
      manifest_bad['signatures'][0]['sig'] = \
          '1234567890abcdef9f1b74d72eb500e4ff0f443f824b83405e2b21264778d1610e0a5f2663b90eda8ab05a28b5b64fc15514020985d8a93576fe33b287e1380f'

      # Try registering the bad-signature manifest.
      with self.assertRaises(tuf.BadSignatureError):
        TestDirector.instance.register_vehicle_manifest(
            'democar', 'INFOdemocar', manifest_bad)


    else:
      assert tuf.conf.METADATA_FORMAT == 'der' # Or test code is broken/old.

      # TODO: Add a test using a bad signature. Note that there is already a
      # test below for the *wrong* signature, but it would be good to test
      # both for the wrong signature and for a corrupt signature.
      # So send a properly-encoded manifest with a signature that is produced
      # by the right key, but which does not match the data in the manifest.

      pass



    # Prepare a manifest with the *wrong* signature - a signature from the
    # wrong key that is otherwise correctly signed.
    if tuf.conf.METADATA_FORMAT == 'json':
      # If using JSON, just corrupt the key ID.
      manifest_bad = copy.deepcopy(manifest_json)
      manifest_bad['signatures'][0]['keyid'] = \
          '1234567890abcdef29bfbff1c1c75df59f154fbc45539b2eb30c8a867843b2cb'

    else:
      assert tuf.conf.METADATA_FORMAT == 'der' # Or test code is broken/old.
      # When using DER, we can convert JSON to DER and re-sign with the wrong
      # key to achieve a similar test.
      manifest_bad = asn1_codec.convert_signed_metadata_to_der(
          manifest_json, DATATYPE_VEHICLE_MANIFEST, resign=True,
          private_key=demo.import_private_key('directortimestamp'))

    # Try registering the bad-signature manifest.
    with self.assertRaises(tuf.BadSignatureError):
      TestDirector.instance.register_vehicle_manifest(
          'democar', 'INFOdemocar', manifest_bad)



    # Send Vehicle Manifest containing an ECU Manifest with an unknown
    # ECU Serial. Expect no error, and expect the Vehicle Manifest to be
    # registered, but the particular ECU Manifest to not be registered.

    # First, make sure the ECU Serial in question is not registered.
    with self.assertRaises(uptane.UnknownECU):
      inventory.check_ecu_registered('unknown_ecu')

    if tuf.conf.METADATA_FORMAT == 'json':
      manifest_bad = json.load(open(os.path.join(TEST_DATA_DIR,
          'flawed_manifests', 'vm2_contains_one_unknown_ecu_manifest.json')))
    else:
      assert tuf.conf.METADATA_FORMAT == 'der' # Or test code is broken/old.
      manifest_bad = open(os.path.join(TEST_DATA_DIR, 'flawed_manifests',
          'vm2_contains_one_unknown_ecu_manifest.der'), 'rb').read()

    TestDirector.instance.register_vehicle_manifest(
        'democar', 'INFOdemocar', manifest_bad)

    # Now check to make sure the data for an unknown ECU wasn't saved as its
    # own ECU Manifest.
    self.assertNotIn('unknown_ecu',
        inventory.get_all_ecu_manifests_from_vehicle('democar'))
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_last_ecu_manifest('unknown_ecu')
    with self.assertRaises(uptane.UnknownECU):
      inventory.get_ecu_manifests('unknown_ecu')

    # Check to make sure the vehicle manifest itself was saved, though.
    self.assertIn('unknown_ecu', inventory.get_last_vehicle_manifest(
        'democar')['signed']['ecu_version_manifests'])



    # Provide a vehicle manifest that is correctly signed by the Primary, but
    # which contains a single ECU Manifest, that ECU Manifest being signed by
    # the wrong key.
    # Ensure that the Vehicle Manifest is saved, but that the ECU Manifest it
    # contains is not saved on its own as a valid ECU Manifest.
    previous_vehicle_manifest = inventory.get_last_vehicle_manifest('democar')
    previous_ecu_manifest = inventory.get_last_ecu_manifest('TCUdemocar')
    n_vms_before = len(inventory.get_vehicle_manifests('democar'))
    n_ems_before = len(inventory.get_ecu_manifests('TCUdemocar'))

    if tuf.conf.METADATA_FORMAT == 'json':
      manifest_bad = json.load(open(os.path.join(TEST_DATA_DIR,
          'flawed_manifests', 'vm3_ecu_manifest_signed_with_wrong_key.json')))
    else:
      assert tuf.conf.METADATA_FORMAT == 'der' # Or test code is broken/old.
      manifest_bad = open(os.path.join(TEST_DATA_DIR, 'flawed_manifests',
          'vm3_ecu_manifest_signed_with_wrong_key.der'), 'rb').read()

    TestDirector.instance.register_vehicle_manifest(
        'democar', 'INFOdemocar', manifest_bad)

    # If the latest vehicle manifest is no longer the same as the latest before
    # the test, then a vehicle manifest has been correctly saved.
    self.assertNotEqual(previous_vehicle_manifest,
        inventory.get_last_vehicle_manifest('democar'))
    # But we must also be sure that the bad manifest has not been saved.
    self.assertEqual(previous_ecu_manifest,
        inventory.get_last_ecu_manifest('TCUdemocar'))
    # Redundant test in case of code changes:
    self.assertEqual(
        n_vms_before + 1, len(inventory.get_vehicle_manifests('democar')))
    self.assertEqual(
        n_ems_before, len(inventory.get_ecu_manifests('TCUdemocar')))



    # TODO: Provide a vehicle manifest that is correctly signed by the
    # Primary, but which contains one untrustworthy ECU Manifest and one
    # trustworthy ECU Manifest. Expected behavior is to accept the Vehicle
    # Manifest and any valid ECU Manifests, and reject the untrustworthy
    # ECU Manifest. Call get functions to confirm.



    # Send a Vehicle Manifest containing an ECU Manifest that has an attack
    # detected report.
    previous_vehicle_manifest = inventory.get_last_vehicle_manifest('democar')
    previous_ecu_manifest = inventory.get_last_ecu_manifest('TCUdemocar')
    n_vms_before = len(inventory.get_vehicle_manifests('democar'))
    n_ems_before = len(inventory.get_ecu_manifests('TCUdemocar'))

    if tuf.conf.METADATA_FORMAT == 'json':
      manifest = json.load(open(os.path.join(TEST_DATA_DIR,
          'flawed_manifests', 'vm4_attack_detected_in_ecu_manifest.json')))
    else:
      assert tuf.conf.METADATA_FORMAT == 'der' # Or test code is broken/old.
      manifest = open(os.path.join(TEST_DATA_DIR, 'flawed_manifests',
          'vm4_attack_detected_in_ecu_manifest.der'), 'rb').read()

    TestDirector.instance.register_vehicle_manifest(
        'democar', 'INFOdemocar', manifest)

    self.assertNotEqual(previous_vehicle_manifest,
        inventory.get_last_vehicle_manifest('democar'))
    # But we must also be sure that the bad manifest has not been saved.
    self.assertNotEqual(previous_ecu_manifest,
        inventory.get_last_ecu_manifest('TCUdemocar'))
    # Redundant test in case of code changes:
    self.assertEqual(
        n_vms_before + 1, len(inventory.get_vehicle_manifests('democar')))
    self.assertEqual(
        n_ems_before + 1, len(inventory.get_ecu_manifests('TCUdemocar')))

    # Expect the attack report string in the registered manifests.
    self.assertEqual('some attack detected',
        inventory.get_last_vehicle_manifest('democar')['signed']
        ['ecu_version_manifests']['TCUdemocar'][0]['signed']
        ['attacks_detected'])

    self.assertEqual('some attack detected', inventory.get_last_ecu_manifest(
        'TCUdemocar')['signed']['attacks_detected'])





  # Covered well by test_15. May merit duplication?
  # def test_20_validate_primary_certification_in_vehicle_manifest(self):
  #   pass





  def test_25_register_ecu_manifest(self):
    pass





  def test_35_create_director_repo_for_vehicle(self):
    pass





  def test_40_add_target_for_ecu(self):
    pass





  def test_60_register_vehicle(self):
    """Tests inventorydb.register_vehicle(), along with check_vin_registered()
    and helper function _check_registration_is_sane()."""

    vin = 'democar2'

    # Make sure the vehicle is not known before the test.
    with self.assertRaises(uptane.UnknownVehicle):
      inventory.check_vin_registered(vin)
    self.assertNotIn(vin, inventory.primary_ecus_by_vin)


    # Try various invalid arguments.
    with self.assertRaises(tuf.FormatError):
      inventory.register_vehicle(5, 'other_ecu', overwrite=False)

    with self.assertRaises(tuf.FormatError):
      inventory.register_vehicle(vin, 5, overwrite=False)

    with self.assertRaises(tuf.FormatError):
      inventory.register_vehicle(vin, 'other_ecu', overwrite='not boolean')


    # Register correctly, expecting success.
    inventory.register_vehicle(vin, 'tv_primary')


    # Make sure the registration worked, also directly testing the helper
    # function that check_vin_registered uses.
    inventory.check_vin_registered(vin)
    self.assertEqual('tv_primary', inventory.primary_ecus_by_vin[vin])
    inventory._check_registration_is_sane(vin)

    # Expect re-registering WITHOUT overwrite on to fail.
    with self.assertRaises(uptane.Spoofing):
      inventory.register_vehicle(vin, 'other_ecu', overwrite=False)
    self.assertEqual('tv_primary', inventory.primary_ecus_by_vin[vin])

    # Expect re-registering with overwrite to succeed.
    inventory.register_vehicle(vin, 'tv_primary2', overwrite=True)
    self.assertEqual('tv_primary2', inventory.primary_ecus_by_vin[vin])


    # See that _check_registration_is_sane tests its VIN argument, by providing
    # an incorrectly formatted VIN.
    with self.assertRaises(tuf.FormatError):
      inventory._check_registration_is_sane(42)





# Run unit test.
if __name__ == '__main__':
  unittest.main()
