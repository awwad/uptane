"""
<Program Name>
  test_der_encoder.py

<Purpose>
  Unit testing for DER Encoding, uptane/encoding/asn1_codec.py

"""
from __future__ import print_function
from __future__ import unicode_literals

import uptane # Import before TUF modules; may change tuf.conf values.
import tuf.formats
import tuf.keys
import tuf.repository_tool as repo_tool
import uptane.formats
import uptane.common

import uptane.encoding.asn1_codec as asn1_codec
import uptane.encoding.timeserver_asn1_coder as timeserver_asn1_coder
import uptane.encoding.ecu_manifest_asn1_coder as ecu_manifest_asn1_coder
import uptane.encoding.asn1_definitions as asn1_spec
import pyasn1.codec.der.encoder as p_der_encoder
import pyasn1.codec.der.decoder as p_der_decoder
import pyasn1.error
from pyasn1.type import tag, univ

import sys # to test Python version 2 vs 3, for byte string behavior
import hashlib
import unittest
import os
import time
import copy
import shutil

from uptane.encoding.asn1_codec import DATATYPE_TIME_ATTESTATION
from uptane.encoding.asn1_codec import DATATYPE_ECU_MANIFEST
from uptane.encoding.asn1_codec import DATATYPE_VEHICLE_MANIFEST

# For temporary convenience
import demo # for generate_key, import_public_key, import_private_key

TEST_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'tests', 'test_data')
TEMP_TEST_DIR = os.path.join(TEST_DATA_DIR, 'temp_test_encoding')
test_signing_key = None


def destroy_temp_dir():
  # Clean up anything that may currently exist in the temp test directory.
  if os.path.exists(TEMP_TEST_DIR):
    shutil.rmtree(TEMP_TEST_DIR)





def setUpModule():
  """
  This is run once for the full module, before all tests.
  It prepares some globals, including a single Primary ECU client instance.
  When finished, it will also start up an OEM Repository Server,
  Director Server, and Time Server. Currently, it requires them to be already
  running.
  """
  destroy_temp_dir()

  private_key_fname = os.path.join(
      os.getcwd(), 'demo', 'keys', 'director')

  global test_signing_key
  test_signing_key = repo_tool.import_ed25519_privatekey_from_file(
      private_key_fname, 'pw')




def tearDownModule():
  """This is run once for the full module, after all tests."""
  destroy_temp_dir()





class TestASN1(unittest.TestCase):
  """
  "unittest"-style test class for the Primary module in the reference
  implementation

  Please note that these tests are NOT entirely independent of each other.
  Several of them build on the results of previous tests. This is an unusual
  pattern but saves code and works at least for now.
  """

  def test_ensure_valid_metadata_type_for_asn1(self):
    for metadata_type in asn1_codec.SUPPORTED_ASN1_METADATA_MODULES:
      asn1_codec.ensure_valid_metadata_type_for_asn1(metadata_type)

    with self.assertRaises(uptane.Error):
      asn1_codec.ensure_valid_metadata_type_for_asn1('not_a_metadata_type')





  def test_01_encode_token(self):

    # Test the ASN.1 data definitions in asn1_spec.
    # Begin with a very simple object, which simply encodes an integer.

    # Create ASN.1 object for a token (nonce-like int provided by a Secondary
    # in order to validate recency of the time returned).
    t = asn1_spec.Token(42)

    # Encode as DER
    t_der = p_der_encoder.encode(t)

    # Decode back into ASN1
    # decode() returns a 2-tuple. The first element is the decoded portion.
    # The second element (which should be empty) is any remainder after the
    # decoding.
    (decoded, remainder) = p_der_decoder.decode(
        t_der, asn1_spec.Token())
    self.assertFalse(remainder)
    self.assertEqual(t, decoded)





  def test_02_encode_tokens(self):

    # Continue to test the ASN.1 data definitions in asn1_spec.
    # This will be an array of tokens that each encode an integer.

    tokens = asn1_spec.Tokens()

    # Add a first token to the list.
    t = asn1_spec.Token(42)
    tokens.setComponentByPosition(0, t, False) # TODO: Figure out what the third argument means....

    # tokens should look like:
    #   Tokens(tagSet=TagSet((), Tag(tagClass=128, tagFormat=32, tagId=1))).setComponents(Token(42))

    tokens_der = p_der_encoder.encode(tokens)
    # tokens_der should look like: '\xa1\x03\x02\x01*'

    (tokens_again, remainder) = p_der_decoder.decode(
        tokens_der,
        asn1_spec.Tokens())


    self.assertFalse(remainder)
    self.assertEqual(tokens, tokens_again)





  def test_03_encode_tokensandtimestamp(self):
    """
    Using lower level code (than asn1_codec), test translation of a timeserver
    attestation from standard Uptane Python dictionary format to an ASN.1
    representation, then into a DER encoding, and then back to the original
    form.
    """
    sample_attestation = {
        'nonces': [15856], 'time': '2017-03-01T19:30:45Z'}

    uptane.formats.TIMESERVER_ATTESTATION_SCHEMA.check_match(sample_attestation)

    asn1_attestation = timeserver_asn1_coder.get_asn_signed(sample_attestation)

    der_attestation = p_der_encoder.encode(asn1_attestation)

    self.assertTrue(is_valid_nonempty_der(der_attestation))

    # Decoding requires that we provide an object with typing that precisely
    # matches what we expect to decode. This is such an object.
    exemplar_object = asn1_spec.TokensAndTimestamp()

    (asn1_attestation_again, remainder) = p_der_decoder.decode(
        der_attestation, asn1Spec=exemplar_object)

    self.assertFalse(remainder)
    self.assertEqual(asn1_attestation, asn1_attestation_again)






  def test_04_encode_full_signable_attestation(self):
    """
    Tests the conversion of signable time attestations from Python dictionaries
    to ASN.1/DER objects, and back.

    Similar to test 03 above, except that it encodes the signable dictionary
    (signed and signatures) instead of what is effectively just the 'signed'
    portion.

    Employing the asn1_codec code instead of using
     - the lower level code from pyasn1.der, asn1_spec, and
       timeserver_asn1_coder.
     - using a signable version of the time attestation (encapsulated in
       'signed', with 'signatures')

    This test doesn't re-sign the attestation over the hash of the DER encoding.
    One of the other tests below does that. The signatures here remain over
    the human-readable internal representation of the time attestation.

    """
    # Using str() here because in Python2, I'll get u'' if I don't, and the
    # self.assertEqual(signable_attestation, attestation_again) will fail
    # because they won't both have u' prefixes.
    signable_attestation = {
        str('signatures'): [
        {str('keyid'):
        str('79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'),
        str('sig'):
        str('a5ea6a3b685ad64f96c8c12145beda4efafddfac60bcdb45def35fe43c7d1150a182a1b50a1463bfffb0ef8d30b6203aa8b5365b0b7176312e1e9d7e355e550e'),
        str('method'): str('ed25519')}],
        str('signed'): {str('nonces'): [1],
        str('time'): str('2017-03-08T17:09:56Z')}}
        # str('signed'): {str('nonces'): [834845858], str('time'): str('2017-03-01T19:30:45Z')},
        # str('signatures'): [{str('keyid'): str('12'), str('method'): str('ed25519'), str('sig'): str('123495')}]}
        # u'signed': {u'nonces': [834845858], u'time': u'2017-03-01T19:30:45Z'},
        # u'signatures': [{u'keyid': u'12', u'method': u'ed25519', u'sig': u'12345'}]}

    uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
        signable_attestation)


    # Converts it, without re-signing (default for this method).
    der_attestation = asn1_codec.convert_signed_metadata_to_der(
        signable_attestation, DATATYPE_TIME_ATTESTATION)

    self.assertTrue(is_valid_nonempty_der(der_attestation))

    attestation_again = asn1_codec.convert_signed_der_to_dersigned_json(
        der_attestation, DATATYPE_TIME_ATTESTATION)

    self.assertEqual(attestation_again, signable_attestation)



    # Make sure that convert_signed_metadata_to_der() accepts/rejects
    # parameters appropriately.
    # Pass incoherent value as metadata.
    with self.assertRaises(tuf.FormatError):
      asn1_codec.convert_signed_metadata_to_der(5, DATATYPE_TIME_ATTESTATION)
    # Pass incoherent value as datatype.
    with self.assertRaises(uptane.Error):
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, 'nonsense')
    # Pass inconsistent resign/privatekey/only_signed args
    with self.assertRaises(uptane.Error):
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, DATATYPE_TIME_ATTESTATION, resign=True)
    with self.assertRaises(uptane.Error):
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, DATATYPE_TIME_ATTESTATION,
          private_key=None, resign=True)
    with self.assertRaises(uptane.Error):
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, DATATYPE_TIME_ATTESTATION,
          private_key=test_signing_key, resign=False)
    with self.assertRaises(uptane.Error):
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, DATATYPE_TIME_ATTESTATION,
          private_key=test_signing_key, resign=True, only_signed=True)
    with self.assertRaises(uptane.Error):
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, DATATYPE_TIME_ATTESTATION,
          private_key=test_signing_key, resign=False, only_signed=True)
    with self.assertRaises(uptane.Error):
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, DATATYPE_TIME_ATTESTATION,
          private_key=None, resign=True, only_signed=True)
    with self.assertRaises(uptane.Error): # either that or tuf.FormatError....
      asn1_codec.convert_signed_metadata_to_der(
          signable_attestation, DATATYPE_TIME_ATTESTATION,
          private_key='nonsense', resign=True, only_signed=True)


    # Make sure that uptane.FailedToEncodeASN1DER is raised if nonsense is
    # provided as DER.
    with self.assertRaises(uptane.FailedToDecodeASN1DER):
      asn1_codec.convert_signed_der_to_dersigned_json(
          b'nonsense', DATATYPE_TIME_ATTESTATION)





  def test_05_encode_full_signable_attestation_manual(self):
    """
    Similar to test 04 above, but performs much of the work manually.
    Useful separately only for debugging.

    Instead of just employing asn1_codec, uses lower level code from pyasn1.der,
    asn1_spec, and timeserver_asn1_coder.
    """
    signable_attestation = {
        'signatures': [
        {'keyid': '79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e',
        'sig': 'a5ea6a3b685ad64f96c8c12145beda4efafddfac60bcdb45def35fe43c7d1150a182a1b50a1463bfffb0ef8d30b6203aa8b5365b0b7176312e1e9d7e355e550e',
        'method': 'ed25519'}],
        'signed': {'nonces': [1], 'time': '2017-03-08T17:09:56Z'}}

    uptane.formats.SIGNABLE_TIMESERVER_ATTESTATION_SCHEMA.check_match(
        signable_attestation)

    json_signed = signable_attestation['signed']

    asn_signed = timeserver_asn1_coder.get_asn_signed(json_signed)

    asn_signatures_list = asn1_spec.Signatures()
    i = 0 # Index for iterating through asn signatures
    for pydict_sig in signable_attestation['signatures']:
      asn_sig = asn1_spec.Signature()
      asn_sig['keyid'] = asn1_spec.Keyid(hexValue=pydict_sig['keyid'])
      asn_sig['method'] = int(asn1_spec.SignatureMethod(
          pydict_sig['method']))
      asn_sig['value'] = asn1_spec.OctetString(hexValue=pydict_sig['sig'])
      asn_signatures_list[i] = asn_sig # has no append method
      i += 1

    asn_signable = asn1_spec.TokensAndTimestampSignable()#.subtype(implicitTag=tag.Tag(
        #tag.tagClassContext, tag.tagFormatConstructed, 3))
    asn_signable['signed'] = asn_signed #considering using der_signed instead - requires changes
    asn_signable['signatures'] = asn_signatures_list # TODO: Support multiple sigs, or integrate with TUF.
    asn_signable['numberOfSignatures'] = len(asn_signatures_list)


    der_attestation = p_der_encoder.encode(asn_signable)

    self.assertTrue(is_valid_nonempty_der(der_attestation))

    # Decoding requires that we provide an object with typing that precisely
    # matches what we expect to decode. This is such an object.
    exemplar_object = asn1_spec.TokensAndTimestampSignable()#.subtype(implicitTag=tag.Tag(
        #tag.tagClassContext, tag.tagFormatConstructed, 3))

    (asn1_attestation_again, remainder) = p_der_decoder.decode(
        der_attestation, asn1Spec=exemplar_object)

    self.assertFalse(remainder)
    self.assertEqual(asn1_attestation_again, asn_signable)

    # TODO: Test rest of the way back: ASN1 to Python dictionary.
    # (This is in addition to the next test, which does that with the higher
    # level code in asn1_codec.)


    # No, for some reason, pyasn1 raises a KeyError....
    # # Try again with nonsense to ensure that a PyAsn1Error is raised.
    # # with self.assertRaises(pyasn1.error.PyAsn1Error):
    # #   asn_signable['numberOfSignatures'] = 'a'

    # Not sure how to get convert_signed_metadata_to_der to raise
    # pyasn1.error.PyAsn1Error, since I don't think we can get that far into
    # the function with a value that wouldn't encode: we'd have to be following
    # the spec already to convert to a pyasn1 ASN.1 dictionary. We could change
    # the definitions midway somehow, maybe? That'll be a one-line coverage gap
    # until I can figure it out.
    # with self.assertRaises(uptane.FailedToEncodeASN1DER):
    #   der_attestation = p_der_encoder.encode(5)





  def test_06_encode_and_validate_resigned_time_attestation(self):
    """
    Test timeserver attestation encoding and decoding, with signing over DER
    ('re-sign' functionality in asn1_codec) and signature validation.
    """

    signable_attestation = {
        str('signatures'): [
        {str('keyid'):
        str('79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'),
        str('sig'):
        str('a5ea6a3b685ad64f96c8c12145beda4efafddfac60bcdb45def35fe43c7d1150a182a1b50a1463bfffb0ef8d30b6203aa8b5365b0b7176312e1e9d7e355e550e'),
        str('method'): str('ed25519')}],
        str('signed'): {str('nonces'): [1],
        str('time'): str('2017-03-08T17:09:56Z')}}

    # Load the timeserver's private key to sign a time attestation, and public
    # key to verify that signature.
    timeserver_key = demo.import_private_key('timeserver')
    timeserver_key_pub = demo.import_public_key('timeserver')
    tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_key)
    tuf.formats.ANYKEY_SCHEMA.check_match(timeserver_key_pub)


    # First, calculate what we'll be verifying at the end of this test.
    # The re-signing in the previous line produces a signature over the SHA256
    # hash of the DER encoding of the ASN.1 format of the 'signed' portion of
    # signable_attestation. We produce it here so that we can check it against
    # the result of encoding, resigning, and decoding.
    der_signed = asn1_codec.convert_signed_metadata_to_der(
        signable_attestation, DATATYPE_TIME_ATTESTATION, only_signed=True)
    der_signed_hash = hashlib.sha256(der_signed).digest()


    # Now perform the actual conversion to ASN.1/DER of the full
    # signable_attestation, replacing the signature (which was given as
    # signatures over the Python 'signed' dictionary) with a signature over
    # the hash of the DER encoding of the 'signed' ASN.1 data.
    # This is the final product to be distributed back to a Primary client.
    der_attestation = asn1_codec.convert_signed_metadata_to_der(
        signable_attestation, DATATYPE_TIME_ATTESTATION,
        private_key=timeserver_key, resign=True)


    # Now, in order to test the final product, decode it back from DER into
    # pyasn1 ASN.1, and convert back into Uptane's standard Python dictionary
    # form.
    pydict_again = asn1_codec.convert_signed_der_to_dersigned_json(
        der_attestation, DATATYPE_TIME_ATTESTATION)

    # Check the extracted signature against the hash we produced earlier.
    self.assertTrue(tuf.keys.verify_signature(
        timeserver_key_pub,
        pydict_again['signatures'][0],
        der_signed_hash))





  def test_07_encode_and_validate_resigned_time_attestation_again(self):
    """
    This is a redundant test, repeating much of test 06 above with a slightly
    different method.
    """
    signable_attestation = {
        str('signatures'): [
        {str('keyid'):
        str('79c796d7e87389d1ebad04edce49faef611d139ee41ea9fb1931732afbfaac2e'),
        str('sig'):
        str('a5ea6a3b685ad64f96c8c12145beda4efafddfac60bcdb45def35fe43c7d1150a182a1b50a1463bfffb0ef8d30b6203aa8b5365b0b7176312e1e9d7e355e550e'),
        str('method'): str('ed25519')}],
        str('signed'): {str('nonces'): [1],
        str('time'): str('2017-03-08T17:09:56Z')}}
    conversion_tester(
        signable_attestation, DATATYPE_TIME_ATTESTATION, self)







  def test_10_ecu_manifest_asn1_conversion(self):

    # First try the low-level asn1 conversion.
    asn_signed = ecu_manifest_asn1_coder.get_asn_signed(
        SAMPLE_ECU_MANIFEST_SIGNABLE['signed'])#ecu_manifest_signed_component)

    # Convert back to a basic Python dictionary.
    json_signed = ecu_manifest_asn1_coder.get_json_signed({'signed': asn_signed})

    # Make sure that the result of conversion to ASN.1 and back is the same
    # as the original.
    self.assertEqual(json_signed, SAMPLE_ECU_MANIFEST_SIGNABLE['signed'])





  def test_11_ecu_manifest_der_conversion(self):

    conversion_tester(
        SAMPLE_ECU_MANIFEST_SIGNABLE, DATATYPE_ECU_MANIFEST, self)


    # Redundant tests. The above call should cover all of the following tests.
    der_ecu_manifest = asn1_codec.convert_signed_metadata_to_der(
        SAMPLE_ECU_MANIFEST_SIGNABLE, DATATYPE_ECU_MANIFEST, only_signed=True)

    der_ecu_manifest = asn1_codec.convert_signed_metadata_to_der(
        SAMPLE_ECU_MANIFEST_SIGNABLE, DATATYPE_ECU_MANIFEST)

    pydict_ecu_manifest = asn1_codec.convert_signed_der_to_dersigned_json(
        der_ecu_manifest, DATATYPE_ECU_MANIFEST)

    self.assertEqual(
        pydict_ecu_manifest, SAMPLE_ECU_MANIFEST_SIGNABLE)





  def test_20_vehicle_manifest_der_conversion(self):
    uptane.formats.SIGNABLE_VEHICLE_VERSION_MANIFEST_SCHEMA.check_match(
        SAMPLE_VEHICLE_MANIFEST_SIGNABLE)
    conversion_tester(
        SAMPLE_VEHICLE_MANIFEST_SIGNABLE, DATATYPE_VEHICLE_MANIFEST, self)






def conversion_tester(signable_pydict, datatype, cls): # cls: clunky
  """
  Tests each of the different kinds of conversions into ASN.1/DER, and tests
  converting back. In one type of conversion, compares to make sure the data
  has not changed.

  This function takes as a third parameter the unittest.TestCase object whose
  functions (assertTrue etc) it can use. This is awkward and inappropriate. :P
  Find a different means of providing modularity instead of this one.
  (Can't just have this method in the class above because it would be run as
  a test. Could have default parameters and do that, but that's clunky, too.)
  Does unittest allow/test private functions in UnitTest classes?
  """


  # Test type 1: only-signed
  # Convert and return only the 'signed' portion, the metadata payload itself,
  # without including any signatures.
  signed_der = asn1_codec.convert_signed_metadata_to_der(
      signable_pydict, datatype, only_signed=True)

  cls.assertTrue(is_valid_nonempty_der(signed_der))

  # TODO: Add function to asn1_codec that will convert signed-only DER back to
  # Python dictionary. Might be useful, and is useful for testing only_signed
  # in any case.


  # Test type 2: full conversion
  # Convert the full signable ('signed' and 'signatures'), maintaining the
  # existing signature in a new format and encoding.
  signable_der = asn1_codec.convert_signed_metadata_to_der(
      signable_pydict, datatype)
  cls.assertTrue(is_valid_nonempty_der(signable_der))

  # Convert it back.
  signable_reverted = asn1_codec.convert_signed_der_to_dersigned_json(
      signable_der, datatype)

  # Ensure the original is equal to what is converted back.
  cls.assertEqual(signable_pydict, signable_reverted)



  # Test type 3: full conversion with re-signing
  # Convert the full signable ('signed' and 'signatures'), but discarding the
  # original signatures and re-signing over, instead, the hash of the converted,
  # ASN.1/DER 'signed' element.
  resigned_der = asn1_codec.convert_signed_metadata_to_der(
      signable_pydict, datatype, resign=True, private_key=test_signing_key)
  cls.assertTrue(is_valid_nonempty_der(resigned_der))

  # Convert the re-signed DER manifest back in order to split it up.
  resigned_reverted = asn1_codec.convert_signed_der_to_dersigned_json(
      resigned_der, datatype)
  resigned_signature = resigned_reverted['signatures'][0]

  # Check the signature on the re-signed DER manifest:
  cls.assertTrue(uptane.common.verify_signature_over_metadata(
      test_signing_key,
      resigned_signature,
      resigned_reverted['signed'],
      datatype,
      metadata_format='der'))

  # The signatures will not match, because a new signature was made, but the
  # 'signed' elements should match when converted back.
  cls.assertEqual(
      signable_pydict['signed'], resigned_reverted['signed'])





def is_valid_nonempty_der(der_string):
  """
  Currently a hacky test to see if the result is a non-empty byte string.

  This CAN raise false failures, stochastically, in Python2. In Python2,
  where bytes and str are the same type, we check to see if, anywhere in the
  string, there is a character requiring a \\x escape, as would almost
  certainly happen in an adequately long DER string of bytes. As a result,
  short or very regular strings may raise false failures in Python2.

  The best way to really do this test is to decode the DER and see if
  believable ASN.1 has come out of it.
  """
  if not der_string:
    return False
  elif sys.version_info.major < 3:
    return '\\x' in repr(der_string)
  else:
    return isinstance(der_string, bytes)





SAMPLE_ECU_MANIFEST_SIGNABLE = {
  'signed': {
    'timeserver_time': '2017-03-27T16:19:17Z',
    'previous_timeserver_time': '2017-03-27T16:19:17Z',
    'ecu_serial': '22222',
    'attacks_detected': '',
    'installed_image': {
      'filepath': '/secondary_firmware.txt',
      'fileinfo': {
        'length': 37,
        'hashes': {
          'sha256': '6b9f987226610bfed08b824c93bf8b2f59521fce9a2adef80c495f363c1c9c44',
          'sha512': '706c283972c5ae69864b199e1cdd9b4b8babc14f5a454d0fd4d3b35396a04ca0b40af731671b74020a738b5108a78deb032332c36d6ae9f31fae2f8a70f7e1ce'}}}},
  'signatures': [{
    'sig': '42e6f4b398dbad0404cca847786a926972b54ca2ae71c7334f3d87fc62a10d08e01f7b5aa481cd3add61ef36f2037a9f68beca9f6ea26d2f9edc6f4ba0ba2a06',
    'method': 'ed25519',
    'keyid': '49309f114b857e4b29bfbff1c1c75df59f154fbc45539b2eb30c8a867843b2cb'}]}



SAMPLE_VEHICLE_MANIFEST_SIGNABLE = {
  'signed': {
    'primary_ecu_serial': '11111',
    'vin': '111',
    'ecu_version_manifests': {
      '22222': [{
          'signed': {
            'previous_timeserver_time': '2017-03-31T15:48:31Z',
            'timeserver_time': '2017-03-31T15:48:31Z',
            'ecu_serial': '22222',
            'attacks_detected': '',
            'installed_image': {
              'filepath': '/secondary_firmware.txt',
              'fileinfo': {
                'length': 37,
                'hashes': {
                  'sha256': '6b9f987226610bfed08b824c93bf8b2f59521fce9a2adef80c495f363c1c9c44',
                  'sha512': '706c283972c5ae69864b199e1cdd9b4b8babc14f5a454d0fd4d3b35396a04ca0b40af731671b74020a738b5108a78deb032332c36d6ae9f31fae2f8a70f7e1ce'}}}},
          'signatures': [{
              'keyid': '49309f114b857e4b29bfbff1c1c75df59f154fbc45539b2eb30c8a867843b2cb',
              'sig': '40069be1dd6f3fc091300307d61bc1646683a3ab8ebefac855bec0082c6fa067136800b744a2276564d9216cfcaafdea3976fc7f2128d2454d8d46bac79ebe05',
              'method': 'ed25519'}]}]}},
  'signatures': [{
      'keyid': '9a406d99e362e7c93e7acfe1e4d6585221315be817f350c026bbee84ada260da',
      'sig': '222e3fe0f3aa4fd14e163ec68f61954a9f4714d6d91d7114190e0a19a5ecc1cc43d9684e99dd8082c519815a01dd2e55a7a63d1467612cfb360937178586530c',
      'method': 'ed25519'}]}





# Run unit tests.
if __name__ == '__main__':
  unittest.main()
