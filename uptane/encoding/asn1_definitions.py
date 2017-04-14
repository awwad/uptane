# This file is generated from asn1_definitions.asn1, by a combination of
# asn1c and asn1ate, along with some hand modification in between.
# After this, the order of components in this file should be hand-modified
# purely for git consistency (readable diffs) and then this sequence of comments
# should be added to the start again.
#
# How to generate this file when changes are made to the ASN.1 definitions in
# asn1_definitions.asn1:
#
# 1. generate the consolidated ASN.1 definitions in Python using asn1c,
#    putting them in file intermediate_asn1_definitions.asn1:
#    $ asn1c -EF asn1_definitions.asn1 > intermediate_asn1_definitions.asn1
#
# 2. Make manual edits to the newly generated intermediate_asn1_definitions.asn1
#    to keep it consistent with pyasn1's asn1ate expections:
#
#    2.1 Remove all PATTERN constraints on VisibleString definitions.
#    2.2 Remove extraneous Module definitions: the full file is to be treated
#        as one module.
#        For example, remove sets of three lines like this:
#           END
#           MetadataModule DEFINITIONS AUTOMATIC TAGS ::=
#           BEGIN
#        When you're finished, there should be only one Module definitions
#        statement and one END statement in the file.
#
# 3. Run pyasn1's asn1ate to generate the Python definitions from the
#    consolidated ASN.1 definitions:
#    $ asn1ate intermediate_asn1_definitions.asn1 > asn1_definitions.py
#
# 4. Add this long comment to the top of the new asn1_definitions.py.
#
# 5. Finally, if you are committing this to the github repo, please re-order
#    the generated lines to match the previous git version as best you can,
#    so as to avoid junk/unreadable diffs, but being careful not to move
#    a given item X after an item Y if Y uses X.
#
# 6. You can now delete intermediate_asn1_definitions.asn1.
#

from pyasn1.type import univ, char, namedtype, namedval, tag, constraint, useful

# To make this module work, had to:
# 1. Define the INTEGER MAX value.
# https://www.obj-sys.com/docs/acv58/CCppUsersGuide/CCppUsersGuidea12.html
MAX = 2**32-1


class OctetString(univ.OctetString):
    pass


OctetString.subtypeSpec = constraint.ValueSizeConstraint(1, 2048)


class BitString(univ.BitString):
    pass


BitString.subtypeSpec=constraint.ValueSizeConstraint(1, 2048)


class BinaryData(univ.Choice):
    pass


BinaryData.componentType = namedtype.NamedTypes(
    namedtype.NamedType('bitString', BitString().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('octetString', OctetString().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1)))
)


class Token(univ.Integer):
    pass


class Tokens(univ.SequenceOf):
    pass


Tokens.componentType = Token()
Tokens.subtypeSpec=constraint.ValueSizeConstraint(1, 1024)


class Natural(univ.Integer):
    pass


Natural.subtypeSpec = constraint.ValueRangeConstraint(0, MAX)


class Length(Natural):
    pass


class Positive(univ.Integer):
    pass


Positive.subtypeSpec = constraint.ValueRangeConstraint(1, MAX)


class UTCDateTime(Positive):
    pass


class TokensAndTimestamp(univ.Sequence):
    pass


TokensAndTimestamp.componentType = namedtype.NamedTypes(
    namedtype.NamedType('numberOfTokens', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('tokens', Tokens().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('timestamp', UTCDateTime().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)))
)


class SignatureMethod(univ.Enumerated):
    pass


SignatureMethod.namedValues = namedval.NamedValues(
    ('rsassa-pss', 0),
    ('ed25519', 1)
)


class Keyid(BinaryData):
    pass


class Signature(univ.Sequence):
    pass


Signature.componentType = namedtype.NamedTypes(
    namedtype.NamedType('keyid', Keyid().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.NamedType('method', SignatureMethod().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('value', BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)))
)


class Signatures(univ.SequenceOf):
    pass


Signatures.componentType = Signature()
Signatures.subtypeSpec=constraint.ValueSizeConstraint(1, 256)



# I can't seem to figure out why I need to do this this way.
# Why can't I just use Metadata() by adding TokensAndTimestamp to SignedBody()?
class TokensAndTimestampSignable(univ.Sequence):
    pass


TokensAndTimestampSignable.componentType = namedtype.NamedTypes(
    namedtype.NamedType('signed', TokensAndTimestamp().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.NamedType('numberOfSignatures', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('signatures', Signatures().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)))
)


class EncryptedSymmetricKeyType(univ.Enumerated):
    pass


EncryptedSymmetricKeyType.namedValues = namedval.NamedValues(
    ('aes128', 0),
    ('aes192', 1),
    ('aes256', 2)
)


class EncryptedSymmetricKey(univ.Sequence):
    pass


EncryptedSymmetricKey.componentType = namedtype.NamedTypes(
    namedtype.NamedType('encryptedSymmetricKeyType', EncryptedSymmetricKeyType().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('encryptedSymmetricKeyValue', BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)))
)


class Identifier(char.VisibleString):
    pass


Identifier.subtypeSpec = constraint.ValueSizeConstraint(1, 256)


class HashFunction(univ.Enumerated):
    pass


HashFunction.namedValues = namedval.NamedValues(
    ('sha224', 0),
    ('sha256', 1),
    ('sha384', 2),
    ('sha512', 3),
    ('sha512-224', 4),
    ('sha512-256', 5)
)


class Hash(univ.Sequence):
    pass


Hash.componentType = namedtype.NamedTypes(
    namedtype.NamedType('function', HashFunction().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('digest', BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)))
)


class Hashes(univ.SequenceOf):
    pass


Hashes.componentType = Hash()
Hashes.subtypeSpec=constraint.ValueSizeConstraint(1, 32)


class Filename(char.VisibleString):
    pass


Filename.subtypeSpec = constraint.ValueSizeConstraint(1, 256)


class Target(univ.Sequence):
    pass


Target.componentType = namedtype.NamedTypes(
    namedtype.NamedType('filename', Filename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('length', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('numberOfHashes', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('hashes', Hashes().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3)))
)


class Custom(univ.Sequence):
    pass


Custom.componentType = namedtype.NamedTypes(
    namedtype.OptionalNamedType('releaseCounter', Natural().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.OptionalNamedType('hardwareIdentifier', Identifier().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.OptionalNamedType('ecuIdentifier', Identifier().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.OptionalNamedType('encryptedTarget', Target().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3))),
    namedtype.OptionalNamedType('encryptedSymmetricKey', EncryptedSymmetricKey().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 4)))
)


class ECUVersionManifestSigned(univ.Sequence):
    pass


ECUVersionManifestSigned.componentType = namedtype.NamedTypes(
    namedtype.NamedType('ecuIdentifier', Identifier().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('previousTime', UTCDateTime().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('currentTime', UTCDateTime().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.OptionalNamedType('securityAttack', char.VisibleString().subtype(subtypeSpec=constraint.ValueSizeConstraint(1, 1024)).subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3))),
    namedtype.NamedType('installedImage', Target().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 4)))
)


class ECUVersionManifest(univ.Sequence):
    pass


ECUVersionManifest.componentType = namedtype.NamedTypes(
    namedtype.NamedType('signed', ECUVersionManifestSigned().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.NamedType('numberOfSignatures', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('signatures', Signatures().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)))
)


class ECUVersionManifests(univ.SequenceOf):
    pass


ECUVersionManifests.componentType = ECUVersionManifest()
ECUVersionManifests.subtypeSpec=constraint.ValueSizeConstraint(1, 256)


class ImageBlock(univ.Sequence):
    pass


ImageBlock.componentType = namedtype.NamedTypes(
    namedtype.NamedType('filename', Filename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('blockNumber', Positive().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('block', BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)))
)


class ImageFile(univ.Sequence):
    pass


ImageFile.componentType = namedtype.NamedTypes(
    namedtype.NamedType('filename', Filename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('numberOfBlocks', Natural().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('blockSize', Positive().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)))
)


class ImageRequest(univ.Sequence):
    pass


ImageRequest.componentType = namedtype.NamedTypes(
    namedtype.NamedType('filename', Filename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0)))
)


class Keyids(univ.SequenceOf):
    pass


Keyids.componentType = Keyid()
Keyids.subtypeSpec=constraint.ValueSizeConstraint(1, 1024)


class RoleType(univ.Enumerated):
    pass


RoleType.namedValues = namedval.NamedValues(
    ('root', 0),
    ('targets', 1),
    ('snapshot', 2),
    ('timestamp', 3)
)


class PublicKeyType(univ.Enumerated):
    pass


PublicKeyType.namedValues = namedval.NamedValues(
    ('rsa', 0),
    ('ed25519', 1)
)


class PublicKey(univ.Sequence):
    pass


PublicKey.componentType = namedtype.NamedTypes(
    namedtype.NamedType('publicKeyid', Keyid().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.NamedType('publicKeyType', PublicKeyType().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('publicKeyValue', BinaryData().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)))
)


class PublicKeys(univ.SequenceOf):
    pass


PublicKeys.componentType = PublicKey()
PublicKeys.subtypeSpec=constraint.ValueSizeConstraint(1, 1024)


class Threshold(Positive):
    pass


class StrictFilename(char.VisibleString):
    pass


StrictFilename.subtypeSpec = constraint.ValueSizeConstraint(1, 256)


class MultiRole(univ.Sequence):
    pass


MultiRole.componentType = namedtype.NamedTypes(
    namedtype.NamedType('rolename', StrictFilename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('numberOfKeyids', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('keyids', Keyids().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('threshold', Threshold().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3)))
)


class MultiRoles(univ.SequenceOf):
    pass


MultiRoles.componentType = MultiRole()
MultiRoles.subtypeSpec=constraint.ValueSizeConstraint(1, 128)


class Path(char.VisibleString):
    pass


Path.subtypeSpec = constraint.ValueSizeConstraint(1, 256)


class Paths(univ.SequenceOf):
    pass


Paths.componentType = Path()
Paths.subtypeSpec=constraint.ValueSizeConstraint(1, 256)


class PathsToRoles(univ.Sequence):
    pass


PathsToRoles.componentType = namedtype.NamedTypes(
    namedtype.NamedType('numberOfPaths', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('paths', Paths().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('numberOfRoles', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('roles', MultiRoles().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3))),
    namedtype.DefaultedNamedType('terminating', univ.Boolean().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4)).subtype(value=0))
)


class PrioritizedPathsToRoles(univ.SequenceOf):
    pass


PrioritizedPathsToRoles.componentType = PathsToRoles()
PrioritizedPathsToRoles.subtypeSpec=constraint.ValueSizeConstraint(1, 128)


class TargetsDelegations(univ.Sequence):
    pass


TargetsDelegations.componentType = namedtype.NamedTypes(
    namedtype.NamedType('numberOfKeys', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('keys', PublicKeys().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('numberOfDelegations', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('delegations', PrioritizedPathsToRoles().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3)))
)


class TargetAndCustom(univ.Sequence):
    pass


TargetAndCustom.componentType = namedtype.NamedTypes(
    namedtype.NamedType('target', Target().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.OptionalNamedType('custom', Custom().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)))
)


class Targets(univ.SequenceOf):
    pass


Targets.componentType = TargetAndCustom()
Targets.subtypeSpec=constraint.ValueSizeConstraint(1, 256)


class TargetsMetadata(univ.Sequence):
    pass


TargetsMetadata.componentType = namedtype.NamedTypes(
    namedtype.NamedType('numberOfTargets', Natural().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('targets', Targets().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.OptionalNamedType('delegations', TargetsDelegations().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)))
)


class Version(Natural):
    pass


class TimestampMetadata(univ.Sequence):
    pass


TimestampMetadata.componentType = namedtype.NamedTypes(
    namedtype.NamedType('filename', Filename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('version', Version().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('length', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('numberOfHashes', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3))),
    namedtype.NamedType('hashes', Hashes().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4)))
)


class URL(char.VisibleString):
    pass


URL.subtypeSpec = constraint.ValueSizeConstraint(1, 1024)


class URLs(univ.SequenceOf):
    pass


URLs.componentType = URL()
URLs.subtypeSpec=constraint.ValueSizeConstraint(0, 256)


class TopLevelRole(univ.Sequence):
    pass


TopLevelRole.componentType = namedtype.NamedTypes(
    namedtype.NamedType('role', RoleType().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.OptionalNamedType('numberOfURLs', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.OptionalNamedType('urls', URLs().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('numberOfKeyids', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3))),
    namedtype.NamedType('keyids', Keyids().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4))),
    namedtype.NamedType('threshold', Threshold().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 5)))
)


class TopLevelRoles(univ.SequenceOf):
    pass


TopLevelRoles.componentType = TopLevelRole()
TopLevelRoles.subtypeSpec=constraint.ValueSizeConstraint(4, 4)


class RootMetadata(univ.Sequence):
    pass


RootMetadata.componentType = namedtype.NamedTypes(
    namedtype.NamedType('numberOfKeys', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('keys', PublicKeys().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('numberOfRoles', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('roles', TopLevelRoles().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3)))
)


class RootRoleFileInfo(univ.Sequence):
    pass


RootRoleFileInfo.componentType = namedtype.NamedTypes(
    namedtype.NamedType('filename', StrictFilename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('version', Version().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('length', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('numberOfHashes', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3))),
    namedtype.NamedType('hashes', Hashes().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4)))
)


class TargetRoleFileInfo(univ.Sequence):
    pass


TargetRoleFileInfo.componentType = namedtype.NamedTypes(
    namedtype.NamedType('filename', StrictFilename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('version', Version().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1)))
)


class TargetRoleFileInfos(univ.SequenceOf):
    pass


TargetRoleFileInfos.componentType = TargetRoleFileInfo()


class SnapshotMetadata(univ.Sequence):
    pass


SnapshotMetadata.componentType = namedtype.NamedTypes(
    namedtype.NamedType('numberOfTargetRoleFiles', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('targetRoleFileInfos', TargetRoleFileInfos().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('rootRoleFileInfo', RootRoleFileInfo().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)))
)


class VehicleVersionManifestSigned(univ.Sequence):
    pass


VehicleVersionManifestSigned.componentType = namedtype.NamedTypes(
    namedtype.NamedType('vehicleIdentifier', Identifier().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('primaryIdentifier', Identifier().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('numberOfECUVersionManifests', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('ecuVersionManifests', ECUVersionManifests().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3))), # Should this be tagFormatConstructed?
    namedtype.OptionalNamedType('securityAttack', char.VisibleString().subtype(subtypeSpec=constraint.ValueSizeConstraint(1, 1024)).subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4)))
)


class SignedBody(univ.Choice):
    pass


SignedBody.componentType = namedtype.NamedTypes(
    namedtype.NamedType('rootMetadata', RootMetadata().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.NamedType('targetsMetadata', TargetsMetadata().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1))),
    namedtype.NamedType('snapshotMetadata', SnapshotMetadata().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2))),
    namedtype.NamedType('timestampMetadata', TimestampMetadata().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3))),
    namedtype.NamedType('vehicleVersionManifest', VehicleVersionManifestSigned().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 4))),
    namedtype.NamedType('ecuVersionManifest', ECUVersionManifestSigned().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 5))),
    namedtype.NamedType('timeAttestation', TokensAndTimestamp().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 6)))
)


class Signed(univ.Sequence):
    pass


Signed.componentType = namedtype.NamedTypes(
    namedtype.NamedType('type', RoleType().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('expires', UTCDateTime().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('version', Natural().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('body', SignedBody().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3)))
)


class Metadata(univ.Sequence):
    pass


Metadata.componentType = namedtype.NamedTypes(
    namedtype.NamedType('signed', Signed().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.NamedType('numberOfSignatures', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('signatures', Signatures().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)))
)


class MetadataFile(univ.Sequence):
    pass


MetadataFile.componentType = namedtype.NamedTypes(
    namedtype.NamedType('setGUID', univ.Integer().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('fileNumber', Positive().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('filename', Filename().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('metadata', Metadata().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 3)))
)


class MetadataFiles(univ.Sequence):
    pass


MetadataFiles.componentType = namedtype.NamedTypes(
    namedtype.NamedType('setGUID', univ.Integer().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('numberOfMetadataFiles', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1)))
)


class SequenceOfTokens(univ.Sequence):
    pass


SequenceOfTokens.componentType = namedtype.NamedTypes(
    namedtype.NamedType('numberOfTokens', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('tokens', Tokens().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1)))
)


class VehicleVersionManifest(univ.Sequence):
    pass


VehicleVersionManifest.componentType = namedtype.NamedTypes(
    namedtype.NamedType('signed', VehicleVersionManifestSigned().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 0))),
    namedtype.NamedType('numberOfSignatures', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('signatures', Signatures().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)))
)


class VersionReport(univ.Sequence):
    pass


VersionReport.componentType = namedtype.NamedTypes(
    namedtype.NamedType('tokenForTimeServer', Token().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('ecuVersionManifest', ECUVersionManifest().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)))
)


