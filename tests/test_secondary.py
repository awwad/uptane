"""
<Program Name>
  test_secondary.py

<Purpose>
  Unit testing for uptane/clients/secondary.py
  Much of this is copied from test_primary.py and then modified slightly
"""
from __future__ import print_function
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

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
TEMP_CLIENT_DIR = os.path.join(TEST_DATA_DIR, 'temp_test_secondary')

# I'll initialize this in one of the early tests, and use this for the simple
# non-damaging tests so as to avoid creating objects all over again.
secondary_instance = None

# Changing some of these values would require producing new signed test data
# from the Timeserver or a Secondary.
nonce = 5
vin = '000'
ecu_serial = '00000'

# Initialize these in setUpModule below.
secondary_ecu_key = None
key_timeserver_pub = None
key_timeserver_pri = None # simplifies use of test data (re-sign)
key_directortargets_pub = None
clock = None

# Set starting firmware fileinfo (that this ECU had coming from the factory)
factory_firmware_fileinfo = {
    'filepath': '/secondary_firmware.txt',
    'fileinfo': {
        'hashes': {
            'sha512': '706c283972c5ae69864b199e1cdd9b4b8babc14f5a454d0fd4d3b35396a04ca0b40af731671b74020a738b5108a78deb032332c36d6ae9f31fae2f8a70f7e1ce',
            'sha256': '6b9f987226610bfed08b824c93bf8b2f59521fce9a2adef80c495f363c1c9c44'},
        'length': 37}}



def destroy_temp_dir():
  # Clean up anything that may currently exist in the temp test directory.
  if os.path.exists(TEMP_CLIENT_DIR):
    shutil.rmtree(TEMP_CLIENT_DIR)





def setUpModule():
  """
  This is run once for the full module, before all tests.
  It prepares some globals, including a single Secondary ECU client instance.
  When finished, it will also start up an OEM Repository Server,
  Director Server, and Time Server. Currently, it requires them to be already
  running.
  """
  global secondary_ecu_key
  global key_timeserver_pub
  global key_timeserver_pri
  global key_directortargets_pub
  global clock

  destroy_temp_dir()

  # Load the private key for this Secondary ECU.
  key_pub = demo.import_public_key('secondary')
  key_pri = demo.import_private_key('secondary')
  secondary_ecu_key = uptane.common.canonical_key_from_pub_and_pri(
      key_pub, key_pri)

  # Load the public timeserver key.
  key_timeserver_pub = demo.import_public_key('timeserver')
  key_timeserver_pri = demo.import_private_key('timeserver')

  # Load the public director key.
  key_directortargets_pub = demo.import_public_key('director')

  # Generate a trusted initial time for the Secondary.
  clock = tuf.formats.unix_timestamp_to_datetime(int(time.time()))
  clock = clock.isoformat() + 'Z'
  tuf.formats.ISO8601_DATETIME_SCHEMA.check_match(clock)






def tearDownModule():
  """This is run once for the full module, after all tests."""
  destroy_temp_dir()





class TestSecondary(unittest.TestCase):
  """
  "unittest"-style test class for the Secondary module in the reference
  implementation

  Please note that these tests are NOT entirely independent of each other.
  Several of them build on the results of previous tests. This is an unusual
  pattern but saves code and works at least for now.
  """

  def test_01_init(self):
    """
    Note that this doesn't test the root files provided, as those aren't used
    at all in the initialization; for that, we'll have to test the update cycle.
    """

    global secondary_instance


    # Set up a client directory first.
    uptane.common.create_directory_structure_for_client(
        TEMP_CLIENT_DIR,
        TEST_PINNING_FNAME,
        {'imagerepo': TEST_IMAGE_REPO_ROOT_FNAME,
        'director': TEST_DIRECTOR_ROOT_FNAME})


    # TODO: Test with invalid pinning file
    # TODO: Test with pinning file lacking a Director repo.

    # Now try creating a Secondary with a series of bad arguments, expecting
    # errors.

    # Invalid VIN:
    with self.assertRaises(tuf.FormatError):
      s = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=5,
          ecu_serial=ecu_serial,
          ecu_key=secondary_ecu_key,
          time=clock,
          timeserver_public_key=key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Invalid ECU Serial
    with self.assertRaises(tuf.FormatError):
      s = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=500,
          ecu_key=secondary_ecu_key,
          time=clock,
          timeserver_public_key=key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Invalid ECU Key
      s = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=ecu_serial,
          ecu_key={''},
          time=clock,
          timeserver_public_key=key_timeserver_pub,
          firmware_fileinfo=firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)

    # Invalid time:
    with self.assertRaises(tuf.FormatError):
      s = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=ecu_serial,
          ecu_key=secondary_ecu_key,
          time='potato',
          timeserver_public_key=key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=key_directortargets_pub,
          partial_verifying=False)

    # Invalid director_public_key:
    with self.assertRaises(tuf.FormatError):
      s = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=ecu_serial,
          ecu_key=secondary_ecu_key,
          time=clock,
          timeserver_public_key=key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key={''},
          partial_verifying=False)

    # Inconsistent arguments, partial_verifying and director_public_key.
    # partial verification requires a director_public_key argument, as it does
    # not use the normal trust chain. Providing a director_public_key when not
    # performing partial verification makes no sense, as the keys to be used
    # for full verification are determined based on the root metadata file.
    with self.assertRaises(uptane.Error):
      s = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=ecu_serial,
          ecu_key=secondary_ecu_key,
          time=clock,
          timeserver_public_key=key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=key_directortargets_pub,
          partial_verifying=False)
    with self.assertRaises(uptane.Error):
      s = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=ecu_serial,
          ecu_key=secondary_ecu_key,
          time=clock,
          timeserver_public_key=key_timeserver_pub,
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=True)


    # Invalid timeserver key
    with self.assertRaises(tuf.FormatError):
      secondary_instance = secondary.Secondary(
          full_client_dir=TEMP_CLIENT_DIR,
          director_repo_name=demo.DIRECTOR_REPO_NAME,
          vin=vin,
          ecu_serial=ecu_serial,
          ecu_key=secondary_ecu_key,
          time=clock,
          timeserver_public_key=clock, # INVALID
          firmware_fileinfo=factory_firmware_fileinfo,
          director_public_key=None,
          partial_verifying=False)


    print(TEMP_CLIENT_DIR)

    # Try creating a Secondary, expecting it to work. Initializes a Secondary
    # ECU, making a client directory and copying the root file from the
    # repositories. Save the result for future tests, to save time and code.
    # TODO: Stick TEST_PINNING_FNAME in the right place.
    # Stick TEST_IMAGE_REPO_ROOT_FNAME and TEST_DIRECTOR_ROOT_FNAME in the right place.
    secondary_instance = secondary.Secondary(
        full_client_dir=TEMP_CLIENT_DIR,
        director_repo_name=demo.DIRECTOR_REPO_NAME,
        vin=vin,
        ecu_serial=ecu_serial,
        ecu_key=secondary_ecu_key,
        time=clock,
        timeserver_public_key=key_timeserver_pub,
        firmware_fileinfo=factory_firmware_fileinfo,
        director_public_key=None,
        partial_verifying=False)


    # Check the fields initialized in the instance to make sure they're correct.

    # Fields initialized from parameters
    self.assertEqual(TEMP_CLIENT_DIR, secondary_instance.full_client_dir)
    self.assertEqual(
        demo.DIRECTOR_REPO_NAME, secondary_instance.director_repo_name)
    self.assertEqual(vin, secondary_instance.vin)
    self.assertEqual(ecu_serial, secondary_instance.ecu_serial)
    self.assertEqual(secondary_ecu_key, secondary_instance.ecu_key)
    self.assertEqual(clock, secondary_instance.all_valid_timeserver_times[0])
    self.assertEqual(clock, secondary_instance.all_valid_timeserver_times[1])
    self.assertEqual(
        key_timeserver_pub, secondary_instance.timeserver_public_key)
    self.assertTrue(None is secondary_instance.director_public_key)
    self.assertFalse(secondary_instance.partial_verifying)

    # Fields initialized, but not directly with parameters
    self.assertTrue(None is secondary_instance.last_nonce_sent)
    self.assertTrue(secondary_instance.nonce_next) # Random value
    self.assertIsInstance(
        secondary_instance.updater, tuf.client.updater.Updater)


    # Now, fix the updater's pinned metadata, since the pinned metadata we fed
    # in was actually for the Primary (which connects to central services)
    # instead of for the Secondary (which obtains metadata and images via TUF
    # from an unverified local directory, then validates them).
    # The location of the files will be as follows, after the sample
    # metadata archive is expanded (in test 40 below):
    image_repo_mirror = ['file://' + TEMP_CLIENT_DIR + '/unverified/imagerepo']
    director_mirror = ['file://' + TEMP_CLIENT_DIR + '/unverified/director']
    repository_urls = secondary_instance.updater.pinned_metadata['repositories']
    repository_urls['imagerepo']['mirrors'] = image_repo_mirror
    repository_urls['director']['mirrors'] = director_mirror

    # Also fix the copied pinned metadata in the individual repo updaters
    # in the updater.
    secondary_instance.updater.repositories['imagerepo'].mirrors = \
        image_repo_mirror
    secondary_instance.updater.repositories['director'].mirrors = \
        director_mirror






  def test_10_nonce_rotation(self):

    old_nonce = secondary_instance.nonce_next

    secondary_instance.change_nonce()
    # Collision is unlikely in the next line (new random nonce equal to
    # previous).
    self.assertNotEqual(old_nonce, secondary_instance.nonce_next)


    secondary_instance.set_nonce_as_sent()
    self.assertEqual(
        secondary_instance.last_nonce_sent, secondary_instance.nonce_next)





  def test_20_validate_time_attestation(self):

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
    secondary_instance.last_nonce_sent = nonce

    if tuf.conf.METADATA_FORMAT == 'der':
      # Convert this time attestation to the expected ASN.1/DER format.
      time_attestation = asn1_codec.convert_signed_metadata_to_der(
          original_time_attestation, private_key=key_timeserver_pri, resign=True)

    secondary_instance.validate_time_attestation(time_attestation)


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
      secondary_instance.validate_time_attestation(time_attestation__badsig)


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
          private_key=key_timeserver_pri, resign=True)

    with self.assertRaises(uptane.BadTimeAttestation):
      secondary_instance.validate_time_attestation(time_attestation__wrongnonce)


    # TODO: Consider other tests here.





  def test_25_generate_signed_ecu_manifest(self):

    ecu_manifest = secondary_instance.generate_signed_ecu_manifest()

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
    # TODO: Check some values from the ECU Manifest
    # TODO: Check some values from the ECU Manifest

    # TODO: More testing of the contents of the ECU Manifest.

    # Check the signature on the ECU Manifest.
    self.assertTrue(uptane.common.verify_signature_over_metadata(
        secondary_ecu_key,
        ecu_manifest['signatures'][0], # TODO: Deal with 1-sig assumption?
        ecu_manifest['signed'],
        datatype='ecu_manifest'))




  def test_40_process_metadata(self):

    # Check that in the fresh temp directory for this test Secondary client,
    # there aren't any metadata files except root.json yet.
    self.assertEqual(
        ['root.der', 'root.json'],
        sorted(os.listdir(TEST_DIRECTOR_METADATA_DIR)))
    self.assertEqual(
        ['root.der', 'root.json'],
        sorted(os.listdir(TEST_IMAGE_REPO_METADATA_DIR)))

    # Location of the sample Primary-produced metadata archive
    sample_archive_fname = os.path.join(
        uptane.WORKING_DIR, 'samples', 'metadata_samples_long_expiry',
        'update_to_one_ecu', 'full_metadata_archive.zip')

    # Location in the client directory to which we'll copy the archive.
    archive_fname = os.path.join(TEMP_CLIENT_DIR, 'full_metadata_archive.zip')

    assert os.path.exists(sample_archive_fname), 'Cannot test ' \
        'process_metadata; unable to find expected sample metadata archive' + \
        ' at ' + repr(sample_archive_fname)

    # Copy the sample archive into place in the client directory.
    shutil.copy(sample_archive_fname, archive_fname)

    # Process this sample metadata.
    secondary_instance.process_metadata(archive_fname)

    # Now, either some element of the metadata could not be validated, or
    # this Secondary ECU has not been assigned an update, or the field
    # validated_targets_for_this_ecu is now populated with the validated
    # target that this ECU has been instructed to install.
    print(secondary_instance.validated_targets_for_this_ecu)

    # TODO: Check value in validated_targets_for_this_ecu

    # TODO: Make sure the archive was expanded

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





  def test_50_validate_image(self):
    # TODO: Test this method.
    pass









# Run unit test.
if __name__ == '__main__':
  unittest.main()
