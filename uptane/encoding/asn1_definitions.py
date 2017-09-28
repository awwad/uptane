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


class Keyid(OctetString):
    pass


class Signature(univ.Sequence):
    pass


Signature.componentType = namedtype.NamedTypes(
    namedtype.NamedType('keyid', Keyid()),
    namedtype.NamedType('method', SignatureMethod()),
    namedtype.NamedType('value', OctetString())
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
    namedtype.NamedType('encryptedSymmetricKeyValue', OctetString().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 1)))
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
    namedtype.NamedType('function', HashFunction()),
    namedtype.NamedType('digest', OctetString()))


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
    namedtype.NamedType('block', OctetString().subtype(explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatConstructed, 2)))
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


class Version(Natural):
    pass



class URL(char.VisibleString):
    pass


URL.subtypeSpec = constraint.ValueSizeConstraint(1, 1024)


class URLs(univ.SequenceOf):
    pass


URLs.componentType = URL()
URLs.subtypeSpec=constraint.ValueSizeConstraint(0, 256)



class VehicleVersionManifestSigned(univ.Sequence):
    pass


VehicleVersionManifestSigned.componentType = namedtype.NamedTypes(
    namedtype.NamedType('vehicleIdentifier', Identifier().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
    namedtype.NamedType('primaryIdentifier', Identifier().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))),
    namedtype.NamedType('numberOfECUVersionManifests', Length().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2))),
    namedtype.NamedType('ecuVersionManifests', ECUVersionManifests().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3))),
    namedtype.OptionalNamedType('securityAttack', char.VisibleString().subtype(subtypeSpec=constraint.ValueSizeConstraint(1, 1024)).subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 4)))
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


