"""
<Program Name>
  test_secondary.py

<Purpose>
  Unit testing for uptane/clients/secondary.py
  Much of this is modified from test_primary.py.

<Copyright>
  See LICENSE for licensing information.
"""
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

import unittest
import os.path
import time
import shutil
import hashlib

from six.moves.urllib.error import URLError

import tuf
import tuf.formats
import tuf.conf
import tuf.client.updater

import uptane.formats
import uptane.clients.secondary as secondary
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

TEMP_CLIENT_DIRS = [
    os.path.join(TEST_DATA_DIR, 'temp_test_secondary0'),
    os.path.join(TEST_DATA_DIR, 'temp_test_secondary1'),
    os.path.join(TEST_DATA_DIR, 'temp_test_secondary2')]

# I'll initialize these in the __init__ test, and use this for the simple
# non-damaging tests so as to avoid creating objects all over again.
secondary_instances = [None, None, None]

# Changing these values would require producing new signed test data from the
# Timeserver (in the case of nonce) or a Secondary (in the case of the others).
nonce = 5
vins = ['democar', 'democar', '000']
ecu_serials = ['TCUdemocar', '00000', '00000']

# Set starting firmware fileinfo (that this ECU had coming from the factory)
# It will serve as the initial firmware state for the Secondary clients.
factory_firmware_fileinfo = {
    'filepath': '/secondary_firmware.txt',
    'fileinfo': {
        'hashes': {
            'sha512': '706c283972c5ae69864b199e1cdd9b4b8babc14f5a454d0fd4d3b35396a04ca0b40af731671b74020a738b5108a78deb032332c36d6ae9f31fae2f8a70f7e1ce',
            'sha256': '6b9f987226610bfed08b824c93bf8b2f59521fce9a2adef80c495f363c1c9c44'},
        'length': 37}}

expected_updated_fileinfo = {
    'filepath': '/TCU1.1.txt',
    'fileinfo': {
        'custom': {'ecu_serial': 'TCUdemocar'},
        'hashes': {
            'sha512': '94d7419b8606103f363aa17feb875575a978df8e88038ea284ff88d90e534eaa7218040384b19992cc7866f5eca803e1654c9ccdf3b250d6198b3c4731216db4',
            'sha256': '56d7cd56a85e34e40d005e1f79c0e95d6937d5528ac0b301dbe68d57e03a5c21'},
        'length': 17}}


def destroy_temp_dir():
  # Clean up anything that may currently exist in the temp test directories.
  for client_dir in TEMP_CLIENT_DIRS:
    if os.path.exists(client_dir):
      shutil.rmtree(client_dir)





class TestSecondary(unittest.TestCase):
  """
  "unittest"-style test class for the Secondary module in the reference
  implementation

  Note that these tests are NOT entirely independent of each other.
  Several of them build on the results of previous tests. This is an unusual
  pattern but saves code and works at least for now.
  """

  # Class variables
  secondary_ecu_key = None
  key_timeserver_pub = None
  key_timeserver_pri = None
  key_directortargets_pub = None
  initial_time = None

  @classmethod
  def setUpClass(cls):
    """
    This is run once for the full class (and so the full module, which contains
    only one class), before all tests. It prepares some variables and stores
    them in the class.
    """

    destroy_temp_dir()

    # Load the private key for this Secondary ECU.
    cls.secondary_ecu_key = uptane.common.canonical_key_from_pub_and_pri(
        demo.import_public_key('secondary'),
        demo.import_private_key('secondary'))

    # Load the public timeserver key.
    cls.key_timeserver_pub = demo.import_public_key('timeserver')
    cls.key_timeserver_pri = demo.import_private_key('timeserver')

    # Load the public director key.
    cls.key_directortargets_pub = demo.import_public_key('director')

    # Generate a trusted initial time for the Secondaries.
    cls.initial_time = tuf.formats.unix_timestamp_to_datetime(
        int(time.time())).isoformat() + 'Z'
    tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(cls.initial_time)

    # Set up client directories for the two Secondaries, containing the
    # initial root.json and root.der (both, for good measure) metadata files
    # so that the clients can validate further metadata they obtain.
    # NOTE that running multiple clients in the same Python process does not
    # work normally in the reference implementation, as the value of
    # tuf.conf.repository_directories is client-specific, and it is set during
    # uptane.common.create_directory_structure_for_client, and used when a
    # client is created (initialization of a Secondary in our case)
    # We're going to cheat in this test module for the purpose of testing
    # and update tuf.conf.repository_directories before each Secondary is
    # created,  to refer to the client we're creating.
    for client_dir in TEMP_CLIENT_DIRS:
      uptane.common.create_directory_structure_for_client(
          client_dir,
          TEST_PINNING_FNAME,
          {'imagerepo': TEST_IMAGE_REPO_ROOT_FNAME,
          'director': TEST_DIRECTOR_ROOT_FNAME})




  @classmethod
  def tearDownClass(cls):
    """This is run once for the full class (and so the full module, which
    contains only one class), after all tests."""
    destroy_temp_dir()





  def test_01_init(self):
    """
    Tests uptane.clients.secondary.Secondary::__init__()
    Note that this doesn't test the root files provided to the constructor, as
    those aren't used at all in the initialization; those will be tested by
    attempting an update in the test for process_metadata below.
    """

    # TODO: Test with invalid pinning file
    # TODO: Test with pinning file lacking a Director repo.

    # Now try creating a Secondary with a series of bad arguments, expecting
    # errors.

    # Invalid full_client_dir
    with self.assertRaises(tuf.FormatError):
      secondary.Secondary(
          full_client_dir=42,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # TODO: Test providing a nonexistent directory for full_client_dir
    # TODO: Test providing the wrong directory for full_client_dir.
    #       Both of these tests may require saving additional clients and
    #       running the later tests with them.

    # Invalid director_repo_name
    with self.assertRaises(tuf.FormatError):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=42,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Unknown director_repo_name
    with self.assertRaises(uptane.Error):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name='string_that_is_not_a_known_repo_name',
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Invalid VIN:
    with self.assertRaises(tuf.FormatError):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=5,
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Invalid ECU Serial
    with self.assertRaises(tuf.FormatError):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=500,
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Invalid ECU Key
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key={''},
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Invalid initial time:
    with self.assertRaises(tuf.FormatError):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time='potato',
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=TestSecondary.key_directortargets_pub,
          partial_verifying=False)

    # Invalid director_public_key:
    with self.assertRaises(tuf.FormatError):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key={''},
          partial_verifying=False)

    # Inconsistent arguments, partial_verifying and director_public_key.
    # partial verification requires a director_public_key argument, as it does
    # not use the normal trust chain. Providing a director_public_key when not
    # performing partial verification makes no sense, as the keys to be used
    # for full verification are determined based on the root metadata file.
    with self.assertRaises(uptane.Error):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=TestSecondary.key_directortargets_pub,
          partial_verifying=False)
    with self.assertRaises(uptane.Error):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=True)


    # Invalid timeserver key
    with self.assertRaises(tuf.FormatError):
      secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIRS[0],
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vins[0],
          ecu_serial=ecu_serials[0],
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.initial_time, # INVALID
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)



    # Try initializing three Secondaries, expecting the three calls to work.
    # Save the instances for future tests as class variables to save time and
    # code.

    # Recall that, as mentioned in a comment in the SetUpClass method, running
    # multiple reference implementation updater clients simultaneously in the
    # same Python process is not supported, and we're going to engage in the
    # hack of swapping tuf.conf.repository_directories back and forth to make
    # it work for these tests.


    # Initialize three clients and perform checks on each of them.
    for i in range(0, len(TEMP_CLIENT_DIRS)):
      client_dir = TEMP_CLIENT_DIRS[i]
      ecu_serial = ecu_serials[i]
      vin = vins[i]

      # Try initializing each of three secondaries, expecting these calls to
      # work. Save the instances for future tests as elements in a module list
      # variable(secondary_instances) to save time and code.
      tuf.conf.repository_directory = client_dir
      secondary_instances[i] = secondary.Secondary(
          full_client_dir=client_dir,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=ecu_serial,
          ecu_key=TestSecondary.secondary_ecu_key,
          time=TestSecondary.initial_time,
          timeserver_public_key=TestSecondary.key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

      instance = secondary_instances[i]

      # Check the fields initialized in the instance to make sure they're correct.

      # Fields initialized from parameters
      self.assertEqual(client_dir, instance.full_client_dir)
      self.assertEqual(demo.DIRECTOR_REPO_NAME, instance.director_repo_name)
      self.assertEqual(vin, instance.vin)
      self.assertEqual(ecu_serial, instance.ecu_serial)
      self.assertEqual(TestSecondary.secondary_ecu_key, instance.ecu_key)
      self.assertEqual(
          TestSecondary.initial_time, instance.all_valid_timeserver_times[0])
      self.assertEqual(
          TestSecondary.initial_time, instance.all_valid_timeserver_times[1])
      self.assertEqual(
          TestSecondary.key_timeserver_pub, instance.timeserver_public_key)
      self.assertTrue(None is instance.director_public_key)
      self.assertFalse(instance.partial_verifying)

      # Fields initialized, but not directly with parameters
      self.assertTrue(None is instance.last_nonce_sent)
      self.assertTrue(instance.nonce_next) # Random value
      self.assertIsInstance(
          instance.updater, tuf.client.updater.Updater)


      # Now, fix the updater's pinned metadata, since the pinned metadata we
      # fed in was actually for the Primary (which connects to central
      # services) instead of for the Secondary (which obtains metadata and
      # images via TUF from an unverified local directory, then validates
      # them). Do this for both clients.
      # The location of the files will be as follows, after the sample
      # metadata archive is expanded (in test 40 below):

      image_repo_mirror = ['file://' + client_dir + '/unverified/imagerepo']
      director_mirror = ['file://' + client_dir + '/unverified/director']
      if vin == '000':
        # Simulate unavailable Director repo for the third Secondary
        director_mirror[0] += '/nonexistent_directory'

      repository_urls = instance.updater.pinned_metadata['repositories']
      repository_urls['imagerepo']['mirrors'] = image_repo_mirror
      repository_urls['director']['mirrors'] = director_mirror

      # Also fix the copied pinned metadata in the individual repo updaters
      # in the updater.
      instance.updater.repositories['imagerepo'].mirrors = image_repo_mirror
      instance.updater.repositories['director'].mirrors = director_mirror






  def test_10_nonce_rotation(self):
    """
    Tests two uptane.clients.secondary.Secondary methods:
      - change_nonce()
      - set_nonce_as_sent()
    """
    # We'll just test one of the three client instances, since it shouldn't
    # make a difference.
    instance = secondary_instances[0]

    old_nonce = instance.nonce_next

    instance.change_nonce()
    # Collision is unlikely in the next line (new random nonce equal to
    # previous).
    self.assertNotEqual(old_nonce, instance.nonce_next)

    instance.set_nonce_as_sent()
    self.assertEqual(instance.last_nonce_sent, instance.nonce_next)





  def test_20_validate_time_attestation(self):
    """
    Tests uptane.clients.secondary.Secondary::validate_time_attestation()
    """

    # We'll just test one of the three client instances, since it shouldn't
    # make a difference.
    instance = secondary_instances[0]

    # Try a valid time attestation first, signed by an expected timeserver key,
    # with an expected nonce (previously "received" from a Secondary)
    original_time_attestation = time_attestation = {
        'signed': {'nonces': [nonce], 'time': '2016-11-02T21:06:05Z'},
        'signatures': [{
          'method': 'ed25519',
          'sig': 'aabffcebaa57f1d6397bdc5647764261fd23516d2996446c3c40b3f30efb2a4a8d80cd2c21a453e78bf99dafb9d0f5e56c4e072db365499fa5f2f304afec100e',
          'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'}]}

    # Make sure that the Secondary thinks that it sent the nonce listed in the
    # sample data above.
    instance.last_nonce_sent = nonce

    if tuf.conf.METADATA_FORMAT == 'der':
      # Convert this time attestation to the expected ASN.1/DER format.
      time_attestation = asn1_codec.convert_signed_metadata_to_der(
          original_time_attestation,
          private_key=TestSecondary.key_timeserver_pri, resign=True)

    # If the time_attestation is not deemed valid, an exception will be raised.
    instance.validate_time_attestation(time_attestation)


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
      instance.validate_time_attestation(time_attestation__badsig)


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
          private_key=TestSecondary.key_timeserver_pri, resign=True)

    with self.assertRaises(uptane.BadTimeAttestation):
      instance.validate_time_attestation(time_attestation__wrongnonce)


    # TODO: Consider other tests here.





  def test_25_generate_signed_ecu_manifest(self):
    """
    Tests uptane.clients.secondary.Secondary::generate_signed_ecu_manifest()
    """

    # We'll just test one of the three client instances, since it shouldn't
    # make a difference.
    ecu_manifest = secondary_instances[0].generate_signed_ecu_manifest()

    # If the ECU Manifest is in DER format, check its format and then
    # convert back to JSON so that we can inspect it further.
    if tuf.conf.METADATA_FORMAT == 'der':
      uptane.formats.DER_DATA_SCHEMA.check_match(ecu_manifest)
      ecu_manifest = asn1_codec.convert_signed_der_to_dersigned_json(
          ecu_manifest, datatype='ecu_manifest')

    # Now it's not in DER format, whether or not it started that way.
    # Check its format and inspect it.
    uptane.formats.SIGNABLE_ECU_VERSION_MANIFEST_SCHEMA.check_match(
        ecu_manifest)

    # Test contents of the ECU Manifest.
    # Make sure there is exactly one signature. (Not specified by the
    # Implementation Specification, but the way we do it. Using more is
    # unlikely to be particularly useful).
    self.assertEqual(1, len(ecu_manifest['signatures']))

    # TODO: Check some values from the ECU Manifest

    # Check the signature on the ECU Manifest.
    self.assertTrue(uptane.common.verify_signature_over_metadata(
        TestSecondary.secondary_ecu_key,
        ecu_manifest['signatures'][0], # TODO: Deal with 1-sig assumption?
        ecu_manifest['signed'],
        datatype='ecu_manifest'))





  def test_40_process_metadata(self):
    """
    Tests uptane.clients.secondary.Secondary::process_metadata()

    Tests three clients:
     - secondary_instances[0]: an update is provided in Director metadata
     - secondary_instances[1]: no update is provided in Director metadata
     - secondary_instances[2]: no Director metadata can be retrieved
    """

    # --- Test this test module's setup (defensive)
    # First, check the source directories, from which the temp dir is copied.
    # This first part is testing this test module, since this setup was done
    # above in setUpClass(), to maintain test integrity over time.
    # We should see only root.(json or der).
    for data_directory in [
        TEST_DIRECTOR_METADATA_DIR, TEST_IMAGE_REPO_METADATA_DIR]:

      self.assertEqual(
          ['root.der', 'root.json'],
          sorted(os.listdir(data_directory)))

    # Next, check that the clients' metadata directories have the same
    # properties -- that the correct root metadata file was transferred to the
    # client directories when the directories were created by the
    # create_directory_structure_for_client() calls in setUpClass above, and
    # only the root metadata file.
    for client_dir in TEMP_CLIENT_DIRS:
      for repo in ['director', 'imagerepo']:
        self.assertEqual(
            ['root.' + tuf.conf.METADATA_FORMAT],
            sorted(os.listdir(os.path.join(
                client_dir, 'metadata', repo, 'current'))))

    # --- Set up this test

    # Location of the sample Primary-produced metadata archive
    sample_archive_fname = os.path.join(
        uptane.WORKING_DIR, 'samples', 'metadata_samples_long_expiry',
        'update_to_one_ecu', 'full_metadata_archive.zip')

    assert os.path.exists(sample_archive_fname), 'Cannot test ' \
        'process_metadata; unable to find expected sample metadata archive' + \
        ' at ' + repr(sample_archive_fname)


    # Continue set-up followed by the test, per client.
    for i in range(0, len(TEMP_CLIENT_DIRS)):
      client_dir = TEMP_CLIENT_DIRS[i]
      instance = secondary_instances[i]

      # Make sure TUF uses the right client directory.
      # Hack to allow multiple clients to run in the same Python process.
      # See comments in SetUpClass() method.
      tuf.conf.repository_directory = client_dir

      # Location in the client directory to which we'll copy the archive.
      archive_fname = os.path.join(client_dir, 'full_metadata_archive.zip')

      # Copy the sample archive into place in the client directory.
      shutil.copy(sample_archive_fname, archive_fname)


      # --- Perform the test

      # Process this sample metadata.

      if instance is secondary_instances[2]:
        # Expect the update to fail for the third Secondary client.
        with self.assertRaises(tuf.NoWorkingMirrorError):
          instance.process_metadata(archive_fname)
        continue

      else:
        instance.process_metadata(archive_fname)

      # Make sure the archive of unverified metadata was expanded
      for repo in ['director', 'imagerepo']:
        for role in ['root', 'snapshot', 'targets', 'timestamp']:
          self.assertTrue(os.path.exists(client_dir + '/unverified/' + repo +
              '/metadata/' + role + '.' + tuf.conf.METADATA_FORMAT))


    # Verify the results of the test, which are different for the three clients.

    # First: Check the top-level metadata files in the client directories.

    # For clients 0 and 1, we expect root, snapshot, targets, and timestamp for
    # both director and image repo.
    for client_dir in [TEMP_CLIENT_DIRS[0], TEMP_CLIENT_DIRS[1]]:
      for repo in ['director', 'imagerepo']:
        self.assertEqual([
            'root.' + tuf.conf.METADATA_FORMAT,
            'snapshot.' + tuf.conf.METADATA_FORMAT,
            'targets.' + tuf.conf.METADATA_FORMAT,
            'timestamp.' + tuf.conf.METADATA_FORMAT],
            sorted(os.listdir(os.path.join(client_dir, 'metadata', repo,
            'current'))))

    # For client 2, we are certain that Director metadata will have failed to
    # update. Image Repository metadata may or may not have updated before the
    # Director repository update failure, so we don't check that. Client 2
    # started with root metadata for the Director repository, so that is all
    # we expect to find.
    self.assertEqual(
        ['root.' + tuf.conf.METADATA_FORMAT],
        sorted(os.listdir(os.path.join(TEMP_CLIENT_DIRS[2], 'metadata',
        'director', 'current'))))


    # Second: Check targets each Secondary client has been instructed to
    # install (and has in turn validated).
    # Client 0 should have validated expected_updated_fileinfo.
    self.assertEqual(
        expected_updated_fileinfo,
        secondary_instances[0].validated_targets_for_this_ecu[0])

    # Clients 1 and 2 should have no validated targets.
    self.assertFalse(secondary_instances[1].validated_targets_for_this_ecu)
    self.assertFalse(secondary_instances[2].validated_targets_for_this_ecu)





  def test_50_validate_image(self):

    image_fname = 'TCU1.1.txt'
    sample_image_location = os.path.join(demo.DEMO_DIR, 'images')
    client_unverified_targets_dir = TEMP_CLIENT_DIRS[0] + '/unverified_targets'

    if os.path.exists(client_unverified_targets_dir):
      shutil.rmtree(client_unverified_targets_dir)
    os.mkdir(client_unverified_targets_dir)

    shutil.copy(
        os.path.join(sample_image_location, image_fname),
        client_unverified_targets_dir)

    secondary_instances[0].validate_image(image_fname)

    with self.assertRaises(uptane.Error):
      secondary_instances[1].validate_image(image_fname)
    with self.assertRaises(uptane.Error):
      secondary_instances[2].validate_image(image_fname)





# Run unit tests.
if __name__ == '__main__':
  unittest.main()
