# [Uptane](https://uptane.github.io): Securing Software Updates for Automobiles

Reference Implementation and demonstration code

[![Build Status](https://travis-ci.org/uptane/uptane.png)](https://travis-ci.org/uptane/uptane) [![Coverage Status](https://coveralls.io/repos/github/uptane/uptane/badge.svg)](https://coveralls.io/github/uptane/uptane?branch=develop)
--------------------------------

# Documentation
Extensive documentation on design can be found in the following documents:

* [Design Overview](https://docs.google.com/document/d/1pBK--40BCg_ofww4GES0weYFB6tZRedAjUy6PJ4Rgzk/edit?usp=sharing)
* [Implementation Specification](https://docs.google.com/document/d/1wjg3hl0iDLNh7jIRaHl3IXhwm0ssOtDje5NemyTBcaw/edit?usp=sharing)
* [Deployment Considerations](https://docs.google.com/document/d/17wOs-T7mugwte5_Dt-KLGMsp-3_yAARejpFmrAMefSE/edit?usp=sharing)

The project's [maintainers, contribution policies, and how-tos for submitting
issues, security audits, etc. are visible in PROJECT.md](PROJECT.md)


# Instructions on use of the Uptane demonstration code

Below are the instructions on use of the Uptane demonstration and reference
implementation code, divided into these sections:

* [0: Installation](#0-installation)
* [1: Starting the Demo](#1-starting-the-demo)
* [2: Delivering an Update](#2-delivering-an-update)
* [3: Blocking Attacks](#3-blocking-attacks)
  * [3.1: Arbitrary Package Attack on Director Repository without Compromised Keys](#31-arbitrary-package-attack-on-director-repository-without-compromised-keys)
  * [3.2: Arbitrary Package Attack on Image Repository without Compromised Keys](#32-arbitrary-package-attack-on-image-repository-without-compromised-keys)
  * [3.3: Replay Attack without Compromised Keys](#33-replay-attack-without-compromised-keys)
  * [3.4: Arbitrary Package Attack with a Compromised Director Key](#34-arbitrary-package-attack-with-a-compromised-director-key)
  * [3.5: Compromise Both Repositories Simultaneously to Serve Arbitrary Package](#35-compromise-both-repositories-simultaneously-to-server-arbitrary-package)
  * [3.6: Recover from Major Key Compromise](#36-recover-from-major-key-compromise)
  * [3.7: Arbitrary Package Attack with Revoked Keys](#37-arbitrary-package-attack-with-revoked-keys)
* [Testing](#testing)


# 0: Installation
Uptane supports Python2 and Python3. As usual for Python, [virtual environments](https://python-docs.readthedocs.io/en/latest/dev/virtualenvs.html) are recommended for development and testing, but not necessary.

Some development libraries are necessary to install some of Uptane's dependencies. If your system uses apt, the command to install them will be:
```shell
$ sudo apt-get install build-essential libssl-dev libffi-dev python-dev python3-dev
```

Fedora-based distributions can instead install these libraries with dnf.
```shell
$ dnf install redhat-rpm-config openssl-devel libffi-devel python-devel python3-devel
```

OS X users can instead install these header libraries with the [Homebrew](http://brew.sh/) package manager.
```shell
$ brew install python
$ brew install libffi
```

To download and install the Uptane code and its dependencies, run the following:
```shell
$ git clone https://github.com/uptane/uptane
$ cd uptane
$ pip install -r dev-requirements.txt
```

#### Updates
When updating Uptane code, please reinstall its dependencies, as the
corresponding TUF fork may be updated:
`pip install --force-reinstall -r dev-requirements.txt`

#### Metadata format
Note that the demonstration now operates using ASN.1 / DER format and encoding
for metadata files by default. If desired, this can be switched to JSON (which
results in human-readable metadata files) by changing the
tuf.conf.METADATA_FORMAT option in `uptane/__init__.py`, from 'der' to 'json'
`tuf.conf.METADATA_FORMAT = 'json'`


#### Install command-line audio player (optional)
If you want the demo to play notification sounds you need one of the following audio player command line utilities on your path:
- mplayer (available for all major operating systems)
- omxplayer (built-in on Raspbian)
- afplay (built-in on OS X)

#### Troubleshooting
If you are running into errors or want to run unit and integration tests to
better understand the workings of the reference implementation, see the
[Testing](#testing) section at the bottom of this document.


# 1: Starting the Demo
The code below is intended to be run in three or more consoles:
- [WINDOW 1](#window-1-the-uptane-services): Python shell for the Uptane services
- [WINDOW 2](#window-2-the-primary-clients): Python shell for a Primary client in the vehicle. This fetches images and metadata from the repositories via HTTP, and communicates with the Director service, Timeserver, and any Secondaries via XMLRPC. (More of these can be run, simulating more vehicles with one Primary each.)
- [WINDOW 3](#window-3-the-secondary-clients): Python shell for a Secondary in the vehicle. This communicates directly only with the Primary via XMLRPC, and will perform full metadata verification. (More of these can be run, simulating more ECUs in one or more vehicles.)



### WINDOW 1: the Uptane services
These instructions start a demonstration version of the three services that
run OEM-side (or supplier-side, or fleet-side): the Image Repository,
the Director, and the Timeserver.


The Uptane documentation explains each of these services in greater detail,
but in brief:

**The Image Repository** is the main repository for images and general metadata
about them.

**The Director** generates metadata for specific
vehicles indicating which ECUs should install what firmware (validated against
and obtained from the Image Repository). It also receives and validates
Vehicle Manifests from Primaries, and the ECU Manifests from Secondaries
that have been bundled in the Vehicle Manifests, which capture trustworthy
information about what software is running on the ECUs, along with, optionally,
signed reports of any attacks observed by those ECUs.

**The Timeserver** is a simple service that receives requests for signed
times, each bundled by a vehicle Primary, and produces a signed attestation
that includes the request tokens each Secondary ECU sent to its Primary, so
that each ECU can better establish that it is not being tricked into accepting
a false or very old time.


From within the root `uptane/` directory of the downloaded code (which contains e.g. the `setup.py` file), run the following command. (Any version of Python > 2.7
should do. We test on 2.7, 3.5, and 3.6.)

```Bash
$ python -i demo/start_servers.py
```


After that, proceed to the following Windows to prepare clients.
Once those are ready, you can perform a variety of modifications and attacks.
Examples will be discussed below in the
[Delivering an Update](#2-delivering-an-update) and
[Blocking Attacks](#blocking-attacks) sections.



### WINDOW 2(+): the Primary client(s):
(Image Repo, Director, and Timeserver must already have finished starting up.)
The Primary client started below is likely to run on a more capable and
connected ECU in the vehicle - potentially the head unit / infotainment. It will
obtain metadata and images from the Image Repository as instructed by the Director
and distribute them appropriately to other, Secondary ECUs in the vehicle,
and it will receive ECU Manifests indicating the software on each Secondary ECU,
and bundle these into a Vehicle Manifest which it will send to the Director.

Open a Python shell in a new terminal window and then run the following:

```python
>>> import demo.demo_primary as dp
>>> dp.clean_slate() # sets up a fresh Primary that has never been updated
>>> dp.update_cycle()
```

The Primary's update_cycle() call:
- fetches and validates all signed metadata for the vehicle, from the Director and Image repositories
- fetches all images that the Director instructs this vehicle to install, excluding any that do not exactly match corresponding images on the Image repository. Any images fetched from the repositories that do not match validated metadata are discarded.
- queries the Timeserver for a signed attestation about the current time, including in it any nonces sent by Secondaries, so that Secondaries may trust that the time returned is at least as recent as their sent nonce
- generates a Vehicle Version Manifest with some vehicle metadata and all ECU Version Manifests received from Secondaries, describing currently installed images, most recent times available to each ECU, and reports of any attacks observed by Secondaries (can also be called directly: `dp.generate_signed_vehicle_manifest()`)
- sends that Vehicle Version Manifest to the Director (can also be called directly: `dp.submit_vehicle_manifest_to_director()`)

If you wish to run the demo with multiple vehicles (one Primary each), you can open a Python shell in a new terminal
window for each vehicle's Primary and provide a unique VIN and ECU Serial for each of them. Because each Secondary will need to communicate with the correct Primary in this demo, find port that is chosen in the Primary's initialization (when `dp.clean_slate()` is called) and make note of it so that it can be provided to any Secondaries you set up in a moment. The message will be e.g. "Primary will now listen on port 30702")
Example setting up a different Primary for a different vehicle:
```python
>>> import demo.demo_primary as dp
>>> dp.clean_slate(vin='112', ecu_serial='PRIMARY_ECU_2')
>>> dp.update_cycle()
```



### WINDOW 3(+): the Secondary client(s):
(The following assumes that the Image Repository, Director, Timeserver, and
Primary have finished starting up and are hosting/listening.)
Here, we start a single Secondary ECU and generate a signed ECU Manifest
with information about the "firmware" that it is running, which we send to the
Primary.

Open a Python shell in a new terminal window and then run the following:
- For full verification secondaries
```python
>>> import demo.demo_secondary as ds
>>> ds.clean_slate()
>>> ds.update_cycle()
```
- For partial verification secondaries
```python
>>> import demo.demo_secondary as ds
>>> ds.clean_slate(partial_verifying=True)
>>> ds.update_cycle()
```

Optionally, multiple windows with different Secondary clients can be run simultaneously. In each additional window, you can run the same calls as above to set up a new ECU in the same, default vehicle by modifying the clean_slate() call to include a distinct ECU Serial. e.g. `ds.clean_slate(ecu_serial='33333')` for Full Verification Secondaries or `ds.clean_slate(partial_verifying=True, ecu_serial='33333')` for Partial Verifying Secondaries.

If the Secondary is in a different vehicle from the default vehicle, this call should look like:
`ds.clean_slate(vin='vehicle_id_here', ecu_serial='ecu_serial_here', primary_port=30702)`, providing a VIN for the new vehicle, a unique ECU Serial, and indicating the port listed by this Secondary's Primary when that Primary initialized (e.g. "Primary will now listen on port 30702").

The Secondary's update_cycle() call for Full Verification Secondaries:
- fetches and validates the signed metadata for the vehicle from the Primary
- fetches any image that the Primary assigns to this ECU, validating that against the instructions of the Director in the Director's metadata, and against file info available in the Image Repository's metadata. If the image from the Primary does not match validated metadata, it is discarded.
- fetches the latest Timeserver attestation from the Primary, checking for the nonce this Secondary last sent. If that nonce is included in the signed attestation from the Timeserver and the signature checks out, this time is saved as valid and reasonably recent.
- generates an ECU Version Manifest that indicates the secure hash of the image currently installed on this Secondary, the latest validated times, and a string describing attacks detected (can also be called directly: `ds.generate_signed_ecu_manifest()`)
- submits the ECU Version Manifest to the Primary (can also be called directly: `ds.submit_ecu_manifest_to_primary()`)

The Secondary's update_cycle() call for Partial Verification Secondaries:
- fetches and validates the signed director's targets metadata for the vehicle from the Primary
- fetches any image that the Primary assigns to this ECU, validating that against the instructions of the Director in the Director's metadata. If the image from the Primary does not match validated metadata, it is discarded.
- fetches the latest Timeserver attestation from the Primary, checking for the nonce this Secondary last sent. If that nonce is included in the signed attestation from the Timeserver and the signature checks out, this time is saved as valid and reasonably recent.
- generates an ECU Version Manifest that indicates the secure hash of the image currently installed on this Secondary, the latest validated times, and a string describing attacks detected (can also be called directly: `ds.generate_signed_ecu_manifest()`)
- submits the ECU Version Manifest to the Primary (can also be called directly: `ds.submit_ecu_manifest_to_primary()`)



# 2: Delivering an Update
To deliver an Update via Uptane, you'll need to add the firmware image to the Image repository, then assign it to a vehicle
and ECU in the Director repository. Then, the Primary will obtain the new firmware, and the Secondary will update from the
Primary.

Execute the following code in the Uptane services window (WINDOW 1) to create a
new firmware file, generate metadata about it, sign that metadata with the
appropriate keys (assigned by delegations in the Image Repository), and host
the image and metadata on the Image Repository.

```python
>>> firmware_fname = filepath_in_repo = 'firmware.img'
>>> open(firmware_fname, 'w').write('Fresh firmware image')
>>> di.add_target_to_imagerepo(firmware_fname, filepath_in_repo)
>>> di.write_to_live()
```

To assign the new image to the ecu 'TCUdemocar' on vehicle 'democar', run
the following in the Uptane services window (WINDOW 1):
```python
>>> vin='democar'; ecu_serial='TCUdemocar'
>>> dd.add_target_to_director(firmware_fname, filepath_in_repo, vin, ecu_serial)
>>> dd.write_to_live(vin_to_update=vin)
```

Next, you can update the Primary. In WINDOW 2:
```python
>>> dp.update_cycle()
```

When the Primary has finished, you can update the Secondary. In WINDOW 3:
```python
>>> ds.update_cycle()
```

You should see an Updated banner on the Secondary, indicating a successful, validated update.



# 3: Blocking Attacks
Uptane is designed to secure the software updates delivered between repositories and vehicles.  [Section
7.3](https://docs.google.com/document/d/1pBK--40BCg_ofww4GES0weYFB6tZRedAjUy6PJ4Rgzk/edit#heading=h.jta2pcxo2frp) of the [Uptane Design Overview](https://docs.google.com/document/d/1pBK--40BCg_ofww4GES0weYFB6tZRedAjUy6PJ4Rgzk/edit?usp=sharing) covers all of the known attacks in more detail.  We begin this section with a demonstration
of the Arbitrary Package Attack.



### 3.1: Arbitrary Package Attack on Director Repository without Compromised Keys
This is a simple attack simulating a Man in the Middle that provides a malicious image file. In this attack, the
attacker does not have the keys to correctly sign new metadata (and so it is an exceptionally basic attack).

In the Uptane services window (1):
```python
>>> dd.mitm_arbitrary_package_attack(vin, firmware_fname)
```

As a result of the attack above, the Director will instruct the secondary client in the vehicle to install *firmware.img*.
Since this file is not on (and validated by) the Image Repository, the Primary will refuse to download it
(and a Full Verification Secondary would likewise refuse it even if a compromised Primary delivered it
to the Secondary).

In WINDOW 1, run:
```python
>>> dp.update_cycle()
```

Now, when the Primary runs dp.update_cycle(), it'll display the DEFENDED banner and play a sound clip, as it's
able to discard the manipulated file without even sending it to the Secondary.

To resume experimenting with the repositories, run this script to put the
repository back in a normal state (undoing what the attack did) by running the
following in the services window (1):
```python
>>> dd.undo_mitm_arbitrary_package_attack(vin, firmware_fname)
```

If the primary client runs an update_cycle() after the restoration of the Director repository, *firmware.img*
should updated successfully.



### 3.2: Arbitrary Package Attack on Image Repository without Compromised Keys
In the previous section, the firmware available on the director repository was replaced with a malicious one.
What if the image repository is corrupted with a malicious firmware?

Run the following in WINDOW 1:
```python
>>> di.mitm_arbitrary_package_attack(firmware_fname)
```

You can see the update once again proceeding normally by running this in the
Primary's window (2):
```python
>>> dp.update_cycle()
```


The result is the same: The primary client is expected to also discard the
malicious `firmware.img` downloaded from the Image repository
and print a DEFENDED banner.  If you inspect messages further up in
the console (above the banner) to get more detail, you should
find the following:

```
Downloading: u'http://localhost:30301/targets/firmware.img'
Downloaded 14 bytes out of the expected 14 bytes.
Not decompressing http://localhost:30301/targets/firmware.img
Update failed from http://localhost:30301/targets/firmware.img.
BadHashError
Failed to update /firmware.img from all mirrors: {u'http://localhost:30301/targets/firmware.img': BadHashError()}
Downloading: u'http://localhost:30401/democar/targets/firmware.img'
Could not download URL: u'http://localhost:30401/democar/targets/firmware.img'
```

Uptane detected that the image retrieved did not have a hash matching what the
signed, validated metadata indicated we should expect.

Undo the the arbitrary package attack so that subsequent demonstration sections
can proceed.

```python
>>> di.undo_mitm_arbitrary_package_attack(firmware_fname)
```

### 3.3: Replay Attack without Compromised Keys

We next demonstrate a replay attack, where the client is given an older (and previously trusted)
version of metadata.  A replay attack could result in a rollback of installed
software, causing secondary clients to use older firmware than they
currently trust. Rollback attacks in general are described in The
[Deny Functionality subsection of the Design Overview](https://docs.google.com/document/d/1pBK--40BCg_ofww4GES0weYFB6tZRedAjUy6PJ4Rgzk/edit#heading=h.4mo91b3dvcqd).

First, switch to the services window and copy the Timestamp role's
metadata, `timestamp.der` to a backup. This is what we'll roll back to in the
attack.
A function is available to perform this action:
```python
>>> dd.backup_timestamp(vin)
```

Now, we update the metadata in the Director repository. In this case, a fairly
empty update, writing a new `timestamp.der` and `snapshot.der` files. The backup
we saved earlier is now old by comparison.
```python
>>> dd.write_to_live(vin)
```

In the Primary's window (2), the Primary client now performs an update,
retrieving the new metadata we generated.

```python
>>> dp.update_cycle()
```

Next, in the services window, we simulate the replay attack, trying to
distribute the out-of-date metadata backed up earlier, effectively rolling back
the timestamp file to a previous version.
```python
>>> dd.replay_timestamp(vin)
```

If this old metadata is presented to the Primary, the Primary rejects it,
because it has already validated newer metadata. When you run the below, you
should see a REPLAY banner. The console also logs the cause of the download
failure (ReplayedMetadataError exception). In the **Primary's window**:
```python
>>> dp.update_cycle()
...
Update failed from http://localhost:30401/democar/metadata/timestamp.der.
ReplayedMetadataError
Failed to update timestamp.der from all mirrors:
{u'http://localhost:30401/democar/metadata/timestamp.der': ReplayedMetadataError()}
```

Finally, restore the valid, latest version of Timestamp metadata
(`timestamp.der`) into place in the services window.
```python
>>> dd.restore_timestamp(vin)
```



### 3.4: Arbitrary Package Attack with a Compromised Director Key

Thus far we have simulated a few attacks that have not depended on compromised keys.  In
the previous attacks, an attacker has presented unchanged, out-of-date data
(replay, 3.3) or simply modified the images or metadata requested by a primary
or secondary client, without having the right key to sign new metadata.
Consequently, these clients have blocked the attacks because the malicious
images do not match what is listed in signed, trusted metadata.

However, what happens if an attacker manages to obtain or make use of a
repository key and signs for a malicious image?  Is the client able to block a compromise
of just the image repository?  What about a compromise of both the image and director
repositories?

Both repositories currently have metadata about 'firmware.img', which we added
in the [2: Delivering an Update](#2-delivering-an-update) section.

For this attack, we'll modify `firmware.img` to include malicious content, and
will sign metadata certifying that malicious firmware file.

To simulate a compromised directory key, we simply sign for an updated
"firmware.img" that includes malicious content (the phrase "evil content" in
this case), in the services window:

```python
>>> dd.add_target_and_write_to_live(filename='firmware.img',
    file_content='evil content', vin=vin, ecu_serial=ecu_serial)
```

The primary client now attempts to download the malicious file.
```python
>>> dp.update_cycle()
```

The primary client should print a DEFENDED banner and provide the following error message: `The Director has instructed
us to download a file that does not exactly match the Image Repository metadata. File: '/firmware.img'`



### 3.5: Compromise Both Repositories Simultaneously to Serve Arbitrary Package
In 3.4, the Director repository has been compromised, but the malicious
metadata and firmware it distributes is rejected. Compromising the Director is
not enough to allow arbitrary package attacks against ECUs in the vehicle.
The Director can only instruct clients to install images validated by the Image
Repository.

But what happens if, at the same time, the attacker is able to sign with a
high-level image-signing key trusted by the Image Repository? (Note that these
should generally be offline keys and rarely need to be used.)
With the previous attack still in place, let's add:
```python
>>> di.add_target_and_write_to_live(filename='firmware.img', file_content='evil content')
```

Now, when the the Primary and Secondary update, the malicious package will
successfully be installed!

On the **primary** client:
```python
>>> dp.update_cycle()
```

On the **secondary** client:
```python
>>> ds.update_cycle()
```

Note, both the image and director repositories have been compromised. As a
result, unfortunately, in an attack of this kind Secondary would install this
malicious firmware.img, which neither the Primary nor the
Secondary have any way of knowing is malicious, since every necessary key has
signed metadata for that image.

For demonstration purposes, the secondary detects that a malicious file is installed.  The secondary
client in the demo code prints a banner indicating that the *firmware.img* image was malicously
installed: A malicious update has been installed! Arbitrary package attack successful:
this Secondary has been compromised! Image: 'new_firmware.img'

##### A note on the difficulty of this attack
To improve resilience against repository compromises, the
[Deployment Considerations document](https://docs.google.com/document/d/17wOs-T7mugwte5_Dt-KLGMsp-3_yAARejpFmrAMefSE)
provides many recommendations. In particular, the
[key placement recommendations](https://docs.google.com/document/d/17wOs-T7mugwte5_Dt-KLGMsp-3_yAARejpFmrAMefSE/view#heading=h.k5rokxr32wv6)
indicate that Targets keys for the Image Repository are best kept offline; it
should not be easy to compromise this top-level Image Repository Targets key
and use it to sign malicious images, as this key should be needed only when
altering delegations (to parties who may sign for particular subsets of images).
Depending on the way you deploy the system, this may be only when establishing a
relationship with a new firmware supplier or revoking trust in them, for
example.

A more limited attack of this sort is possible against a subset of available
firmware if rather than the top-level Image Repository targets keys, the
attacker acquires the signing keys held by a party who has been delegated trust
for a subset of images, such as a supplier the Image Repository has elected to
trust to do the image signing for its own firmware releases to the Image
Repository. While such delegated keys should also be held offline and need only
be used when the delegatee produces new firmware, it is easier to imagine such
a key being compromised than the Image Repository's top-level Targets role
key(s). The structure of Uptane is flexible enough to accommodate almost any
trust arrangement, allowing the impact of keys being lost to be limited to a
small subset of images. Note that as before, this attack still requires also
compromising the Director repository's Targets role keys or Root role keys.




### 3.6: Recover from Major Key Compromise

If a malicious attacker has laid hands on your online keys, or found a way to
force systems with such access to sign malicious metadata, trust in those keys
should be revoked, and new keys should be used in their place. These are likely
to be the Timestamp and Snapshot role keys, and the Targets role keys in some circumstances (generally the Director). (More information on these roles and
deployment considerations are available in documentation
[linked to above](#uptane).)

Once the servers have been recovered, it is easy to revoke any keys that may
have been compromised. We should also make sure that the targets and metadata
in the repositories are correct again, in case things have been changed by the
attacker while in control. In this demo, these two things are done like so:

In the services window:
```
>>> di.revoke_compromised_keys()
>>> di.add_target_and_write_to_live(filename='firmware.img',
        file_content='Fresh firmware image')
>>> dd.revoke_compromised_keys()
>>> dd.add_target_and_write_to_live(filename='firmware.img',
    file_content='Fresh firmware image', vin=vin, ecu_serial=ecu_serial)
```

We have just used the rarely-needed root keys of the two repositories to
revoke the potentially compromised Timestamp, Snapshot, and Targets keys from
both repositories. This is the first time they have needed to be used since the
repositories' creation at the beginning of this demo. Root keys should be
kept offline, as discussed in
the [Uptane Deployment Considerations document](https://docs.google.com/document/d/17wOs-T7mugwte5_Dt-KLGMsp-3_yAARejpFmrAMefSE/edit?usp=sharing).
If trust in a key needs to be revoked, the keys at a level above it (or any
level above that) can be used.
In the case of the top-level roles (like Timestamp, Snapshot, and Targets here),
that falls to Root to do. In the case of delegated Targets roles, the role
that delegates would do the revocation. So, for example, if you delegate
the ability to sign for firmware from a given vendor to the security team from
that vendor, and that team delegates in turn to a particular release manager,
and that release manager's YubiKey falls into the sewers, the security team
from the vendor can remove trust in it and trust a new key. Alternatively, the
top-level Targets role for the Image Repository could remove trust for the
security team from the vendor, etc.

Any client that receives the new metadata will be able to validate the root key
and will cease trusting the revoked keys.

On the **primary** client:
```python
>>> dp.update_cycle()
```

On the **secondary** client:
```python
>>> ds.update_cycle()
```

As ever, if a particular ECU has been compromised and arbitrary attacker code
has been executed on it, being certain that specific device is secure again
without wiping it manually is difficult. Devices that have not been compromised
in such an attack, however,
should thereafter be protected from the use of those compromised keys by an
attacker.



### 3.7: Arbitrary Package Attack with Revoked Keys

We should verify that the Primary does indeed reject metadata that's been
signed with revoked keys.  As noted in the previous section, the Primary and
secondaries automatically remove trust in revoked keys when they install the
new Root metadata.

Let's begin the demonstration by generating metadata that is maliciously
signed with the keys revoked in the last section.

```Python
>>> dd.sign_with_compromised_keys_attack(vin)
```


The Primary attempts to download the maliciously-signed metadata...

```Python
>>> dp.update_cycle()
```

... and detects a bad signature by displaying a DEFENDED banner.  The Primary
does not trust the keys and signature specified in the metadata, as expected.
If you were to inspect the cause of the download failure, you'd find the
following exception:

```
Downloading: u'http://localhost:30401/democar/metadata/timestamp.der'
Downloaded 202 bytes out of an upper limit of 16384 bytes.
Not decompressing http://localhost:30401/democar/metadata/timestamp.der
metadata_role: u'timestamp'
Update failed from http://localhost:30401/democar/metadata/timestamp.der.
BadSignatureError
Failed to update timestamp.der from all mirrors: {u'http://localhost:30401/democar/metadata/timestamp.der': BadSignatureError()}
Valid top-level metadata cannot be downloaded.  Unsafely update the Root metadata.
```

We next restore metadata to the previously trusted state, where the compromised
keys had been revoked and where new keys were added for the Targets, Snapshot,
and Timestamp roles.

```Python
>>> dd.undo_sign_with_compromised_keys_attack(vin)
```

If the Primary initiates an update cycle once again, it would appear to be
up-to-date.  The metadata that was signed by the revoked keys should not
have been saved by the Primary.


```Python
# This call should indicate that the client is up-to-date.
>>> dp.update_cycle()
```



# Testing

If you are concerned that there may be installation issues, or have run into
issues running the demo, or want to better understand the workings of
the reference implementation, or want a thorough test of whether or not the
Uptane reference implementation would work in a particular environment, you can
run Uptane's unit tests from the root uptane/ repository directory by invoking
[tox](https://testrun.org/tox/) like so:
```Bash
$ tox
```

Alternatively, you can execute any of the unit tests in the tests directory
directly, like so:
```Bash
$ python tests/test_secondary.py
```

Or you can run all tests with a particular encoding (default ASN.1/DER):
```Bash
$ python tests/runtests.py
// Or:
$ python tests/runtests.py json
$ python tests/runtests.py der
```