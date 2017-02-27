#!/usr/bin/env python

"""
<Author>
  Trishank Karthik Kuppusamy
"""

from pyasn1.type import univ, char, namedtype, namedval, tag, constraint, useful

from uptane.encoding.metadataverificationmodule import *

import uptane.encoding.metadata as metadata


def get_asn_signed(json_signed):
  asn_signed = TimestampMetadata()\
                      .subtype(implicitTag=tag.Tag(tag.tagClassContext,
                                                   tag.tagFormatConstructed, 3))
  if len(json_signed['meta']) != 1:
    raise tuf.Error('Expecting only one file to be identified in timestamp '
        'metadata: snapshot. Contents of timestamp metadata: ' +
        repr(json_signed['meta']))

  # Get the only key in the dictionary, the filename of the file timestamp
  # contains a hash for (snapshot.*).
  filename = list(json_signed['meta'])[0]

  fileinfo = json_signed['meta'][filename]
  asn_signed['filename'] = filename
  asn_signed['version'] = fileinfo['version']
  asn_signed['length'] = fileinfo['length']
  asn_signed['numberOfHashes'] = len(fileinfo['hashes']) # TODO: <~> Ascertain this rather than assuming.
  asn_hashes = Hashes().subtype(
      implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4))

  i = 0 # counter for hashes, as Hashes() object must be indexed (no append)
  for hashtype in fileinfo['hashes']:
    asn_hash = Hash()
    asn_hash['function'] = int(HashFunction(hashtype))
    digest = BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext,
                                                    tag.tagFormatConstructed,
                                                    1))
    digest['hexString'] = fileinfo['hashes'][hashtype]
    asn_hash['digest'] = digest
    asn_hashes[i] = asn_hash
    i += 1

  asn_signed['hashes'] = asn_hashes

  signedBody = SignedBody()\
               .subtype(explicitTag=tag.Tag(tag.tagClassContext,
                                            tag.tagFormatConstructed, 3))
  signedBody['timestampMetadata'] = asn_signed

  signed = Signed().subtype(implicitTag=tag.Tag(tag.tagClassContext,
                                                tag.tagFormatConstructed, 0))
  signed['type'] = int(RoleType('timestamp'))
  signed['expires'] = metadata.iso8601_to_epoch(json_signed['expires'])
  signed['version'] = json_signed['version']
  signed['body'] = signedBody

  return signed


def get_json_signed(asn_metadata):
  json_signed = {
    '_type': 'Timestamp'
  }

  asn_signed = asn_metadata['signed']
  json_signed['expires'] = metadata.epoch_to_iso8601(asn_signed['expires'])
  json_signed['version'] = int(asn_signed['version'])

  timestampMetadata = asn_signed['body']['timestampMetadata']
  json_signed['meta'] = {
    filename : {
      'hashes': {
        'sha256': str(timestampMetadata['hashes'][0]['digest']['hexString'])
      },
      'length': int(timestampMetadata['length']),
      'version': int(timestampMetadata['version'])
    }
  }

  return json_signed


if __name__ == '__main__':
  metadata.test('timestamp.json', 'timestamp.ber', get_asn_signed,
                get_json_signed, metadata.identity_update_json_signature,
                Metadata)
