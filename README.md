# uptanedemo
Early demonstration code for UPTANE. Python 3 is preferred during development.

## Instructions on use of the uptane demo code
### Installation
(As usual, virtual environments are recommended for development and testing, but not necessary.)

To download and install the Uptane code, run the following:
```
git clone https://github.com/uptane/uptane
cd uptane
pip install cffi==1.7.0 pycrypto==2.6.1 pynacl==1.0.1 cryptography
pip install git+git://github.com/awwad/tuf.git@pinning
pip install -e .
```

If you're going to be running the ASN.1 encoding scripts once they are ready, you'll also need to `pip install pyasn1`


### Running
The code below is intended to be run IN FIVE PANES:
- Python shell for the OEM. This serves HTTP (repository files).
- Python shell for the Director (Repository and Service). This serves metadata and image files via HTTP receives manifests from the Primary via XMLRPC (manifests).
- Bash shell for the Timeserver. This serves signed times in response to requests from the Primary via XMLRPC.
- Python shell for a Primary client in the vehicle. This fetches images and metadata from the repositories via HTTP, and communicates with the Director service, Timeserver, and any Secondaries via XMLRPC.
- (At least one) Python shell for a Secondary in the vehicle. This communicates directly only with the Primary via XMLRPC, and will perform full metadata verification.


*WINDOW 1: the OEM Repository*
```python
import demo.demo_oem_repo as do
do.clean_slate()
do.write_to_live()
do.host()
# See instructions in uptane_test_instructions for examples of how to manipulate further.
# After the demo, to end hosting:
do.kill_server()
```


*WINDOW 2: the Director*
```python
import demo.demo_director as dd
dd.clean_slate()
dd.write_to_live()
dd.host()
dd.listen()

# Proceed to the next sections to prepare clients.

# Now, a variety of modifications / attacks can be made.
# For example, to try to have the director list a file not validated by the oem:
  new_target_fname = demo_director.TARGETS_DIR + '/file5.txt'
  open(new_target_fname, 'w').write('Director-created target')
  demo_director.repo.targets.add_target(new_target_fname)
  demo_director.write_to_live()

# After the demo, to end HTTP hosting
# (but not XMLRPC serving, which requires exiting the shell)
dd.kill_server()
```


*WINDOW 3: the Timeserver:*
```shell
#!/bin/bash
python demo/demo_timeserver.py
```

*WINDOW 4: the Primary client:*
(ONLY AFTER THE OTHERS HAVE FINISHED STARTING UP AND ARE HOSTING)
```python
import demo.demo_primary as dp
dp.clean_slate() # also listens, xmlrpc
# AFTER at least one Secondary client has been set up and submitted (next section), you
# can try out normal operation:
dp.generate_signed_vehicle_manifest()
dp.submit_vehicle_manifest_to_director()
```

*WINDOW 5+: the Secondary client(s):*
(ONLY AFTER THE OTHERS HAVE FINISHED STARTING UP AND ARE HOSTING)
```python
import demo.demo_secondary as ds
ds.clean_slate()
ds.listen()
ds.generate_signed_ecu_manifest()   # saved as ds.most_recent_signed_manifest
ds.submit_ecu_manifest_to_primary() # optionally takes different signed manifest
# Some attacks can be performed here, such as:
# Attack: MITM without secondary's key changes ECU manifest:
  ds.ATTACK_send_corrupt_manifest_to_primary()
  # (then, switch back to the Primary and execute:
  dp.submit_vehicle_manifest_to_director()
  # The Director should then discard the bad ECU Manifest and keep the rest of
  # the Vehicle Manifest.
# Attack: MITM modifies ECU manifest and signs with another ECU's key:
  ds.ATTACK_send_manifest_with_wrong_sig_to_primary()
  # (then, switch back to the Primary and execute:
  dp.submit_vehicle_manifest_to_director()
  # The Director should then discard the bad ECU Manifest and keep the rest of
  # the Vehicle Manifest.
