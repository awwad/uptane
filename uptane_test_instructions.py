"""

uptane_test_instructions.py

This is demonstration code for Uptane.

The code below is intended to be run IN FIVE PYTHON SHELLS:
- One for the OEM Repository, speaking HTTP
- One for the Director Repository, speaking HTTP
- One for the Director Services, speaking XMLRPC (receives manifests)
- One for the Timeserver, speaking XMLRPC (receives requests for signed times)
- One for the client

Each shell should be run in a python environment (the same environment is
fine) that has the awwad/tuf:pinning version of TUF installed. In order to
get everything you need, run the following:
`pip install cffi==1.7.0 pycrypto==2.6.1 pynacl==1.0.1 cryptography`
`pip install git+git://github.com/awwad/tuf.git@pinning`

# (If you run into issues installing cryptography, you may need to:
#   apt-get install build-essential libssl-dev libffi-dev python-dev
# )
# More instructions for other distributions at
# https://github.com/theupdateframework/tuf/blob/develop/README.rst


If you're going to be running the ASN.1 encoding scripts (not involved here),
you'll also need to `pip install pyasn1`

# WINDOW 1: the Supplier repository
import demo_oem_repo as demo_oem
demo_oem.clean_slate()
demo_oem.write_to_live()
demo_oem.host()
# See instructions in sections below for examples of what to do next.

# WINDOW 2: the Director repository
import demo_director_repo as demo_director
demo_director.clean_slate()
demo_director.write_to_live()
demo_director.host()
# See instructions in sections below for examples of what to do next.

# WINDOW 3: the Director service (receives manifests)
./run_director_svc.sh
      # OR, in a python shell:
      import uptane.director.director as director_svc
      d_svc = director_svc.Director()
      d_svc.listen()

# WINDOW 4: the Timeserver service (responds to requests for signed times):
./run_timeserver.sh
      # OR, in a python shell:
      import uptane.director.timeserver as timeserver
      timeserver.listen()

# In the client's window (ONLY after the others FINISH starting and are hosting)
# Running this sets up a fresh secondary and executes a full update cycle,
# along with a few tests.
import demo_client
demo_client.clean_slate() #default: use_new_keys=False
demo_client.update_cycle()

# (For attacks and such, see below in the client section.)
"""


# ----------------
# Main (OEM) Repo window
# ----------------
"""
import demo_oem_repo as demo_oem
demo_oem.clean_slate()
demo_oem.write_to_live()
demo_oem.host()
"""

# Modifications can be made here.
# For example, add something to the repo that is not validated by the director:
"""
new_target_fname = demo_director.TARGETS_DIR + '/file5.txt'
open(new_target_fname, 'w').write('Director-created target')
demo_oem.repo.targets.add_target(new_target_fname)
demo_oem.write_to_live()
# demo_oem.kill_server()
"""


# ----------------
# Director Repo window
# ----------------
"""
import demo_director_repo as demo_director
demo_director.clean_slate()
demo_director.write_to_live()
demo_director.host()
"""

# Modifications can be made here.
# For example, try to have the director list a file not validated by the oem:
"""
# new_target_fname = demo_director.TARGETS_DIR + '/file5.txt'
# open(new_target_fname, 'w').write('Director-created target')
# demo_director.repo.targets.add_target(new_target_fname)
# demo_director.write_to_live()
# # demo_director.kill_server()
"""



# ----------------
# Inventory DB / Director Services window
# ----------------
"""
import uptane.director.director as director_svc
d_svc = director_svc.Director()
d_svc.listen()
"""




# ----------------
# Client window
# ----------------
"""
import demo_client
demo_client.clean_slate() #default: use_new_keys=False
demo_client.update_cycle()

# At this point, file1.txt has been downloaded.

demo_client.generate_and_send_manifest_to_director()

# Here's an attack: MITM without secondary's key changes ECU manifest:

demo_client.ATTACK_send_corrupt_manifest_to_director()

# Here's another attack: MITM modifies ECU manifest and signs with another ECU's key:

demo_client.ATTACK_send_manifest_with_wrong_sig_to_director()


"""


# Old junk code to salvage for more tests follows.
"""

  # If we change our copy of the timeserver's public key here, it simulates a
  # man in the middle (possibly the Primary) changing the time and invalidating
  # the timeserver's signature.
  # The result of running the below will be an informative error about the
  # timeserver's key not checking out.
  print('ATTACK TEST: simulating modified timeserver data.')
  key_timeserver_wrong_pub = rt.import_ed25519_publickey_from_file(
      os.path.join('attack_data', 'timeserver_wrong.pub'))
  secondary_ecu.timeserver_public_key = key_timeserver_wrong_pub
  try:
    nonce = secondary_ecu._create_nonce()
    secondary_ecu.update_time_from_timeserver(nonce)
  except tuf.BadSignatureError:
    print('Successfully detected bad signature on timeserver time.')
  else:
    raise Exception('Failed to detect bad signature on timeserver time!')

  # Put the right public key back.  
  secondary_ecu.timeserver_public_key = key_timeserver_pub


  # Insist that file2.txt is one of the verified targets.
  assert True in [targ['filepath'] == '/file2.txt' for targ in \
      verified_targets], 'I do not see /file2.txt in the verified targets.' + \
      ' Test has changed or something is wrong. The targets are: ' + \
      repr(verified_targets)


  #file2_trustworthy_info = upd.target('file2.txt')

  # If you execute the following, commented-out command, you'll get a not found
  # error, because while the mainrepo specifies file1.txt, the Director does not.
  # Anything the Director doesn't also list can't be validated.
  # file1_trustworthy_info = secondary.updater.target('file1.txt')

  # Delete file2.txt if it already exists. We're about to download it.
  if os.path.exists(os.path.join(client_directory_name, 'file2.txt')):
    os.remove(os.path.join(client_directory_name, 'file2.txt'))

  # Now that we have fileinfo for all targets listed by both the Director and
  # the Supplier (mainrepo) -- which should include file2.txt in this test --
  # we can download the target files and only keep each if it matches the
  # verified fileinfo. This call will try every mirror on every repository
  # within the appropriate delegation in pinned.json until one of them works.
  # In this case, both the Director and mainrepo (Supplier) are hosting the
  # file, just for my convenience in setup. If you remove the file from the
  # Director before calling this, it will still work (assuming mainrepo still
  # has it). (The second argument here is just where to put the files.)
  # This should include file2.txt.
  for verified_target in verified_targets:
    secondary_ecu.updater.download_target(
        verified_target, client_directory_name)

    file_location = os.path.join(
        client_directory_name, verified_target['filepath'][1:])

    print(file_location)
    # Make sure the download occurred.
    assert os.path.exists(file_location), 'Failed download w/o error??: ' + \
        str(verified_target)

  #upd.download_target(file2_trustworthy_info, '.')

  if os.path.exists(os.path.join(client_directory_name, 'file2.txt')):
    print('File file2.txt has successfully been validated and downloaded.')
  else:
    print('Nope, file2.txt was not downloaded.')
    assert False


  # Here, I'll assume that the client retains metadata about the firmware image
  # it currently has installed. Things could operate instead such that metadata
  # is calculated based on the installed image.
  # For this test, we'll assume that the target info provided by the Director
  # and supplier for file2 is the same as what is already running on the
  # client.

  # This is a tuf.formats.TARGETFILE_SCHEMA, containing filepath and fileinfo
  # fields.
  # Grab the first verified target, presumably file2.txt, to use it for the
  # ECU manifest later.
  assert len(verified_targets), 'No targets were found, but no error was generated??'
  installed_firmware_targetinfo = verified_targets[0]


  # Load or generate a key.
  if use_new_keys:
    rt.generate_and_write_ed25519_keypair('secondary', password='pw')

  # Load in from the generated files.
  key_pub = rt.import_ed25519_publickey_from_file('secondary.pub')
  key_pri = rt.import_ed25519_privatekey_from_file('secondary', password='pw')

  key = uptane.common.canonical_key_from_pub_and_pri(key_pub, key_pri)


  # Generate and sign a manifest indicating that this ECU has a particular
  # version/hash/size of file2.txt as its firmware.
  signed_ecu_manifest = secondary_ecu.generate_signed_ecu_manifest(
      installed_firmware_targetinfo, [key])


  print('Submitting the Secondary\'s real manifest to the Director.')
  secondary_ecu.submit_ecu_manifest_to_director(signed_ecu_manifest)
  print('Submission successful.')


  import xmlrpc.client # To catch the Fault exception.

  # Attack: MITM w/o key modifies ECU manifest.
  # Modify the ECU manifest without updating the signature.

  signed_ecu_manifest['signed']['attacks_detected'] = 'Everything is great!'
  signed_ecu_manifest['signed']['ecu_serial'] = 'ecu22222'
  try:
    secondary_ecu.submit_ecu_manifest_to_director(signed_ecu_manifest)
  except xmlrpc.client.Fault as e:
    print('Director service REJECTED the fraudulent ECU manifest.')
  else:
    print('Director service ACCEPTED the fraudulent ECU manifest!')
  # (The Director, in its window, should now indicate that it has received this
  # manifest. If signature checking for manifests is on, then the manifest is
  # rejected. Otherwise, it is simply accepted.)


  print('Tests complete.')


"""


