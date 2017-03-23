"""
<Program Name>
  test_der_encoder.py

<Purpose>
  Unit testing for DER Encoding, uptane/encoding/asn1_codec.py

"""
from __future__ import print_function
from __future__ import unicode_literals

import tuf.formats
import tuf.keys
import uptane
import uptane.formats

import uptane.encoding.asn1_codec as asn1_codec
import uptane.encoding.timeserver_asn1_coder as timeserver_asn1_coder
import uptane.encoding.asn1_definitions as asn1_spec
import pyasn1.codec.der.encoder as p_der_encoder
import pyasn1.codec.der.decoder as p_der_decoder
from pyasn1.type import tag, univ

import sys # to test Python version 2 vs 3, for byte string behavior
import hashlib
import unittest
import os.path
import time
import copy
import shutil

# For temporary convenience
import demo # for generate_key, import_public_key, import_private_key

TEST_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'tests', 'test_data')
TEMP_TEST_DIR = os.path.join(TEST_DATA_DIR, 'temp_test_encoding')



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
  global primary_ecu_key

  destroy_temp_dir()





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
    self.assertFalse(remainder) # '' != b''; thus for Python3, don't test it
    self.assertEqual(t, decoded)





  def test_02_encode_tokens(self):

    # Continue to test the ASN.1 data definitions in asn1_spec.
    # This will be an array of tokens that each encode an integer.

    # We create a Tokens object with the subtype definition required by the
    # classes that contain Tokens objects.
    tokens = asn1_spec.Tokens().subtype(
        implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))

    # Add a first token to the list.
    t = asn1_spec.Token(42)
    tokens.setComponentByPosition(0, t, False) # TODO: Figure out what the third argument means....

    # tokens should look like:
    #   Tokens(tagSet=TagSet((), Tag(tagClass=128, tagFormat=32, tagId=1))).setComponents(Token(42))

    tokens_der = p_der_encoder.encode(tokens)
    # tokens_der should look like: '\xa1\x03\x02\x01*'

    (tokens_again, remainder) = p_der_decoder.decode(
        tokens_der,
        asn1_spec.Tokens().subtype(implicitTag=tag.Tag(
        tag.tagClassContext, tag.tagFormatSimple, 1)))


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
    exemplar_object = asn1_spec.TokensAndTimestamp().subtype(
        implicitTag=tag.Tag(tag.tagClassContext,
        tag.tagFormatConstructed,
        0))

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
        signable_attestation)

    self.assertTrue(is_valid_nonempty_der(der_attestation))

    attestation_again = asn1_codec.convert_signed_der_to_dersigned_json(
        der_attestation)

    self.assertEqual(attestation_again, signable_attestation)





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

    asn_signatures_list = asn1_spec.Signatures().subtype(
        implicitTag=tag.Tag(tag.tagClassContext,
        tag.tagFormatSimple, 2))
    i = 0 # Index for iterating through asn signatures
    for pydict_sig in signable_attestation['signatures']:
      asn_sig = asn1_spec.Signature()
      asn_sig['keyid'] = asn1_spec.Keyid().subtype(
          explicitTag=tag.Tag(tag.tagClassContext,
          tag.tagFormatConstructed, 0))
      asn_sig['keyid']['octetString'] = univ.OctetString(
          hexValue=pydict_sig['keyid']).subtype(implicitTag=tag.Tag(
          tag.tagClassContext, tag.tagFormatSimple, 1))
      asn_sig['method'] = int(asn1_spec.SignatureMethod(
          pydict_sig['method']))
      asn_sig['value'] = asn1_spec.BinaryData().subtype(
          explicitTag=tag.Tag(tag.tagClassContext,
          tag.tagFormatConstructed, 2))
      asn_sig['value']['octetString'] = univ.OctetString(
          hexValue=pydict_sig['sig']).subtype(implicitTag=tag.Tag(
          tag.tagClassContext, tag.tagFormatSimple, 1))
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
        signable_attestation, only_signed=True)
    der_signed_hash = hashlib.sha256(der_signed).hexdigest()


    # Now perform the actual conversion to ASN.1/DER of the full
    # signable_attestation, replacing the signature (which was given as
    # signatures over the Python 'signed' dictionary) with a signature over
    # the hash of the DER encoding of the 'signed' ASN.1 data.
    # This is the final product to be distributed back to a Primary client.
    der_attestation = asn1_codec.convert_signed_metadata_to_der(
        signable_attestation, private_key=timeserver_key, resign=True)


    # Now, in order to test the final product, decode it back from DER into
    # pyasn1 ASN.1, and convert back into Uptane's standard Python dictionary
    # form.
    pydict_again = asn1_codec.convert_signed_der_to_dersigned_json(
        der_attestation)

    # Check the extracted signature against the hash we produced earlier.
    self.assertTrue(tuf.keys.verify_signature(
        timeserver_key_pub, pydict_again['signatures'][0],
        der_signed_hash))





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
    if '\\x' not in repr(der_string): # TODO: <~> TEMPORARY FOR DEBUG. DELETE
      print(repr(der_string)) # TODO: <~> TEMPORARY FOR DEBUG. DELETE
    return '\\x' in repr(der_string)
  else:
    return isinstance(der_string, bytes)





# Run unit tests.
if __name__ == '__main__':
  unittest.main()
