#!/usr/bin/env python

from __future__ import print_function
from __future__ import unicode_literals
from io import open

from pyasn1.type import univ, char, namedtype, namedval, tag, constraint, useful

from pyasn1.codec.cer import encoder, decoder

from metadataverificationmodule import BinaryData,      \
                                       Hash,            \
                                       HashFunction,    \
                                       Keyid,           \
                                       Keyids,          \
                                       Metadata,        \
                                       PublicKey,       \
                                       PublicKeyType,   \
                                       PublicKeys,      \
                                       RoleType,        \
                                       RootMetadata,    \
                                       Signed,          \
                                       SignedBody,      \
                                       Signature,       \
                                       SignatureMethod, \
                                       Signatures,      \
                                       TopLevelRole,    \
                                       TopLevelRoles

import hashlib

metadata = Metadata()

signed = Signed().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))
signed['type'] = int(RoleType('root'))
signed['expires'] = "2017-10-08T01:44:22Z"
signed['version'] = 1

rootMetadata = RootMetadata().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))

keys = PublicKeys().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))

rootPublicKey = PublicKey()
rootPublicKey['publicKeyid'] = '94c836f0c45168f0a437eef0e487b910f58db4d462ae457b5730a4487130f290'
rootPublicKey['publicKeyType'] = int(PublicKeyType('ed25519'))
rootPublicKeyValue = BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2))
rootPublicKeyValue['hexString'] = 'f4ac8d95cfdf65a4ccaee072ba5a48e8ad6a0c30be6ffd525aec6bc078211033'
rootPublicKey['publicKeyValue'] = rootPublicKeyValue
keys[0] = rootPublicKey

timestampPublicKey = PublicKey()
timestampPublicKey['publicKeyid'] = '6fcd9a928358ad8ca7e946325f57ec71d50cb5977a8d02c5ab0de6765fef040a'
timestampPublicKeyValue = BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2))
timestampPublicKey['publicKeyType'] = int(PublicKeyType('ed25519'))
timestampPublicKeyValue['hexString'] = '97c1112bbd9047b1fdb50dd638bfed6d0639e0dff2c1443f5593fea40e30f654'
timestampPublicKey['publicKeyValue'] = timestampPublicKeyValue
keys[1] = timestampPublicKey

snapshotPublicKey = PublicKey()
snapshotPublicKey['publicKeyid'] = 'aaf05f8d054f8068bf6cb46beed7c824e2560802df462fc8681677586582ca99'
snapshotPublicKey['publicKeyType'] = int(PublicKeyType('ed25519'))
snapshotPublicKeyValue = BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2))
snapshotPublicKeyValue['hexString'] = '497f62d80e5b892718da8788bb549bcf8369a1460ec23d6d67d0ca099a8e8f83'
snapshotPublicKey['publicKeyValue'] = snapshotPublicKeyValue
keys[2] = snapshotPublicKey

targetsPublicKey = PublicKey()
targetsPublicKey['publicKeyid'] = 'c24b457b2ca4b3c2f415efdbbebb914a0d05c5345b9889bda044362589d6f596'
targetsPublicKey['publicKeyType'] = int(PublicKeyType('ed25519'))
targetsPublicKeyValue = BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2))
targetsPublicKeyValue['hexString'] = '729d9cb5f74688ef8e9a22fae1516f33ff98c7910b64bf3b66e6cfc51559840e'
targetsPublicKey['publicKeyValue'] = targetsPublicKeyValue
keys[3] = targetsPublicKey

rootMetadata['keys'] = keys

roles = TopLevelRoles().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1))

rootRole = TopLevelRole()
rootRole['role'] = int(RoleType('root'))
rootRole['url'] = 'http://example.com/root.json'
rootRoleKeyids = Keyids().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))
rootRoleKeyid = Keyid('94c836f0c45168f0a437eef0e487b910f58db4d462ae457b5730a4487130f290')
rootRoleKeyids[0] = rootRoleKeyid
rootRole['keyids'] = rootRoleKeyids
rootRole['threshold'] = 1
roles[0] = rootRole

snapshotRole = TopLevelRole()
snapshotRole['role'] = int(RoleType('snapshot'))
snapshotRole['url'] = 'http://example.com/snapshot.json'
snapshotRoleKeyids = Keyids().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))
snapshotRoleKeyid = Keyid('aaf05f8d054f8068bf6cb46beed7c824e2560802df462fc8681677586582ca99')
snapshotRoleKeyids[0] = snapshotRoleKeyid
snapshotRole['keyids'] = snapshotRoleKeyids
snapshotRole['threshold'] = 1
roles[1] = snapshotRole

targetsRole = TopLevelRole()
targetsRole['role'] = int(RoleType('targets'))
targetsRole['url'] = 'http://example.com/targets.json'
targetsRoleKeyids = Keyids().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))
targetsRoleKeyid = Keyid('c24b457b2ca4b3c2f415efdbbebb914a0d05c5345b9889bda044362589d6f596')
targetsRoleKeyids[0] = targetsRoleKeyid
targetsRole['keyids'] = targetsRoleKeyids
targetsRole['threshold'] = 1
roles[2] = targetsRole

timestampRole = TopLevelRole()
timestampRole['role'] = int(RoleType('timestamp'))
timestampRole['url'] = 'http://example.com/timestamp.json'
timestampRoleKeyids = Keyids().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))
timestampRoleKeyid = Keyid('6fcd9a928358ad8ca7e946325f57ec71d50cb5977a8d02c5ab0de6765fef040a')
timestampRoleKeyids[0] = timestampRoleKeyid
timestampRole['keyids'] = timestampRoleKeyids
timestampRole['threshold'] = 1
roles[3] = timestampRole

rootMetadata['roles'] = roles

signedBody = SignedBody().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3))
signedBody['rootMetadata'] = rootMetadata
signed['body'] = signedBody
metadata['signed'] = signed

signatures = Signatures().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))
signature = Signature()
signature['keyid'] = rootPublicKey['publicKeyid']
signature['method'] = int(SignatureMethod('ed25519'))
hash = Hash().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2))
hash['function'] = int(HashFunction('sha256'))
digest = BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1))
hexString = hashlib.sha256(encoder.encode(signed)).hexdigest()
digest['hexString'] = hexString
hash['digest'] = digest
signature['hash'] = hash

import tuf.repository_tool as rt
key_root_pub = rt.import_ed25519_publickey_from_file('mainroot.pub')
key_root_pri = rt.import_ed25519_privatekey_from_file('mainroot', password='pw')

import tuf.keys
signed_hash = tuf.keys.create_signature(key_root_pri, hexString)

signature['value'] = signed_hash['sig']
signatures[0] = signature
metadata['signatures'] = signatures

print(metadata.prettyPrint())
before = encoder.encode(metadata)
filename = 'root.cer'
with open(filename, 'wb') as a:
  a.write(before)



# Decode

with open(filename, 'rb') as b:
  after = b.read()

tuples = decoder.decode(after, asn1Spec=Metadata())
recovered = tuples[0]
print(recovered.prettyPrint())


recoveredSigned = recovered['signed']
# Because we know there's only one signature.
recoveredSignature = str(recovered['signatures'][0]['value'])

recoveredHexString = hashlib.sha256(encoder.encode(recoveredSigned)).hexdigest()

# The 0s here are us cheating. One would actually loop through the roles to
# find root and then the keyids to find the keyid that matches.
recoveredRootPublicKeyID = str(
    recovered['signed']['body']['rootMetadata']['roles'][0]['keyids'][0])

recoveredRootPublicKey = str(
    recovered['signed']['body']['rootMetadata']['keys'][0]['publicKeyValue']['hexString'])

recoveredRootPublicKeyDict = {
    'keytype': 'ed25519',
    'keyid': recoveredRootPublicKeyID,
    'keyval': {
        'public': recoveredRootPublicKey}}

recoveredSignatureDict = {
    'keyid': recoveredRootPublicKeyID,
    'method': 'ed25519',
    'sig': recoveredSignature}

assert tuf.keys.verify_signature(recoveredRootPublicKeyDict, recoveredSignatureDict, recoveredHexString), 'Failed! Womp womp!'
print('MISSION ACCOMPLISHED.')

