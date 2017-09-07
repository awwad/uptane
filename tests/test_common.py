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
import copy
import json

import tuf
import tuf.formats
import tuf.conf

import uptane.common as common
import uptane.encoding.asn1_codec as asn1_codec

import demo # for generate_key, import_public_key, import_private_key

# The public and private keys to use during testing, including the Director
# repository keys (public and private) as well as client keys (public).
keys_pri = {}
keys_pub = {}

SAMPLES_DIR = os.path.join(uptane.WORKING_DIR, 'samples')



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





  def test_sign_signable(self):
    """"""
    pass





  def test_sign_over_metadata(self):
    """"""
    pass





  def test_verify_signature_over_metadata(self):
    """"""
    pass





  def test_canonical_key_funcs(self):
    """"""
    # This is also tested by test_primary and test_secondary.

    # Temps for line length:
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
    """"""
    # This is tested by test_primary and test_secondary.
    # TODO: Test more thoroughly later.
    pass





# Run unit test.
if __name__ == '__main__':
  unittest.main()
