# Uptane
Reference Implementation and demonstration code for UPTANE.

Please note that extensive documentation on design can be found in the following documents:
- [Uptane Design Overview](https://docs.google.com/document/d/13XXQZ6KXCK_MiZj_Q84PQyMDmBiHnhEfgJgj8drKWRI/edit#heading=h.8swqb4rerhs3)
- [Uptane Implementation Specification](https://docs.google.com/document/d/1noDyg2t5jB6y3R5-Y3TXXj1tocv_y24NjmOw8rAcaAc/edit?pli=1#)

Python 3 is preferred during development.


# Instructions on use of the Uptane demonstration code
## Installation
(As usual, virtual environments are recommended for development and testing, but not necessary. If you use a virtual environment, use python3: virtualenv -p python3 <name>)

Some development libraries are necessary to install some of Uptane's dependencies. If your system uses apt, the command to install them will be:
```shell
sudo apt-get install build-essential libssl-dev libffi-dev python-dev python3-dev
```


To download and install the Uptane code and its dependencies, run the following:
```shell
git clone https://github.com/uptane/uptane
cd uptane
pip install cffi==1.7.0 pycrypto==2.6.1 pynacl==1.0.1 cryptography canonicaljson
pip install git+git://github.com/awwad/tuf.git@pinning
pip install -e .
```

If you're going to be running the ASN.1 encoding scripts once they are ready, you'll also need to `pip install pyasn1`


## Running
The code below is intended to be run IN FIVE PANES:
- WINDOW 1: Python shell for the OEM. This serves HTTP (repository files).
- WINDOW 2: Python shell for the Director (Repository and Service). This serves metadata and image files via HTTP receives manifests from the Primary via XMLRPC (manifests).
- WINDOW 3: Bash shell for the Timeserver. This serves signed times in response to requests from the Primary via XMLRPC.
- WINDOW 4: Python shell for a Primary client in the vehicle. This fetches images and metadata from the repositories via HTTP, and communicates with the Director service, Timeserver, and any Secondaries via XMLRPC. (More of these can be run, simulating more vehicles with one Primary each.)
- WINDOW 5: Python shell for a Secondary in the vehicle. This communicates directly only with the Primary via XMLRPC, and will perform full metadata verification. (More of these can be run, simulating more ECUs in one or more vehicles.)


###*WINDOW 1: the Supplier/OEM Repository*
These instructions start a demonstration version of an OEM's or Supplier's main repository
for software, hosting images and the metadata Uptane requires.

```python
import demo.demo_oem_repo as do
do.clean_slate()
```
After the demo, to end hosting:
```python
do.kill_server()
```


###*WINDOW 2: the Director*
The following starts a Director server, which generates metadata for specific
vehicles indicating which ECUs should install what firmware (validated against
and obtained from the OEM's main repository). It also receives and validates
Vehicle Manifests from Primaries, and the ECU Manifests from Secondaries
within the Vehicle Manifests, which capture trustworthy information about what
software is running on the ECUs, along with signed reports of any attacks
observed by those ECUs.

```python
import demo.demo_director as dd
dd.clean_slate()
```

After that, proceed to the following Windows to prepare clients.
Once those are ready, you can perform a variety of modifications / attacks.

For example, to try to have the director list a new file not validated by the
oem:
```python
new_target_fname = dd.demo.DIRECTOR_REPO_TARGETS_DIR + '/file5.txt'
open(new_target_fname, 'w').write('Director-created target')
dd.add_target_to_director(new_target_fname, ecu_serial='<ecu serial>')
dd.write_to_live()
```

After the demo, to end HTTP hosting (but not XMLRPC serving, which requires
exiting the shell), do this (or else you'll have a zombie Python process to kill)
```python
dd.kill_server()
```


###*WINDOW 3: the Timeserver:*
The following starts a simple Timeserver, which receives requests for signed
times, bundled by the Primary, and produces a signed attestation that includes
the nonces each Secondary ECU sent the Primary to include along with the
time request, so that each ECU can better establish that it is not being tricked
into accepting a false time.
```shell
#!/bin/bash
python demo/demo_timeserver.py
```

###*WINDOW 4(+): the Primary client(s):*
(ONLY AFTER SUPPLIER, DIRECTOR, AND TIMESERVER HAVE FINISHED STARTING UP AND ARE HOSTING)
The Primary client started below is likely to run on a more capable and
connected ECU in the vehicle - potentially the head unit / infotainment. It will
obtain metadata and images from the OEM Repository as instructed by the Director
and distribute them appropriately to other, Secondary ECUs in the vehicle,
and it will receive ECU Manifests indicating the software on each Secondary ECU,
and bundle these into a Vehicle Manifest which it will send to the Director.
```python
import demo.demo_primary as dp
dp.clean_slate() # sets up a fresh Primary that has never been updated
dp.update_cycle()
```

The Primary's update_cycle() call:
- fetches and validates all signed metadata for the vehicle, from the Director and Supplier repositories
- fetches all images that the Director instructs this vehicle to install, excluding any that do not exactly match corresponding images on the Supplier repository. Any images fetched from the repositories that do not match validated metadata are discarded.
- queries the Timeserver for a signed attestation about the current time, including in it any nonces sent by Secondaries, so that Secondaries may trust that the time returned is at least as recent as their sent nonce
- generates a Vehicle Version Manifest with some vehicle metadata and all ECU Version Manifests received from Secondaries, describing currently installed images, most recent times available to each ECU, and reports of any attacks observed by Secondaries (can also be called directly: `dp.generate_signed_vehicle_manifest()`)
- sends that Vehicle Version Manifest to the Director (can also be called directly: `dp.submit_vehicle_manifest_to_director()`)

If you wish to run the demo with multiple vehicles (one Primary each), you can open a new
window for each vehicle's Primary and provide a unique VIN and ECU for each of them. Find the port that is chosen in the Primary's initialization and make note of it so that it can be provided to any Secondaries you set up in a moment (e.g. "Primary will now listen on port 30702")
For example:
```python
import demo.demo_primary as dp
dp.clean_slate(vin='112', ecu_serial='PRIMARY_ECU_2', primary_port='30702') # Make sure the port matches the Primary's reported port, if there are multiple vehicles running.
dp.update_cycle()
```



###*WINDOW 5(+): the Secondary client(s):*
(ONLY AFTER SUPPLIER, DIRECTOR, TIMESERVER, AND PRIMARY HAVE FINISHED STARTING UP AND ARE HOSTING)
Here, we start a single Secondary ECU and generate a signed ECU Manifest
with information about the "firmware" that it is running, which we send to the
Primary.
```python
import demo.demo_secondary as ds
ds.clean_slate()
ds.update_cycle()
```

Optionally, multiple windows with different Secondary clients can be run simultaneously. In each additional window, you can run the same calls as above to set up a new ECU in the same, default vehicle by modifying the clean_slate() call to include a distinct ECU Serial. e.g. `ds.clean_slate(ecu_serial='33333')`

If the Secondary is in a different vehicle from the default vehicle, this call should look like:
`ds.clean_slate(vin='112', ecu_serial='33333', primary_port='30702')`, providing a VIN for the new vehicle, a unique ECU Serial, and indicating the port listed by this Secondary's Primary when that Primary initialized (e.g. "Primary will now listen on port 30702").

The Secondary's update_cycle() call:
- fetches and validates the signed metadata for the vehicle from the Primary
- fetches any image that the Primary assigns us, validating that against the instructions of the Director in the Director's metadata, and against file info available in the Supplier's metadata. If the image from the Primary does not match validated metadata, it is discarded.
- fetches the latest Timeserver attestation from the Primary, checking for the nonce this Secondary last sent. If that nonce is included in the signed attestation from the Timeserver and the signature checks out, this time is saved as valid and reasonably recent.
- generates an ECU Version Manifest that indicates the secure hash of the image currently installed on this Secondary, the latest validated times, and a string describing attacks detected (can also be called directly: `ds.generate_signed_ecu_manifest()`)
- submits the ECU Version Manifest to the Primary (can also be called directly: `ds.submit_ecu_manifest_to_primary()`)


At this point, some attacks can be performed here, such as:

####Attack: MITM without Secondary's key changes ECU manifest:
The next command simulates a Man in the Middle attack that attempts to modify
the ECU Manifest from this Secondary to issue a false report. In this simple
attack, we simulate the Man in the Middle modifying the ECU Manifest without
modifying the signature (which, without the ECU's private key, it cannot
produce).
```python
# Send the Primary a signed ECU manifest that has been modified after the signature.
ds.ATTACK_send_corrupt_manifest_to_primary()
```
Then run this in Window 4 (the Primary's window), to cause the Primary to bundle
this ECU Manifest in its Vehicle Manifest and send it off to the Director:
```python
dp.generate_signed_vehicle_manifest()
dp.submit_vehicle_manifest_to_director()
```
As you can now see from the output in Window 2, the Director discards the bad
ECU Manifest from this Secondary, and retains the rest of the Vehicle Manifest
from the Primary.

####Attack: MITM modifies ECU manifest and signs with another ECU's key:
The next command also simulates a Man in the Middle attack that attempts to modify
the ECU Manifest from this Secondary to issue a false report. In this attack,
we simulate the Man in the Middle modifying the ECU Manifest and replacing the
signature with a valid signature from a *different* key (obtained, say, from
another vehicle's analogous ECU after reverse-engineering).
```python
ds.ATTACK_send_manifest_with_wrong_sig_to_primary()
```
Then run this in Window 4 (the Primary's window):
```python
dp.generate_signed_vehicle_manifest()
dp.submit_vehicle_manifest_to_director()
```
As you can now see from the output in Window 2, the Director discards the bad
ECU Manifest from this Secondary, and retains the rest of the Vehicle Manifest
from the Primary.