"""
<Program Name>
  reencode_samples.py

<Purpose>
  This module is a development aide and not a part of the Uptane
  implementation. It reproduces samples and test data in the event of a change
  to the ASN.1 specifications. This includes only Uptane-specific client data:
  Time Attestations, ECU Manifests, and Vehicle Manifests.

  In the event that the ASN.1 definitions change but the JSON definitions do
  not, the ASN.1 samples have to be re-generated. The functions here will do
  that. Given an sample filename for the JSON sample, they'll write a

  Note that there is not currently a tool here to compile changed .asn1 files
  into a new asn1_definitions.py module (using asn1ate and pyasn1). The
  instructions for that are in asn1_definitions.py itself and currently in
  progress.

  Functions:
    derify_sample_vehicle_manifest
    derify_sample_ecu_manifest
    derify_sample_time_attestation

    reproduce_all_der_samples <- runs the above on known samples / test data


  Further instructions exist to regenerate sample repository metadata
  (role metadata - timestamp, snapshot, root, targets, and delegated targets
  roles for a sample Director Repository and Image Repository).

"""
import uptane
import uptane.encoding.asn1_codec as asn1_codec
import uptane.common as common
import demo # for easy loading of demo keys
import json
import os.path

SAMPLE_DATA_DIR = os.path.join(uptane.WORKING_DIR, 'samples')
FLAWED_MANIFEST_DIR = os.path.join(
    uptane.WORKING_DIR, 'tests', 'test_data', 'flawed_manifests')


def derify_sample_vehicle_manifest(json_fname, ecu_key, vehicle_key):

  # Read the named JSON file.
  with open(json_fname) as fobj:
    json_data = json.load(fobj)

  # Check assumptions:
  #  - only one signature on the Vehicle Manifest (itself)
  #  - the existing signature on the Vehicle Manifest is by the same key as the
  #    one provided for re-signing
  assert len(json_data['signatures']) == 1, 'Sample conversion not written ' \
      'to handle more than one signature on the Vehicle Manifest itself.'
  if json_data['signatures'][0]['keyid'] != vehicle_key['keyid']:
    print('Existing metadata signed by keyid ' + json_data['signatures'][0]
        ['keyid'] + '; provided key has keyid ' + key['keyid'])
    raise Exception('Wrong key! Not re-signing the Vehicle Manifest.')

  # Minor debugging info.
  n_ecus = len(json_data['signed']['ecu_version_manifests'])
  n_manifests = sum([len(json_data['signed']['ecu_version_manifests'][vin])
      for vin in json_data['signed']['ecu_version_manifests']])
  print('vm ' + json_fname + ' has ' + str(n_ecus) + ' ECUs with a total of ' +
      str(n_manifests) + ' manifests.')

  # Re-sign (in memory, in place) every individual ECU Manifest with the given
  # key. Error out if any existing signature is ostensibly using a different
  # key than the given key.
  for ecu in json_data['signed']['ecu_version_manifests']:
    for em in json_data['signed']['ecu_version_manifests'][ecu]:
      for i in range(0, len(em['signatures'])):
        print('Re-signing manifest #' + str(i) + ' for ecu ' + ecu)
        keyid_used_in_json = em['signatures'][i]['keyid']
        if ecu_key['keyid'] != keyid_used_in_json:
          print('Existing ECU Manifest signed by keyid ' + em['signatures'][i]
              ['keyid'] + '; provided key has keyid ' + ecu_key['keyid'])
          raise Exception('Wrong key! Not re-signing the ECU Manifest.')
        em['signatures'][i] = common.sign_over_metadata(
            ecu_key, em['signed'], 'ecu_manifest', metadata_format='der')

  # Convert the full Vehicle Manifest (which now has all the ECU Manifests
  # in it re-signed) and re-sign the Vehicle Manifest.
  der_data = asn1_codec.convert_signed_metadata_to_der(
      json_data, vehicle_key, True, False, 'vehicle_manifest')

  # Write the new DER sample file.
  der_fname = json_fname[:-4] + 'der'
  with open(der_fname, 'wb') as fobj:
    fobj.write(der_data)





def derify_sample_ecu_manifest(json_fname, key):

  # Read the named JSON file.
  with open(json_fname) as fobj:
    json_data = json.load(fobj)

  # Check assumptions:
  #  - only one signature on the ECU Manifest
  #  - the existing signature on the ECU Manifest is by the same key as the
  #    one provided for re-signing
  assert len(json_data['signatures']) == 1, 'Sample conversion not written ' \
      'to handle more than one signature on a sample ECU Manifest.'
  if json_data['signatures'][0]['keyid'] != key['keyid']:
    print('Existing metadata signed by keyid ' + json_data['signatures'][0]
        ['keyid'] + '; provided key has keyid ' + key['keyid'])
    raise Exception('Wrong key! Not re-signing the ECU Manifest.')

  # Re-sign (in memory) the ECU Manifest using the given key.
  # Error out if any existing signature is ostensibly using a different key
  # than the given key.
  der_data = asn1_codec.convert_signed_metadata_to_der(
      json_data, key, True, False, 'ecu_manifest')

  # Write the new DER sample file.
  der_fname = json_fname[:-4] + 'der'
  with open(der_fname, 'wb') as fobj:
    fobj.write(der_data)





def derify_sample_time_attestation(json_fname, key):

  # Read the named JSON file.
  with open(json_fname) as fobj:
    json_data = json.load(fobj)

  # Check assumptions:
  #  - only one signature on the Time Attestation
  #  - the existing signature on the Time Attestation is by the same key as the
  #    one provided for re-signing
  assert len(json_data['signatures']) == 1, 'Sample conversion not written ' \
      'to handle more than one signature on a sample Time Attestation.'
  if json_data['signatures'][0]['keyid'] != key['keyid']:
    print('Existing metadata signed by keyid ' + json_data['signatures'][0]
        ['keyid'] + '; provided key has keyid ' + key['keyid'])
    raise Exception('Wrong key! Not re-signing the Time Attestation.')

  # Re-sign (in memory) the Time Attestation using the given key.
  # Error out if any existing signature is ostensibly using a different key
  # than the given key.
  der_data = asn1_codec.convert_signed_metadata_to_der(
      json_data, key, True, False, 'time_attestation')


  # Write the new DER sample file.
  der_fname = json_fname[:-4] + 'der'
  with open(der_fname, 'wb') as fobj:
    fobj.write(der_data)





def reproduce_all_der_samples():

  pkey = demo.import_private_key('primary')
  skey = demo.import_private_key('secondary')
  skey2 = demo.import_private_key('maintimestamp')
  tkey = demo.import_private_key('timeserver')


  # Convert Timeserver Attestation sample
  derify_sample_time_attestation(
      '/Users/s/w/uptane/samples/sample_timeserver_attestation.json', tkey)


  # Convert ECU Manifest samples and test data
  samples_using_normal_key = [
      os.path.join(SAMPLE_DATA_DIR, 'sample_ecu_manifest.json'),
      os.path.join(SAMPLE_DATA_DIR, 'sample_ecu_manifest_TCUdemocar.json'),
      os.path.join(SAMPLE_DATA_DIR, 'sample_ecu_manifest_ecu11111.json'),
      os.path.join(FLAWED_MANIFEST_DIR, 'em2_unknown_ecu_manifest.json'),
      os.path.join(FLAWED_MANIFEST_DIR, 'em4_attack_detected_in_ecu_manifest.json')]

  samples_using_wrong_key = [
      os.path.join(FLAWED_MANIFEST_DIR, 'em3_ecu_manifest_signed_with_wrong_key.json')]

  for manifest in samples_using_normal_key:
    derify_sample_ecu_manifest(manifest, skey)

  for manifest in samples_using_wrong_key:
    derify_sample_ecu_manifest(manifest, skey2)


  # Convert Vehicle Manifest samples and test data

  samples_using_normal_key = [
      os.path.join(SAMPLE_DATA_DIR, 'sample_vehicle_manifest.json'),
      os.path.join(SAMPLE_DATA_DIR, 'sample_vehicle_version_manifest_democar.json'),
      os.path.join(FLAWED_MANIFEST_DIR, 'vm1_three_ecus_one_unknown.json'),
      os.path.join(FLAWED_MANIFEST_DIR, 'vm2_contains_one_unknown_ecu_manifest.json'),
      os.path.join(FLAWED_MANIFEST_DIR, 'vm4_attack_detected_in_ecu_manifest.json')]

  samples_using_wrong_key = [
      os.path.join(FLAWED_MANIFEST_DIR, 'vm3_ecu_manifest_signed_with_wrong_key.json')]

  for manifest in samples_using_normal_key:
    derify_sample_vehicle_manifest(manifest, skey, pkey)

  for manifest in samples_using_wrong_key:
    derify_sample_vehicle_manifest(manifest, skey2, pkey)

