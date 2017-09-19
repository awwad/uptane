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
from io import open # To add support for Python 2
import unittest
import os.path
import time
import copy
import shutil
import hashlib

from six.moves.urllib.error import URLError

import tuf
import tuf.formats
import tuf.conf
import tuf.client.updater # to test one of the fields in the Primary object

import uptane.formats
import uptane.clients.primary as primary
import uptane.common # verify sigs, create client dir structure, convert key
import uptane.encoding.asn1_codec as asn1_codec

# For temporary convenience:
import demo # for generate_key, import_public_key, import_private_key


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

# #Source to copy all the local metadata to the TEMP_CLIENT_DIR
# SOURCE_FOR_LOCAL_METADATA = os.path.join(uptane.WORKING_DIR, 'samples', 'metadata_samples_long_expiry', 'updates_w_custom_field_to_one_ecu_bad_director', 'full_metadata_archive')
# #Source to copy all the target files to TEMP_CLIENT_DIR
# SOURCE_FOR_LOCAL_TARGETS = os.path.join(uptane.WORKING_DIR,'demo', "images")


# Changing some of these values would require producing new signed sample data
# from the Timeserver or a Secondary.
nonce = 5
vin = '000'
primary_ecu_serial = '00000'
primary_hardware_id = "Infotainment101"
primary_release_counter = 1



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


    mirror = pinnings['repositories'][repo_name]['mirrors'][0]
    mirror = mirror.replace('<full_client_dir>', uptane.WORKING_DIR)
    mirror = mirror.replace('<temp_test_ecu>', TEMP_PRIMARY_FOLDER)
    pinnings['repositories'][repo_name]['mirrors'][0] = mirror




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
          ecu_serial=primary_ecu_serial,
          primary_key=TestPrimary.ecu_key,
          time=TestPrimary.initial_time,
          timeserver_public_key=TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid ECU Serial
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
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
          vin=vin,
          ecu_serial=primary_ecu_serial,
          primary_key={''}, # INVALID
          time=TestPrimary.initial_time,
          timeserver_public_key=TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid time:
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=primary_ecu_serial,
          primary_key=TestPrimary.ecu_key,
          time='potato', # INVALID
          timeserver_public_key=TestPrimary.key_timeserver_pub,
          my_secondaries=[])

    # Invalid timeserver key
    with self.assertRaises(tuf.FormatError):
      primary.Primary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=primary_ecu_serial,
          primary_key=TestPrimary.ecu_key, time=TestPrimary.initial_time,
          timeserver_public_key=TestPrimary.initial_time, # INVALID
          my_secondaries=[])


    # Try creating a Primary, expecting it to work.
    # Initializes a Primary ECU, making a client directory and copying the root
    # file from the repositories.
    # Save the result for future tests, to save time and code.
    TestPrimary.instance = primary.Primary(
        full_client_dir=TEMP_CLIENT_DIR,
        director_repo_name=demo.DIRECTOR_REPO_NAME,
        vin=vin,
        ecu_serial=primary_ecu_serial,
        primary_key=TestPrimary.ecu_key,
        time=TestPrimary.initial_time,
        timeserver_public_key=TestPrimary.key_timeserver_pub)


    # Check the fields initialized in the instance to make sure they're correct.

    self.assertEqual([], TestPrimary.instance.nonces_to_send)
    self.assertEqual([], TestPrimary.instance.nonces_sent)
    self.assertEqual(vin, TestPrimary.instance.vin)
    self.assertEqual(primary_ecu_serial, TestPrimary.instance.ecu_serial)
    self.assertEqual(TestPrimary.ecu_key, TestPrimary.instance.primary_key)
    self.assertEqual(dict(), TestPrimary.instance.ecu_manifests)
    self.assertEqual(
        TestPrimary.instance.full_client_dir, TEMP_CLIENT_DIR)
    self.assertIsInstance(
        TestPrimary.instance.updater, tuf.client.updater.Updater)
    tuf.formats.ANYKEY_SCHEMA.check_match(
        TestPrimary.instance.timeserver_public_key)
    self.assertEqual([], TestPrimary.instance.my_secondaries)





  def test_05_register_new_secondary(self):

    self.assertEqual([], TestPrimary.instance.my_secondaries)

    TestPrimary.instance.register_new_secondary('1352')

    self.assertIn('1352', TestPrimary.instance.my_secondaries)





  def test_10_register_ecu_manifest(self):

    TestPrimary.instance.register_new_secondary('ecu11111')

    # TODO: Test providing bad data.

    # TODO: Update this test to use either a JSON or an ASN.1/DER ECU Manifest
    # depending on tuf.conf.METADATA_FORMAT instead of always using a JSON
    # manifest.

    # Starting with an empty ecu manifest dictionary.
    self.assertEqual(dict(), TestPrimary.instance.ecu_manifests)

    # Make sure we're starting with no nonces sent or to send.
    self.assertEqual([], TestPrimary.instance.nonces_to_send)
    self.assertEqual([], TestPrimary.instance.nonces_sent)

    sample_ecu_manifest = {
    	'signatures': [{
    	'keyid': '49309f114b857e4b29bfbff1c1c75df59f154fbc45539b2eb30c8a867843b2cb',
    	'method': 'ed25519',
      'sig': '52d19725155ccdbcabb37d016508ec0f5adcc0c16f24f1f16d6e1f71396991c4aa28a737778e3231d596cfdffc79b9e5212c8ad4bd8cd02aff7f41e803d94d0e'}],
 			'signed': {
 						'attacks_detected': '',
            'ecu_serial': 'ecu11111',
            'hardware_id': 'SecondaryPotato101',
            'installed_image': {
            	'fileinfo':
            		{
            			'hashes': {
            				'sha256':
            					'6b9f987226610bfed08b824c93bf8b2f59521fce9a2adef80c495f363c1c9c44',
                    'sha512': '706c283972c5ae69864b199e1cdd9b4b8babc14f5a454d0fd4d3b35396a04ca0b40af731671b74020a738b5108a78deb032332c36d6ae9f31fae2f8a70f7e1ce'},
                 'length': 37},
                                'filepath': '/secondary_firmware.txt'},
            'previous_timeserver_time': '2017-07-24T16:22:51Z',
            'release_counter': 1,
            'timeserver_time': '2017-07-24T16:22:51Z'}}


    # Try using the wrong vin.
    with self.assertRaises(uptane.Error):
      TestPrimary.instance.register_ecu_manifest(
          vin='13105941', # unexpected VIN
          ecu_serial='ecu11111', nonce=nonce,
          signed_ecu_manifest=sample_ecu_manifest,
          force_pydict=True)

    # Try changing the Secondary's ECU Serial so that the ECU Serial argument
    # doesn't match the ECU Serial in the manifest.
    with self.assertRaises(uptane.UnknownECU):
      TestPrimary.instance.register_ecu_manifest(
          vin=vin, # unexpected VIN
          ecu_serial='e689681291f', # unexpected ECU Serial
          nonce=nonce,
          signed_ecu_manifest=sample_ecu_manifest,
          force_pydict=True)

    # Try using an unknown ECU Serial.
    with self.assertRaises(uptane.UnknownECU):
      sample_ecu_manifest2 = copy.deepcopy(sample_ecu_manifest)
      sample_ecu_manifest2['signed']['ecu_serial'] = '12345678'
      TestPrimary.instance.register_ecu_manifest(
          vin=vin, # unexpected VIN
          ecu_serial='12345678', # unexpected ECU Serial
          nonce=nonce,
          signed_ecu_manifest=sample_ecu_manifest2,
          force_pydict=True)


    # TODO: Other possible tests here.

    # Initialize correctly this time.
    TestPrimary.instance.register_ecu_manifest(
        vin=vin, ecu_serial='ecu11111', nonce=nonce,
        signed_ecu_manifest=sample_ecu_manifest,
        force_pydict=True)

    # Make sure the provided manifest is now in the Primary's ecu manifests
    # dictionary.
    self.assertIn('ecu11111', TestPrimary.instance.ecu_manifests)
    self.assertIn(
        sample_ecu_manifest, TestPrimary.instance.ecu_manifests['ecu11111'])

    # Make sure the nonce provided was noted in the right place.
    self.assertIn(nonce, TestPrimary.instance.nonces_to_send)
    self.assertEqual([], TestPrimary.instance.nonces_sent)





  def test_15_get_nonces_to_send_and_rotate(self):

    self.assertIn(nonce, TestPrimary.instance.nonces_to_send)

    # Cycle nonces and make sure the return value is as expected from the
    # previous test (a list of one specific nonce).
    self.assertEqual(
        [nonce], TestPrimary.instance.get_nonces_to_send_and_rotate())

    # Ensure that that nonce is now listed as sent and that the list of nonces
    # to send is now empty.
    self.assertEqual([nonce], TestPrimary.instance.nonces_sent)
    self.assertEqual([], TestPrimary.instance.nonces_to_send)





  def test_20_validate_time_attestation(self):

    # Try a valid time attestation first, signed by an expected timeserver key,
    # with an expected nonce (previously "received" from a Secondary)
    original_time_attestation = time_attestation = {
        'signed': {'nonces': [nonce], 'time': '2016-11-02T21:06:05Z'},
        'signatures': [{
          'method': 'ed25519',
          'sig': 'aabffcebaa57f1d6397bdc5647764261fd23516d2996446c3c40b3f30efb2a4a8d80cd2c21a453e78bf99dafb9d0f5e56c4e072db365499fa5f2f304afec100e',
          'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'}]}

    if tuf.conf.METADATA_FORMAT == 'der':
      # Convert this time attestation to the expected ASN.1/DER format.
      time_attestation = asn1_codec.convert_signed_metadata_to_der(
          original_time_attestation,
          private_key=TestPrimary.key_timeserver_pri, resign=True)

    TestPrimary.instance.validate_time_attestation(time_attestation)


    # Prepare to try again with a bad signature.
    # This test we will conduct differently depending on TUF's current format:
    if tuf.conf.METADATA_FORMAT == 'der':
      # Fail to re-sign the DER, so that the signature is over JSON instead,
      # which results in a bad signature.
      time_attestation__badsig = asn1_codec.convert_signed_metadata_to_der(
          original_time_attestation, resign=False, datatype='time_attestation')

    else: # 'json' format
      # Rewrite the first 9 digits of the signature ('sig') to something
      # invalid.
      time_attestation__badsig = {
          'signed': {'nonces': [nonce], 'time': '2016-11-02T21:06:05Z'},
          'signatures': [{
            'method': 'ed25519',
            'sig': '987654321a57f1d6397bdc5647764261fd23516d2996446c3c40b3f30efb2a4a8d80cd2c21a453e78bf99dafb9d0f5e56c4e072db365499fa5f2f304afec100e',
            'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'}]}

    # Now actually perform the bad signature test.
    with self.assertRaises(tuf.BadSignatureError):
      TestPrimary.instance.validate_time_attestation(time_attestation__badsig)


    self.assertNotEqual(500, nonce, msg='Programming error: bad and good '
        'test nonces are equal.')

    time_attestation__wrongnonce = {
        'signed': {'nonces': [500], 'time': '2016-11-02T21:15:00Z'},
        'signatures': [{
          'method': 'ed25519',
          'sig': '4d01df35ca829fd7ead1408c250950c444db8ac51fa929a7f0288578fbf81016f0e81ed35789689481aee6b7af28ab311306397ef38572732854fb6cf2072604',
          'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'}]}

    if tuf.conf.METADATA_FORMAT == 'der':
      # Convert this time attestation to the expected ASN.1/DER format.
      time_attestation__wrongnonce = asn1_codec.convert_signed_metadata_to_der(
          time_attestation__wrongnonce,
          private_key=TestPrimary.key_timeserver_pri, resign=True)

    with self.assertRaises(uptane.BadTimeAttestation):
      TestPrimary.instance.validate_time_attestation(
          time_attestation__wrongnonce)


    # TODO: Consider other tests here.





  def test_25_generate_signed_vehicle_manifest(self):

    vehicle_manifest = TestPrimary.instance.generate_signed_vehicle_manifest()

    # If the vehicle manifest is in DER format, check its format and then
    # convert back to JSON so that we can inspect it further.
    if tuf.conf.METADATA_FORMAT == 'der':
      uptane.formats.DER_DATA_SCHEMA.check_match(vehicle_manifest)
      vehicle_manifest = asn1_codec.convert_signed_der_to_dersigned_json(
          vehicle_manifest, datatype='vehicle_manifest')

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
        'ecu11111', vehicle_manifest['signed']['ecu_version_manifests'])

    # TODO: More testing of the contents of the vehicle manifest.


    # Check the signature on the vehicle manifest.
    self.assertTrue(uptane.common.verify_signature_over_metadata(
        TestPrimary.ecu_key,
        vehicle_manifest['signatures'][0], # TODO: Deal with 1-sig assumption?
        vehicle_manifest['signed'],
        datatype='vehicle_manifest'))




  def test_30_refresh_toplevel_metadata_from_repositories(self):
    # Testing this requires that we have an OEM Repository and Director server
    # running, with particulars (e.g. address and port) specified in
    # demo/pinned.json.
    #
    # TODO: Write this in a way that draws on saved sample metadata.
    #       Don't expect an actual server to be running.
    #       This will probably entail modification to the pinned.json file to
    #       point it to a local directory instead of a remote server.

    # Check that in the fresh temp directory for this test Primary client,
    # there aren't any metadata files except root.json yet.
    self.assertEqual(
        ['root.der', 'root.json'],
        sorted(os.listdir(TEST_DIRECTOR_METADATA_DIR)))
    self.assertEqual(
        ['root.der', 'root.json'],
        sorted(os.listdir(TEST_IMAGE_REPO_METADATA_DIR)))

    try:
      TestPrimary.instance.refresh_toplevel_metadata_from_repositories()
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


    # Testing this requires that we have a Director server up and running.
    # That seems outside of the scope of this test and more of a subject for
    # integration tests.
    # TODO: Decide whether or not to spin up a Director server within this
    # test.
    secondary_w_update_errors = "BCUdemocar"
    secondary_wo_update_errors = "TCUdemocar"
    target_bad_release = '/BCU1.1.txt'
    target_bad_hardware_id = '/BCU1.2.txt'
    target_no_error = '/TCU1.1.txt'
    primary_instance.register_new_secondary(
    	secondary_w_update_errors)
    primary_instance.register_new_secondary(
    	secondary_wo_update_errors)
    self.assertIn(
    	secondary_wo_update_errors, primary_instance.my_secondaries)
    self.assertIn(
    	secondary_w_update_errors, primary_instance.my_secondaries)
    with self.assertRaises(uptane.ImageRollBack):
    	primary_instance.get_validated_target_info(target_bad_release)
    with self.assertRaises(uptane.HardwareIDMismatch):
    	primary_instance.get_validated_target_info(target_bad_hardware_id)
    # One with no error
    primary_instance.get_validated_target_info(target_no_error)




  def test_45_get_image_for_ecu(self):
    pass





  def test_50_get_metadata_for_ecu(self):
    pass





  def test_55_update_exists_for_ecu(self):
    pass

    # secondary_wo_update = "TCU222" #Secondary that will be registered #w/ primary as secondaries but will not listed by targets/director
    # #for any updates
    # unknown_secondary = "TCU221" #Secondary that will be not registered
    # #w/ primary as secondaries and will not listed by targets/director
    # #for any updates
    # secondary_w_update = "TCUdemocar" #Secondary that will be registered
    # # w/ primary as secondaries and will be listed by targets/director
    # # for updates.
    # bad_secondary_ecu_name = 5 #Invalid ECU Serial for a secondary

    # # Registering valid names
    # primary_instance.register_new_secondary(secondary_wo_update)
    # primary_instance.register_new_secondary(secondary_w_update)

    # # Registering already registered names for testing lines in register_new_secondary()
    # primary_instance.register_new_secondary(secondary_wo_update)

    # # Trying to register an invalid name
    # with self.assertRaises(tuf.FormatError):
    #   primary_instance.register_new_secondary(
    #   	bad_secondary_ecu_name)

    # #Asserting that as long as name is in a valid format it will be registered by the primary as a secondary.
    # self.assertIn(
    # 	secondary_wo_update, primary_instance.my_secondaries)
    # self.assertIn(
    # 	secondary_w_update, primary_instance.my_secondaries)

    # with self.assertRaises(uptane.UnknownECU):
    #   primary_instance._check_ecu_serial(unknown_secondary)

    # # Running a primary update cycle so it process all the files required for a establishing update cycle
    # primary_instance.primary_update_cycle()

    # #Trying to get updates for an unregistered unknown ECU
    # with self.assertRaises(uptane.UnknownECU):
    #   primary_instance.update_exists_for_ecu(unknown_secondary)

    # #Trying to get updates for a registered secondary that is not listed by targets for updates
    # self.assertFalse(primary_instance.update_exists_for_ecu(
    # 		secondary_wo_update))

    # #Trying to get updates for a registered secondary that is listed by targets for updates
    # self.assertTrue(primary_instance.update_exists_for_ecu(
    # 		secondary_w_update))

    # # delete pinned.json file because new pinned.json will be created depending on the current working directory of uptane every time the tests are run
    # #os.remove(TEST_TEMP_PINNING_FNAME)




    def test_60_hardware_id_attack(self):
      pass


# Run unit test.
if __name__ == '__main__':
  unittest.main()
