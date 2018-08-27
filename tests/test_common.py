"""
<Program Name>
  test_common.py

<Purpose>
  Unit and integration testing for uptane/common.py

<Copyright>
  See LICENSE for licensing information.
"""
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.

import unittest
import os.path
import shutil # for rmtree
import copy
import json

import tuf
import tuf.formats
import tuf.conf

import uptane.common as common
import uptane.encoding.asn1_codec as asn1_codec

from uptane.encoding.asn1_codec import DATATYPE_TIME_ATTESTATION
from uptane.encoding.asn1_codec import DATATYPE_ECU_MANIFEST
from uptane.encoding.asn1_codec import DATATYPE_VEHICLE_MANIFEST

import demo # for generate_key, import_public_key, import_private_key

# The public and private keys to use during testing, including the Director
# repository keys (public and private) as well as client keys (public).
keys_pri = {}
keys_pub = {}

SAMPLES_DIR = os.path.join(uptane.WORKING_DIR, 'samples')
TEST_DIRECTOR_ROOT_FNAME = os.path.join(
  SAMPLES_DIR, 'metadata_samples_long_expiry', 'initial_w_no_update',
  'full_metadata_archive', 'director', 'metadata',
  'root.' + tuf.conf.METADATA_FORMAT)
TEST_IMAGE_REPO_ROOT_FNAME = os.path.join(
  SAMPLES_DIR, 'metadata_samples_long_expiry', 'initial_w_no_update',
  'full_metadata_archive', 'imagerepo', 'metadata',
  'root.' + tuf.conf.METADATA_FORMAT)

TEST_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'tests', 'test_data')
TEST_PINNING_FNAME = os.path.join(TEST_DATA_DIR, 'pinned.json')
TEMP_CLIENT_DIR = os.path.join(TEST_DATA_DIR, 'temp_test_common')



class TestCommon(unittest.TestCase):
  """
  "unittest"-style test class for the common.py module in the reference
  implementation
  """

  @classmethod
  def setUpClass(cls):
    """
    This is run once for the class, before all tests. Since there is only one
    class, this runs once. It prepares some variables and stores them in the
    class.
    """
    # Load a public and corresponding private key to use in testing.
    for key in ['secondary', 'primary', 'timeserver']:
      keys_pri[key] = demo.import_private_key(key)
      keys_pub[key] = demo.import_public_key(key)
      assert keys_pri[key]['keyid'] == keys_pub[key]['keyid'], 'Bad test data!'





  def test_signing(self):
    """
    Tests:
     - sign_over_metadata()
     - sign_signable()
     - verify_signature_over_metadata()

    using sample data from samples/. sign_signable() wraps sign_over_metadata(),
    and verify_signature_over_metadata() is tested together with them so that
    they can be tested against each other.

    These functions are also tested in the course of testing other modules.
    """

    # Load sample data, either JSON or ASN.1/DER depending on METADATA_FORMAT.
    if tuf.conf.METADATA_FORMAT == 'json':
      sample_time_attestation = json.load(open(os.path.join(
          SAMPLES_DIR, 'sample_timeserver_attestation.json')))

      sample_vehicle_manifest = json.load(open(os.path.join(SAMPLES_DIR,
          'sample_vehicle_version_manifest_democar.json')))

      sample_ecu_manifest = json.load(open(os.path.join(SAMPLES_DIR,
          'sample_ecu_manifest_TCUdemocar.json')))

      fresh_time_attestation = tuf.formats.make_signable(
          sample_time_attestation['signed'])

      fresh_vehicle_manifest = tuf.formats.make_signable(
          sample_vehicle_manifest['signed'])

      fresh_ecu_manifest = tuf.formats.make_signable(
          sample_ecu_manifest['signed'])


    elif tuf.conf.METADATA_FORMAT == 'der':
      sample_time_attestation = \
          asn1_codec.convert_signed_der_to_dersigned_json(open(os.path.join(
          SAMPLES_DIR, 'sample_timeserver_attestation.der'), 'rb').read(),
          DATATYPE_TIME_ATTESTATION)

      sample_vehicle_manifest = \
          asn1_codec.convert_signed_der_to_dersigned_json(open(os.path.join(
          SAMPLES_DIR, 'sample_vehicle_version_manifest_democar.der'),
          'rb').read(), DATATYPE_VEHICLE_MANIFEST)

      sample_ecu_manifest = \
          asn1_codec.convert_signed_der_to_dersigned_json(open(os.path.join(
          SAMPLES_DIR, 'sample_ecu_manifest_TCUdemocar.der'), 'rb').read(),
          DATATYPE_ECU_MANIFEST)

      fresh_time_attestation = tuf.formats.make_signable(
          sample_time_attestation['signed'])

      fresh_vehicle_manifest = tuf.formats.make_signable(
          sample_vehicle_manifest['signed'])

      fresh_ecu_manifest = tuf.formats.make_signable(
          sample_ecu_manifest['signed'])

    else:
      assert False, 'Unknown metadata format: test code needs rewriting?'



    # Produce a few unsigned signable copies for additional tests.
    fresh_time_attestation2 = copy.deepcopy(fresh_time_attestation)
    fresh_ecu_manifest2 = copy.deepcopy(fresh_ecu_manifest)
    fresh_ecu_manifest3 = copy.deepcopy(fresh_ecu_manifest)
    fresh_ecu_manifest4 = copy.deepcopy(fresh_ecu_manifest)




    # Correctly sign each of the three pieces of metadata with one key,
    # once using sign_over_metadata directly and once using sign_signable.
    # Check these in three ways (in this order, for test code readability):
    # 1. Make sure that the signatures created using the higher and lower level
    #    methods are identical.
    # 2. Compare the signatures produced to the previously-produced signatures
    #    in the sample data.
    # 3. Run common.verify_signature_over_metadata and ensure that the
    #    signature is deemed valid.
    # The combination also tests common.verify_signature_over_metadata.

    # Time Attestation
    sig_alone = common.sign_over_metadata(keys_pri['timeserver'],
        fresh_time_attestation['signed'], DATATYPE_TIME_ATTESTATION)
    common.sign_signable(fresh_time_attestation, [keys_pri['timeserver']],
        DATATYPE_TIME_ATTESTATION)
    self.assertEqual(sig_alone, fresh_time_attestation['signatures'][0])
    self.assertEqual(fresh_time_attestation['signatures'],
        sample_time_attestation['signatures'])
    self.assertTrue(common.verify_signature_over_metadata(
        keys_pub['timeserver'], fresh_time_attestation['signatures'][0],
        fresh_time_attestation['signed'], DATATYPE_TIME_ATTESTATION))

    # Vehicle Manifest
    sig_alone = common.sign_over_metadata(keys_pri['primary'],
        fresh_vehicle_manifest['signed'], DATATYPE_VEHICLE_MANIFEST)
    common.sign_signable(fresh_vehicle_manifest, [keys_pri['primary']],
        DATATYPE_VEHICLE_MANIFEST)
    self.assertEqual(sig_alone, fresh_vehicle_manifest['signatures'][0])
    self.assertEqual(fresh_vehicle_manifest['signatures'],
        sample_vehicle_manifest['signatures'])
    self.assertTrue(common.verify_signature_over_metadata(
        keys_pub['primary'], fresh_vehicle_manifest['signatures'][0],
        fresh_vehicle_manifest['signed'], DATATYPE_VEHICLE_MANIFEST))

    # ECU Manifest
    sig_alone = common.sign_over_metadata(keys_pri['secondary'],
        fresh_ecu_manifest['signed'], DATATYPE_ECU_MANIFEST)
    common.sign_signable(
        fresh_ecu_manifest, [keys_pri['secondary']], DATATYPE_ECU_MANIFEST)
    self.assertEqual(sig_alone, fresh_ecu_manifest['signatures'][0])
    self.assertEqual(fresh_ecu_manifest['signatures'],
        sample_ecu_manifest['signatures'])
    self.assertTrue(common.verify_signature_over_metadata(
        keys_pub['secondary'], fresh_ecu_manifest['signatures'][0],
        fresh_ecu_manifest['signed'], DATATYPE_ECU_MANIFEST))


    # Try providing metadata types that aren't known to sign_over_metadata.
    with self.assertRaises(uptane.Error):
      common.sign_over_metadata(keys_pri['primary'],
          fresh_vehicle_manifest['signed'], 'nonsense_type')
    with self.assertRaises(uptane.Error):
      common.sign_over_metadata(keys_pri['primary'],
          fresh_vehicle_manifest['signed'], 513)


    # Expect the signatures to come out the same even if a key is specified
    # twice. Try only with ECU Manifests for brevity. (Shouldn't matter)
    common.sign_signable(
        fresh_ecu_manifest2, [keys_pri['secondary'], keys_pri['secondary']],
        DATATYPE_ECU_MANIFEST)
    self.assertEqual(1, len(fresh_ecu_manifest2['signatures']))
    self.assertEqual(fresh_ecu_manifest2['signatures'],
        sample_ecu_manifest['signatures'])
    self.assertTrue(common.verify_signature_over_metadata(
        keys_pub['secondary'], fresh_ecu_manifest2['signatures'][0],
        fresh_ecu_manifest2['signed'], DATATYPE_ECU_MANIFEST))



    # Try signing with two keys.
    common.sign_signable(
        fresh_ecu_manifest3, [keys_pri['secondary'], keys_pri['primary']],
        DATATYPE_ECU_MANIFEST)
    self.assertEqual(2, len(fresh_ecu_manifest3['signatures']))
    sigs = fresh_ecu_manifest3['signatures']
    if sigs[0]['keyid'] == keys_pri['primary']['keyid']:
      self.assertEqual(sigs[1]['keyid'], keys_pri['secondary']['keyid'])
      primary_sig = sigs[0]
      secondary_sig = sigs[1]
    else:
      self.assertEqual(sigs[1]['keyid'], keys_pri['primary']['keyid'])
      self.assertEqual(sigs[0]['keyid'], keys_pri['secondary']['keyid'])
      primary_sig = sigs[1]
      secondary_sig = sigs[0]

    # We can check the secondary key's signature against the pre-existing
    # sample. There is no pre-existing sample for the primary key's signature
    # on an ECU Manifest, but there's already plenty of testing at this point,
    # and we'll verify both signatures live next.
    self.assertEqual(
        sample_ecu_manifest['signatures'][0]['sig'], secondary_sig['sig'])

    self.assertTrue(common.verify_signature_over_metadata(keys_pub['secondary'],
        secondary_sig, sample_ecu_manifest['signed'], DATATYPE_ECU_MANIFEST))
    self.assertTrue(common.verify_signature_over_metadata(keys_pub['primary'],
        primary_sig, sample_ecu_manifest['signed'], DATATYPE_ECU_MANIFEST))



    # Expect a signable to be unchanged if the keys provided already signed the
    # signable. Copy an already-signed piece of metadata, sign it again, and
    # compare it to the original, expecting no change.
    duped_vehicle_manifest = copy.deepcopy(fresh_vehicle_manifest)
    common.sign_signable(duped_vehicle_manifest, [keys_pri['primary']],
        DATATYPE_VEHICLE_MANIFEST)

    self.assertEqual(
        len(fresh_vehicle_manifest['signatures']),
        len(duped_vehicle_manifest['signatures']))
    self.assertEqual(fresh_vehicle_manifest, duped_vehicle_manifest)



    # Add a signature from a different key to an already-signed piece of
    # metadata, expecting to find both old and new signatures, valid in both
    # cases. In particular, this signable already has a signature from key
    # 'secondary' and we'll add a signature from key 'primary'. I figure the
    # second signature (from key 'primary') will be second in the list, but
    # because we don't require that behavior, I won't make that assumption in a
    # test, so I'll proceed as if we don't know the signature order in this
    # test.
    common.sign_signable(fresh_ecu_manifest, [keys_pri['primary']],
        DATATYPE_ECU_MANIFEST)
    self.assertEqual(2, len(fresh_ecu_manifest['signatures']))
    sigs = fresh_ecu_manifest['signatures']
    if sigs[0]['keyid'] == keys_pri['primary']['keyid']:
      self.assertEqual(sigs[1]['keyid'] == keys_pri['secondary']['keyid'])
      primary_sig = sigs[0]
      secondary_sig = sigs[1]
    else:
      self.assertEqual(sigs[1]['keyid'], keys_pri['primary']['keyid'])
      self.assertEqual(sigs[0]['keyid'], keys_pri['secondary']['keyid'])
      primary_sig = sigs[1]
      secondary_sig = sigs[0]

    self.assertEqual(
        sample_ecu_manifest['signatures'][0]['sig'], secondary_sig['sig'])

    self.assertTrue(common.verify_signature_over_metadata(keys_pub['secondary'],
        secondary_sig, sample_ecu_manifest['signed'], DATATYPE_ECU_MANIFEST))
    self.assertTrue(common.verify_signature_over_metadata(keys_pub['primary'],
        primary_sig, sample_ecu_manifest['signed'], DATATYPE_ECU_MANIFEST))

    # Paranoid: duplicates should have the same signed element.
    self.assertEqual(
        sample_ecu_manifest['signed'], fresh_ecu_manifest['signed'])




    # Try signing with a public key instead of a private key, expecting a
    # tuf.FormatError.
    with self.assertRaises(tuf.FormatError):
      common.sign_signable(fresh_time_attestation2, [keys_pub['secondary']],
          DATATYPE_TIME_ATTESTATION)


    # Consider performing this test. (Not likely to be useful.)
    # # Try signing with an unsupported key type.
    # # Cheap way to do this: change the listed type of an existing key.
    # # Another cheap way to do this: change SUPPORTED_KEY_TYPES (but this is
    # # even more artificial, to the point of probably not being useful)).
    # # TODO: Consider constructing an artificial Python dict representation of
    # # a key of a type we don't support. (Not useful?)
    # key_badtype = copy.deepcopy(keys_pri['primary'])
    # key_badtype['keytype'] = 'nonsense_type'
    # with self.assertRaises(uptane.Error):
    #   common.sign_signable(fresh_ecu_manifest4, [key_badtype],
    #       DATATYPE_ECU_MANIFEST)





  def test_verify_signature_over_metadata(self):
    """
    # TODO: Test cases that aren't covered in test_signing() above, for example
    # expected signature mismatches.
    This is also tested in other test modules.
    """
    pass





  def test_canonical_key_funcs(self):
    """
    Tests:
      - public_key_from_canonical()
      - canonical_key_from_pub_and_pri()

    Also tests them against each other.
    """

    # Employ temporary variables for these for readability and shorter lines.
    pubkey = keys_pub['secondary']
    prikey = keys_pri['secondary']

    canonical_key = common.canonical_key_from_pub_and_pri(pubkey, prikey)

    tuf.formats.ANYKEY_SCHEMA.check_match(canonical_key)

    pubkey2 = common.public_key_from_canonical(canonical_key)

    tuf.formats.ANYKEY_SCHEMA.check_match(canonical_key)

    # Break test code if the assumptions we've made for this test to work
    # correctly are broken.
    for field in ['keyid', 'keytype', 'keyval']:
      assert field in pubkey, 'Test code assumption broken.'
      assert field in prikey, 'Test code assumption broken.'
    assert 'private' in prikey['keyval'], 'Test code assumption broken.'
    assert 'public' in pubkey['keyval'], 'Test code assumption broken.'
    assert 'public' in prikey['keyval'], 'Test code assumption broken.'
    assert prikey['keyval']['public'] == pubkey['keyval']['public'], \
        'Test code assumption broken.'
    assert 'keyid_hash_algorithms' in pubkey2, 'Test code assumption broken.'

    for field in ['keyid', 'keytype', 'keyval', 'keyid_hash_algorithms']:
      self.assertIn(field, canonical_key)
      self.assertIn(field, pubkey2)

    for field in ['keyid', 'keytype']:
      self.assertEqual(canonical_key[field], pubkey[field])
      self.assertEqual(canonical_key[field], prikey[field])
      self.assertEqual(canonical_key[field], pubkey2[field])

    for field in ['public', 'private']:
      self.assertIn(field, canonical_key['keyval'])

    self.assertNotIn('private', pubkey2['keyval'])


    self.assertEqual(
        canonical_key['keyval']['private'], prikey['keyval']['private'])
    self.assertEqual(
        canonical_key['keyval']['public'], pubkey['keyval']['public'])
    self.assertEqual(
        pubkey2['keyval']['public'], pubkey['keyval']['public'])





  def test_create_directory_structure_for_client(self):
    """
    Tests common.create_directory_structure_for_client()

    create_directory_structure_for_client() is also tested functionally by
    test_primary and test_secondary.
    """

    if os.path.exists(TEMP_CLIENT_DIR):
      shutil.rmtree(TEMP_CLIENT_DIR)

    assert not os.path.exists(TEMP_CLIENT_DIR), 'Test code is flawed!'

    # Set up a client directory.
    uptane.common.create_directory_structure_for_client(
        TEMP_CLIENT_DIR,
        TEST_PINNING_FNAME,
        {'imagerepo': TEST_IMAGE_REPO_ROOT_FNAME,
        'director': TEST_DIRECTOR_ROOT_FNAME})

    # Ensure that the expected files and directories have been created.
    self.assertTrue(os.path.exists(TEMP_CLIENT_DIR))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'pinned.json')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'director', 'current')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'director', 'current', 'root.' +
        tuf.conf.METADATA_FORMAT)))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'director', 'previous')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'imagerepo', 'current')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'imagerepo', 'current', 'root.' +
        tuf.conf.METADATA_FORMAT)))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'imagerepo', 'previous')))

    # TODO: Consider more unit testing (check other results of the call -
    # perhaps that the contents of pinned.json can be parsed?).



    # Set the same client directory up again to test being able to delete
    # existing directory and start over.
    uptane.common.create_directory_structure_for_client(
        TEMP_CLIENT_DIR,
        TEST_PINNING_FNAME,
        {'imagerepo': TEST_IMAGE_REPO_ROOT_FNAME,
        'director': TEST_DIRECTOR_ROOT_FNAME})

    # Ensure that the expected files and directories continue to exist.
    self.assertTrue(os.path.exists(TEMP_CLIENT_DIR))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'pinned.json')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'director', 'current')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'director', 'current', 'root.' +
        tuf.conf.METADATA_FORMAT)))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'director', 'previous')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'imagerepo', 'current')))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'imagerepo', 'current', 'root.' +
        tuf.conf.METADATA_FORMAT)))
    self.assertTrue(os.path.exists(os.path.join(
        TEMP_CLIENT_DIR, 'metadata', 'imagerepo', 'previous')))





  def test_scrub_filename(self):

    self.assertEqual(os.path.abspath(os.path.join('d', 'f')),
        common.scrub_filename('f', 'd'))
    self.assertEqual(os.path.abspath(os.path.join('/d', 'f')),
        common.scrub_filename('f', '/d'))
    self.assertEqual(os.path.abspath(os.path.join('/d/e', 'f')),
        common.scrub_filename('f', '/d/e'))

    # TODO: Uncomment the following code once scrub_filename rewrite PR is
    # merged that changes the errors raised by scrub_filename.
    # # Test argument format.
    # with self.assertRaises(tuf.FormatError):
    #   common.scrub_filename(2, 1)
    # with self.assertRaises(tuf.FormatError):
    #   common.scrub_filename('a', 1)
    # with self.assertRaises(tuf.FormatError):
    #   common.scrub_filename(2, 'a')
    # # Test for unacceptable characters in the filename.
    # with self.assertRaises(uptane.Error):
    #   common.scrub_filename('b~', 'a')
    # with self.assertRaises(uptane.Error):
    #   common.scrub_filename('/b', 'a')
    # with self.assertRaises(uptane.Error):
    #   common.scrub_filename('$b', 'a')
    # with self.assertRaises(uptane.Error):
    #   common.scrub_filename('\\b', 'a')
    # with self.assertRaises(uptane.Error):
    #   common.scrub_filename('../b', 'a')
    # with self.assertRaises(uptane.Error):
    #   common.scrub_filename('..b', 'a')





# Run unit test.
if __name__ == '__main__':
  unittest.main()
