"""
<Program Name>
  test_primary.py

<Purpose>
  Unit testing for uptane/clients/primary.py

<Copyright>
  See LICENSE for licensing information.
"""
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

import unittest
import os.path
import time
import copy
import shutil
import hashlib
import iso8601

from six.moves.urllib.error import URLError

import tuf
import tuf.formats
import tuf.conf
import tuf.client.updater # to test one of the fields in the Primary object

import uptane.formats
import uptane.clients.primary as primary
import uptane.common # verify sigs, create client dir structure, convert key
import uptane.encoding.asn1_codec as asn1_codec

from uptane.encoding.asn1_codec import DATATYPE_TIME_ATTESTATION
from uptane.encoding.asn1_codec import DATATYPE_ECU_MANIFEST
from uptane.encoding.asn1_codec import DATATYPE_VEHICLE_MANIFEST

# For temporary convenience:
import demo # for generate_key, import_public_key, import_private_key
import json


SAMPLE_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'samples')
TEST_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'tests', 'test_data')
TEST_DIRECTOR_METADATA_DIR = os.path.join(TEST_DATA_DIR, 'director_metadata')
TEST_IMAGE_REPO_METADATA_DIR = os.path.join(
    TEST_DATA_DIR, 'image_repo_metadata')
TEST_DIRECTOR_ROOT_FNAME = os.path.join(
    TEST_DIRECTOR_METADATA_DIR, 'root.' + tuf.conf.METADATA_FORMAT)
TEST_IMAGE_REPO_ROOT_FNAME = os.path.join(
    TEST_IMAGE_REPO_METADATA_DIR, 'root.' + tuf.conf.METADATA_FORMAT)
TEST_PINNING_FNAME = os.path.join(TEST_DATA_DIR, 'pinned.json')
TEMP_CLIENT_DIR = os.path.join(TEST_DATA_DIR, 'temp_test_primary')

# Sample metadata and targets that will be copied to TEMP_CLIENT_DIR to use
# as a local repository for testing.
SAMPLE_METADATA = os.path.join(
    uptane.WORKING_DIR, 'samples', 'metadata_samples_long_expiry',
    'update_to_one_ecu', 'full_metadata_archive')
SAMPLE_TARGETS = os.path.join(uptane.WORKING_DIR, 'demo', 'images')

# Changing some of these values would require producing new signed sample data
# from the Timeserver or a Secondary.
NONCE = 5
VIN = 'democar'
PRIMARY_ECU_SERIAL = '00000'



def destroy_temp_dir():
  # Clean up anything that may currently exist in the temp test directory.
  if os.path.exists(TEMP_CLIENT_DIR):
    shutil.rmtree(TEMP_CLIENT_DIR)





class TestPrimary(unittest.TestCase):
  """
  "unittest"-style test class for the Primary module in the reference
  implementation

  Please note that these tests are NOT entirely independent of each other.
  Several of them build on the results of previous tests. This is an unusual
  pattern but saves code and works at least for now.
  """
  # Class variables
  ecu_key = None
  key_timeserver_pub = None
  key_timeserver_pri = None
  initial_time = None
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

    # Load the private key for this Primary ECU.
    cls.ecu_key = uptane.common.canonical_key_from_pub_and_pri(
        demo.import_public_key('primary'),
        demo.import_private_key('primary'))

    # Load the public timeserver key.
    cls.key_timeserver_pub = demo.import_public_key('timeserver')
    cls.key_timeserver_pri = demo.import_private_key('timeserver')

    # Generate a trusted initial time for the Primary.
    cls.initial_time = tuf.formats.unix_timestamp_to_datetime(
        int(time.time())).isoformat() + 'Z'
    tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(cls.initial_time)




  @classmethod
  def tearDownClass(cls):
    """
    This is run once for the class, after all tests. Since there is only one
    class, this runs once.
    """
    destroy_temp_dir()




  def test_01_init(self):
    """
    Note that this doesn't test the root files provided, as those aren't used
    at all in the initialization; for that, we'll have to test the update cycle.
    """

    # Set up a client directory first.
    uptane.common.create_directory_structure_for_client(
        TEMP_CLIENT_DIR,
        TEST_PINNING_FNAME,
        {'imagerepo': TEST_IMAGE_REPO_ROOT_FNAME,
        'director': TEST_DIRECTOR_ROOT_FNAME})

    # Create repository directories that will be accessed locally (using
    # file:// URLs) from which to "download" test metadata and targets.
    for repository in ["director", "imagerepo"]:
    	shutil.copytree(
    		os.path.join(SAMPLE_METADATA, repository),
    		os.path.join(TEMP_CLIENT_DIR, repository))

    # Note that there may be extra targets available here.
    shutil.copytree(
    	SAMPLE_TARGETS, os.path.join(TEMP_CLIENT_DIR, 'imagerepo', 'targets'))



    # TODO: Test with invalid pinning file
    # TODO: Test with pinning file lacking a Director repo.

    # Now try creating a Primary with a series of bad arguments, expecting
    # errors.

    # TODO: Add test for my_secondaries argument.

    # Invalid VIN:
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=5,  # INVALID
          ecu_serial=PRIMARY_ECU_SERIAL,
          primary_key=TestPrimary.ecu_key,
          time=TestPrimary.initial_time,
          timeserver_public_key=TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid ECU Serial
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=VIN,
          ecu_serial=500, # INVALID
          primary_key=TestPrimary.ecu_key,
          time=TestPrimary.initial_time,
          timeserver_public_key=TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid ECU Key
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=VIN,
          ecu_serial=PRIMARY_ECU_SERIAL,
          primary_key={''}, # INVALID
          time=TestPrimary.initial_time,
          timeserver_public_key=TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid time:
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=VIN,
          ecu_serial=PRIMARY_ECU_SERIAL,
          primary_key=TestPrimary.ecu_key,
          time='invalid because this is not a time', # INVALID
          timeserver_public_key=TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid timeserver key
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=VIN,
          ecu_serial=PRIMARY_ECU_SERIAL,
          primary_key=TestPrimary.ecu_key, time=TestPrimary.initial_time,
          timeserver_public_key=TestPrimary.initial_time, # INVALID
          my_secondaries=[])

    # Invalid format for Director Repository name
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=5, #INVALID
          vin=VIN,
          ecu_serial=PRIMARY_ECU_SERIAL,
          primary_key=TestPrimary.ecu_key, time=TestPrimary.initial_time,
          timeserver_public_key = TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid name for Director repository
    with self.assertRaises(uptane.Error):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name= "invalid", #INVALID
          vin=VIN,
          ecu_serial=PRIMARY_ECU_SERIAL,
          primary_key=TestPrimary.ecu_key, time=TestPrimary.initial_time,
          timeserver_public_key = TestPrimary.key_timeserver_pub,
          my_secondaries=[])



    # Try creating a Primary, expecting it to work.
    # Initializes a Primary ECU, making a client directory and copying the root
    # file from the repositories.
    # Save the result for future tests, to save time and code.
    TestPrimary.instance = primary.Primary(
        full_client_dir=TEMP_CLIENT_DIR,
        director_repo_name=demo.DIRECTOR_REPO_NAME,
        vin=VIN,
        ecu_serial=PRIMARY_ECU_SERIAL,
        primary_key=TestPrimary.ecu_key,
        time=TestPrimary.initial_time,
        timeserver_public_key=TestPrimary.key_timeserver_pub)


    # Check the fields initialized in the instance to make sure they're correct.

    self.assertEqual([], TestPrimary.instance.nonces_to_send)
    self.assertEqual([], TestPrimary.instance.nonces_sent)
    self.assertEqual(VIN, TestPrimary.instance.vin)
    self.assertEqual(PRIMARY_ECU_SERIAL, TestPrimary.instance.ecu_serial)
    self.assertEqual(TestPrimary.ecu_key, TestPrimary.instance.primary_key)
    self.assertEqual(dict(), TestPrimary.instance.ecu_manifests)
    self.assertEqual(
        TestPrimary.instance.full_client_dir, TEMP_CLIENT_DIR)
    self.assertIsInstance(
        TestPrimary.instance.updater, tuf.client.updater.Updater)
    tuf.formats.ANYKEY_SCHEMA.check_match(
        TestPrimary.instance.timeserver_public_key)
    self.assertEqual([], TestPrimary.instance.my_secondaries)




    # Now, fix the updater's pinned metadata to point it to the appropriate
    # local directory, since the pinned metadata we fed in was actually for the
    # live demo, connecting to localhost:30401. We instead want to use a
    # local directory via file://.

    # TODO: Determine if this code should be adjusted to use os.path.join(),
    # or if that's not appropriate for file:// links.

    image_repo_mirror = ['file://' + TEMP_CLIENT_DIR + '/imagerepo']
    director_mirror = ['file://' + TEMP_CLIENT_DIR + '/director']

    repository_urls = TestPrimary.instance.updater.pinned_metadata['repositories']
    repository_urls['imagerepo']['mirrors'] = image_repo_mirror
    repository_urls['director']['mirrors'] = director_mirror

    # Also fix the copied pinned metadata in the individual repo updaters
    # in the updater.
    TestPrimary.instance.updater.repositories['imagerepo'].mirrors = image_repo_mirror
    TestPrimary.instance.updater.repositories['director'].mirrors = director_mirror





  def test_05_register_new_secondary(self):

    self.assertEqual([], TestPrimary.instance.my_secondaries)

    TestPrimary.instance.register_new_secondary('1352')

    self.assertIn('1352', TestPrimary.instance.my_secondaries)





  def test_10_register_ecu_manifest(self):

    # Throughout this function, I'll use a different nonces in each call to
    # register_ecu_manifest, and check that the ones in calls expected to
    # succeed have been noted and that the ones in calls expected to fail have
    # not been noted.

    # Starting with an empty ecu manifest dictionary.
    self.assertEqual(dict(), TestPrimary.instance.ecu_manifests)

    # Make sure we're starting with no nonces sent or to send.
    self.assertEqual([], TestPrimary.instance.nonces_to_send)
    self.assertEqual([], TestPrimary.instance.nonces_sent)


    # Load the manifests we'll use in these tests.
    # Note that the .json and .der manifest samples aren't identical; they're
    # signed over different data, so to get the JSON version of the DER
    # manifests, we'll convert them.
    # We'll always need the JSON encodings for testing, and we'll load the
    # ASN.1/DER manifests only if we're in DER mode.
    # 1: Correctly signed ECU manifest from ECU TCUdemocar (good sample)
    # 2: Correctly signed ECU manifest from ECU unknown_ecu
    # 3: ECU Manifest from ECU TCUdemocar signed by the wrong key
    #    (demo's Image Repo timestamp key in particular, instead of demo's
    #     Secondary key)
    # 4: Correctly signed ECU manifest from TCUdemocar w/ attack report

    if tuf.conf.METADATA_FORMAT == 'json':
      manifest1 = manifest1_json = json.load(open(os.path.join(SAMPLE_DATA_DIR,
          'sample_ecu_manifest_TCUdemocar.json')))

      manifest2 = manifest2_json = json.load(open(os.path.join(TEST_DATA_DIR,
          'flawed_manifests', 'em2_unknown_ecu_manifest.json')))

      manifest3 = manifest3_json = json.load(open(os.path.join(TEST_DATA_DIR,
          'flawed_manifests', 'em3_ecu_manifest_signed_with_wrong_key.json')))

      manifest4 = manifest4_json = json.load(open(os.path.join(TEST_DATA_DIR,
          'flawed_manifests', 'em4_attack_detected_in_ecu_manifest.json')))

    else:
      assert tuf.conf.METADATA_FORMAT == 'der', 'Test code is flawed.'

      manifest1 = open(os.path.join(SAMPLE_DATA_DIR,
          'sample_ecu_manifest_TCUdemocar.der'), 'rb').read()

      manifest1_json = asn1_codec.convert_signed_der_to_dersigned_json(
          manifest1, DATATYPE_ECU_MANIFEST)

      manifest2 = open(os.path.join(TEST_DATA_DIR, 'flawed_manifests',
          'em2_unknown_ecu_manifest.der'), 'rb').read()

      manifest2_json = asn1_codec.convert_signed_der_to_dersigned_json(
          manifest2, DATATYPE_ECU_MANIFEST)

      manifest3 = open(os.path.join(TEST_DATA_DIR, 'flawed_manifests',
          'em3_ecu_manifest_signed_with_wrong_key.der'), 'rb').read()

      manifest3_json = asn1_codec.convert_signed_der_to_dersigned_json(
          manifest3, DATATYPE_ECU_MANIFEST)

      manifest4 = open(os.path.join(TEST_DATA_DIR, 'flawed_manifests',
          'em4_attack_detected_in_ecu_manifest.der'), 'rb').read()

      manifest4_json = asn1_codec.convert_signed_der_to_dersigned_json(
          manifest4, DATATYPE_ECU_MANIFEST)


    # Register two Secondaries with the Primary.
    TestPrimary.instance.register_new_secondary('TCUdemocar')
    TestPrimary.instance.register_new_secondary('ecu11111')


    # Start with a sequence of tests with bad arguments but an otherwise
    # correct ECU Manifest, manifest1.

    # Try using a VIN that is not the Primary's VIN (ECU Manifest apparently
    # from another car!)
    with self.assertRaises(uptane.UnknownVehicle):
      TestPrimary.instance.register_ecu_manifest(
          vin='13105941', # unexpected VIN
          ecu_serial='TCUdemocar', nonce=1,
          signed_ecu_manifest=manifest1)

    # Try using the wrong ECU Serial - one that is registered, but which does
    # not match the ECU Serial listed in the ECU Manifest itself.
    with self.assertRaises(uptane.Spoofing):
      TestPrimary.instance.register_ecu_manifest(
          vin=VIN,
          ecu_serial='ecu11111', # not the same ECU Serial in the manifest
          nonce=2, signed_ecu_manifest=manifest1)

    # Try using an ECU Serial that the Primary is not aware of.
    with self.assertRaises(uptane.UnknownECU):
      TestPrimary.instance.register_ecu_manifest(
          vin=VIN, # unexpected VIN
          ecu_serial='an unknown secondary ecu serial', # unexpected ECU Serial
          nonce=3,
          signed_ecu_manifest=manifest1)


    # Register the ECU Manifest correctly this time.
    TestPrimary.instance.register_ecu_manifest(
        vin=VIN, ecu_serial='TCUdemocar', nonce=10,
        signed_ecu_manifest=manifest1)

    # Make sure the provided manifest is now in the Primary's ecu manifests
    # dictionary. Note that the Primary holds manifests as JSON-compatible
    # Python dictionaries regardless of the format it receives them in.
    self.assertIn('TCUdemocar', TestPrimary.instance.ecu_manifests)
    self.assertIn(
        manifest1_json, TestPrimary.instance.ecu_manifests['TCUdemocar'])

    # Make sure the nonce provided was noted in the right place.
    self.assertIn(10, TestPrimary.instance.nonces_to_send)
    self.assertEqual([], TestPrimary.instance.nonces_sent)


    # Though this is not required functionality, test register_ecu_manifest
    # with JSON manifests as well, even if we're running in DER mode.
    # And make sure force_pydict=True doesn't break if we're already in JSON
    # mode, either.
    TestPrimary.instance.register_ecu_manifest(
        VIN, 'TCUdemocar', nonce=11, signed_ecu_manifest=manifest1_json,
        force_pydict=True)



    # The next tests use ECU Manifests that contain problematic values.
    # (We're now testing things beyond just the arguments provided.
    # If we're running in DER mode, we'll try both DER and JSON manifests.
    # If we're running in JSON mode, we'll only try JSON manifests
    #    (though in JSON mode, we'll run twice, once with force_pydict on
    #    to make sure that run doesn't break despite the redundant argument).

    # The list again is:
    # 2: Correctly signed ECU manifest from ECU unknown_ecu
    # 3: ECU Manifest from ECU TCUdemocar signed by the wrong key
    # 4: Correctly signed ECU manifest from TCUdemocar w/ attack report


    # Case 2: We won't save the ECU Manifest from an unknown ECU Serial.
    self.assertNotIn('unknown_ecu', TestPrimary.instance.ecu_manifests)
    self.assertNotIn(
        manifest2_json, TestPrimary.instance.ecu_manifests['TCUdemocar'])

    with self.assertRaises(uptane.UnknownECU):
      TestPrimary.instance.register_ecu_manifest(
          'democar', 'unknown_ecu', nonce=4, signed_ecu_manifest=manifest2)

    with self.assertRaises(uptane.UnknownECU):
      TestPrimary.instance.register_ecu_manifest(
          'democar', 'unknown_ecu', nonce=5,
          signed_ecu_manifest=manifest2_json, force_pydict=True)

    self.assertNotIn('unknown_ecu', TestPrimary.instance.ecu_manifests)
    self.assertNotIn( # Make sure it's not in the wrong list of ECU Manifests
        manifest2_json, TestPrimary.instance.ecu_manifests['TCUdemocar'])


    # Case 3: ECU Manifest signed with the wrong key: we save it anyway and
    #         send it on to the Director like any other; Primaries don't check
    #         the signatures on ECU Manifests: they can't be expected to know
    #         the right public or symmetric keys.
    self.assertNotIn(
        manifest3_json, TestPrimary.instance.ecu_manifests['TCUdemocar'])

    TestPrimary.instance.register_ecu_manifest(
        'democar', 'TCUdemocar', nonce=12, signed_ecu_manifest=manifest3)

    TestPrimary.instance.register_ecu_manifest(
        'democar', 'TCUdemocar', nonce=13, signed_ecu_manifest=manifest3_json,
        force_pydict=True)

    self.assertIn(
        manifest3_json, TestPrimary.instance.ecu_manifests['TCUdemocar'])


    # Case 4: ECU Manifest containing an attack report. Make sure it doesn't
    #         fail to be registered.
    self.assertNotIn(
        manifest4_json, TestPrimary.instance.ecu_manifests['TCUdemocar'])

    TestPrimary.instance.register_ecu_manifest(
        'democar', 'TCUdemocar', nonce=14, signed_ecu_manifest=manifest4)

    TestPrimary.instance.register_ecu_manifest(
        'democar', 'TCUdemocar', nonce=15, signed_ecu_manifest=manifest4_json,
        force_pydict=True)

    self.assertIn(
        manifest4_json, TestPrimary.instance.ecu_manifests['TCUdemocar'])



    # Confirm that we've succeeded in registering the right nonces.
    for this_nonce in [1, 2, 3, 4, 5]:
      self.assertNotIn(this_nonce, TestPrimary.instance.nonces_to_send)

    for this_nonce in [10, 11, 12, 13, 14, 15]:
      self.assertIn(this_nonce, TestPrimary.instance.nonces_to_send)







  def test_15_get_nonces_to_send_and_rotate(self):

    # The Primary's list of nonces to send in the next request to the
    # timeserver for a time attestation:
    nonces_to_have_sent = TestPrimary.instance.nonces_to_send


    # Double-check that one of the expected nonces from the previous test
    # function is in the list of the Primary's nonces to send.
    self.assertIn(10, nonces_to_have_sent)


    # Cycle nonces: Request the list of nonces to send to the timeserver,
    # triggering the rotation of nonces. Make sure the nonce list provided
    # is as expected from the previous test, and then that the rotation has
    # actually occurred (nonces_to_send emptied, contents moved to nonces_sent).
    self.assertEqual(
        sorted(nonces_to_have_sent),
        sorted(TestPrimary.instance.get_nonces_to_send_and_rotate()))

    self.assertEqual(nonces_to_have_sent, TestPrimary.instance.nonces_sent)
    self.assertEqual([], TestPrimary.instance.nonces_to_send)





  def test_20_update_time(self):

    # First, confirm that we've never verified a timeserver attestation, and/or
    # that that results in get_last_timeserver_attestation returning None.
    self.assertIsNone(TestPrimary.instance.get_last_timeserver_attestation())


    # Try a good time attestation first, signed by an expected timeserver key,
    # with an expected nonce (previously "received" from a Secondary)
    original_time_attestation = time_attestation = {
        'signed': {'nonces': [NONCE], 'time': '2016-11-02T21:06:05Z'},
        'signatures': [{
          'method': 'ed25519',
          'sig': 'aabffcebaa57f1d6397bdc5647764261fd23516d2996446c3c40b3f30efb2a4a8d80cd2c21a453e78bf99dafb9d0f5e56c4e072db365499fa5f2f304afec100e',
          'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'}]}

    if tuf.conf.METADATA_FORMAT == 'der':
      # Convert this time attestation to the expected ASN.1/DER format.
      time_attestation = asn1_codec.convert_signed_metadata_to_der(
          original_time_attestation, DATATYPE_TIME_ATTESTATION,
          private_key=TestPrimary.key_timeserver_pri, resign=True)

    # Check expected base conditions before updating time:
    # The only timeserver times registered should be one added during
    # initialization.  Because the clock override is a module variable in TUF,
    # its value (whether None or already set) depends on whether or not other
    # tests resulting in time attestation verification have occurred (e.g.
    # those for the Primary).
    self.assertEqual(1, len(TestPrimary.instance.all_valid_timeserver_times))
    initial_clock_override = tuf.conf.CLOCK_OVERRIDE

    # In the previous functions, we added a variety of nonces in the nonce
    # rotation. Verification of a time attestation confirms that the time
    # attestation contains the nonces we've most recently sent to the
    # timeserver. The sample attestation we have here does not have the nonces
    # we've indicated to the Primary that we've sent, so this verification
    # should fail:
    with self.assertRaises(uptane.BadTimeAttestation):
      TestPrimary.instance.update_time(time_attestation)

    # Check results.  The bad attestation should change none of these.
    self.assertEqual(1, len(TestPrimary.instance.all_valid_timeserver_times))
    self.assertEqual(initial_clock_override, tuf.conf.CLOCK_OVERRIDE)

    # Now we adjust the Primary's notion of what nonces we sent to the
    # timeserver most recently, and then try the verification again, expecting
    # it to succeed.
    TestPrimary.instance.get_nonces_to_send_and_rotate()
    TestPrimary.instance.nonces_to_send = [NONCE]
    TestPrimary.instance.get_nonces_to_send_and_rotate()
    TestPrimary.instance.update_time(time_attestation)

    # Check results.  Among other things, since the verification succeeded,
    # get_last_timeserver_attestation should return the attestation we just
    # provided.
    self.assertEqual(
        time_attestation,
        TestPrimary.instance.get_last_timeserver_attestation())
    self.assertEqual(2, len(TestPrimary.instance.all_valid_timeserver_times))
    self.assertEqual(
        int(tuf.formats.datetime_to_unix_timestamp(iso8601.parse_date(
        '2016-11-02T21:06:05Z'))), tuf.conf.CLOCK_OVERRIDE)


    # Prepare to try again with a bad signature.
    # This test we will conduct differently depending on TUF's current format:
    if tuf.conf.METADATA_FORMAT == 'der':
      # Fail to re-sign the DER, so that the signature is over JSON instead,
      # which results in a bad signature.
      time_attestation__badsig = asn1_codec.convert_signed_metadata_to_der(
          original_time_attestation, DATATYPE_TIME_ATTESTATION, resign=False)

    else: # 'json' format
      # Rewrite the first 9 digits of the signature ('sig') to something
      # invalid.
      time_attestation__badsig = {
          'signed': {'nonces': [NONCE], 'time': '2016-11-02T21:06:05Z'},
          'signatures': [{
            'method': 'ed25519',
            'sig': '987654321a57f1d6397bdc5647764261fd23516d2996446c3c40b3f30efb2a4a8d80cd2c21a453e78bf99dafb9d0f5e56c4e072db365499fa5f2f304afec100e',
            'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'}]}

    # Now actually perform the bad signature test.
    with self.assertRaises(tuf.BadSignatureError):
      TestPrimary.instance.update_time(time_attestation__badsig)


    assert 500 not in original_time_attestation['signed']['nonces'], \
        'Programming error: bad and good test nonces are equal.'

    time_attestation__wrongnonce = {
        'signed': {'nonces': [500], 'time': '2016-11-02T21:15:00Z'},
        'signatures': [{
          'method': 'ed25519',
          'sig': '4d01df35ca829fd7ead1408c250950c444db8ac51fa929a7f0288578fbf81016f0e81ed35789689481aee6b7af28ab311306397ef38572732854fb6cf2072604',
          'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'}]}

    if tuf.conf.METADATA_FORMAT == 'der':
      # Convert this time attestation to the expected ASN.1/DER format.
      time_attestation__wrongnonce = asn1_codec.convert_signed_metadata_to_der(
          time_attestation__wrongnonce, DATATYPE_TIME_ATTESTATION,
          private_key=TestPrimary.key_timeserver_pri, resign=True)

    with self.assertRaises(uptane.BadTimeAttestation):
      TestPrimary.instance.update_time(
          time_attestation__wrongnonce)


    # TODO: Consider other tests here.





  def test_25_generate_signed_vehicle_manifest(self):

    vehicle_manifest = TestPrimary.instance.generate_signed_vehicle_manifest()

    # If the vehicle manifest is in DER format, check its format and then
    # convert back to JSON so that we can inspect it further.
    if tuf.conf.METADATA_FORMAT == 'der':
      uptane.formats.DER_DATA_SCHEMA.check_match(vehicle_manifest)
      vehicle_manifest = asn1_codec.convert_signed_der_to_dersigned_json(
          vehicle_manifest, DATATYPE_VEHICLE_MANIFEST)

    # Now it's not in DER format, whether or not it started that way.
    # Check its format and inspect it.
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        vehicle_manifest)

    # Test contents of vehicle manifest.
    # Make sure there is exactly one signature.
    self.assertEqual(1, len(vehicle_manifest['signatures']))
    # Make sure that the Secondary's ECU Manifest (from the register ECU
    # ECU Manifest test above) is listed in the Vehicle Manifest.
    self.assertIn(
        'TCUdemocar', vehicle_manifest['signed']['ecu_version_manifests'])

    # TODO: More testing of the contents of the vehicle manifest.


    # Check the signature on the vehicle manifest.
    self.assertTrue(uptane.common.verify_signature_over_metadata(
        TestPrimary.ecu_key,
        vehicle_manifest['signatures'][0], # TODO: Deal with 1-sig assumption?
        vehicle_manifest['signed'],
        DATATYPE_VEHICLE_MANIFEST))




  def test_30_refresh_toplevel_metadata(self):

    # Check that in the fresh temp directory for this test Primary client,
    # there aren't any metadata files except root.json yet.
    self.assertEqual(
        ['root.der', 'root.json'],
        sorted(os.listdir(TEST_DIRECTOR_METADATA_DIR)))
    self.assertEqual(
        ['root.der', 'root.json'],
        sorted(os.listdir(TEST_IMAGE_REPO_METADATA_DIR)))

    try:
      TestPrimary.instance.refresh_toplevel_metadata()
    except (URLError, tuf.NoWorkingMirrorError) as e:
      pass
    else:
      # Check the resulting top-level metadata files in the client directory.
      # Expect root, snapshot, targets, and timestamp for both director and
      # image repo.
      for repo in ['director', 'imagerepo']:
        self.assertEqual(
            ['root.' + tuf.conf.METADATA_FORMAT,
            'snapshot.' + tuf.conf.METADATA_FORMAT,
            'targets.' + tuf.conf.METADATA_FORMAT,
            'timestamp.' + tuf.conf.METADATA_FORMAT],
            sorted(os.listdir(os.path.join(TEMP_CLIENT_DIR, 'metadata', repo,
            'current'))))







  def test_35_get_target_list_from_director(self):
    # TODO: Write this in a way that draws on saved sample Director metadata.
    #       Don't expect an actual server to be running.
    #       This will probably entail modification to the pinned.json file to
    #       point it to a local directory instead of a remote server.
    #directed_targets = TestPrimary.instance.test_35_get_target_list_from_director
    pass





  def test_40_get_validated_target_info(self):
    # TODO: Write this in a way that draws on saved sample metadata from the
    #       Director and Image Repo. Don't expect an actual server to be
    #       running. This will probably entail modification to the pinned.json
    #       file to point it to a local directory instead of a remote server.
    pass





  def test_55_update_exists_for_ecu(self):


    # The various ECU Serials of Secondary ECUs we'll test:

    # 1: Registered with the Primary but NOT listed in Director metadata
    #    (i.e. will not have any updates assigned)
    known_secondary_with_no_updates = "secondary_without_updates"

    # 2: NOT registered w/ the Primary and NOT listed in Director metadata
    unknown_secondary = "unknown_ecu_serial"

    # 3: Registered with the Primary and listed in Director metadata
    normal_secondary = "TCUdemocar"

    # 4: Invalid name for a Secondary (wrong format)
    invalid_name_secondary = 5


    # Register the Secondaries with the Primary and make sure registration
    # succeeded.
    TestPrimary.instance.register_new_secondary(known_secondary_with_no_updates)
    TestPrimary.instance.register_new_secondary(normal_secondary)

    self.assertIn(
        known_secondary_with_no_updates, TestPrimary.instance.my_secondaries)
    self.assertIn(normal_secondary, TestPrimary.instance.my_secondaries)

    # Try registering a Secondary that has already been registered with the
    # Primary. Expect success??? # TODO: Clarify.
    TestPrimary.instance.register_new_secondary(known_secondary_with_no_updates)

    # Try registering an invalid name.
    with self.assertRaises(tuf.FormatError):
      TestPrimary.instance.register_new_secondary(invalid_name_secondary)

    # Confirm that unknown_secondary has not been registered.
    with self.assertRaises(uptane.UnknownECU):
      TestPrimary.instance._check_ecu_serial(unknown_secondary)

    # Run a primary update cycle so that the Primary fetches and validates
    # metadata and targets from the "repositories" (in this test, the
    # repositories sit in a local folder accessed by file://).
    # This also processes the data acquired to populate fields accessed by
    # Secondaries below.
    TestPrimary.instance.primary_update_cycle()

    # Try to find out if updates exist for an unknown ECU.
    with self.assertRaises(uptane.UnknownECU):
      TestPrimary.instance.update_exists_for_ecu(unknown_secondary)

    # Find out if updates exist for a known ECU that has no updates assigned to
    # it by the Director (expect empty list).
    self.assertFalse(TestPrimary.instance.update_exists_for_ecu(
        known_secondary_with_no_updates))

    # Confirm that updates exist for a known ECU to which we've assigned
    # updates (list is not empty).
    self.assertTrue(TestPrimary.instance.update_exists_for_ecu(
        normal_secondary))


    # Run the update cycle again to test file/archive replacement when an
    # update cycle has already occurred.
    TestPrimary.instance.primary_update_cycle()





  def test_60_get_image_fname_for_ecu(self):

    # TODO: More thorough tests.

    with self.assertRaises(uptane.UnknownECU):
      TestPrimary.instance.get_image_fname_for_ecu('unknown')

    # Expect an image.
    image_fname = TestPrimary.instance.get_image_fname_for_ecu('TCUdemocar')

    self.assertTrue(image_fname)

    tuf.formats.RELPATH_SCHEMA.check_match(image_fname)

    # Fetch the image filename for an ECU that has had no update assigned it,
    # expecting None.
    self.assertIsNone(TestPrimary.instance.get_image_fname_for_ecu(
        'secondary_without_updates'))






  def test_61_get_full_metadata_archive_fname(self):

    # TODO: More thorough tests.

    archive_fname = TestPrimary.instance.get_full_metadata_archive_fname()

    self.assertTrue(archive_fname)

    tuf.formats.RELPATH_SCHEMA.check_match(archive_fname)





  def test_62_get_partial_metadata_fname(self):

    # TODO: More thorough tests.

    fname = TestPrimary.instance.get_partial_metadata_fname()

    self.assertTrue(fname)

    tuf.formats.RELPATH_SCHEMA.check_match(fname)





  def test_65_get_metadata_for_ecu(self):
    pass






  def test_70_get_last_timeserver_attestation(self):

    # get_last_timeserver_attestation is tested in more detail in a previous
    # test, test_20_update_time.

    attestation = TestPrimary.instance.get_last_timeserver_attestation()

    # We expect to have verified an attestation in previous tests.
    self.assertIsNotNone(attestation)

    if tuf.conf.METADATA_FORMAT == 'der':
      uptane.formats.DER_DATA_SCHEMA.check_match(attestation)
    else:
      assert tuf.conf.METADATA_FORMAT == 'json', 'Coding error in test.'
      uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
          attestation)





# Run unit test.
if __name__ == '__main__':
  unittest.main()
