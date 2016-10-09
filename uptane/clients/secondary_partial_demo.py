"""
<Program Name>
  secondary_partial_demo.py

<Purpose>
  An implementation of an Uptane Secondary client that performs partial
  verification of Uptane/TUF metadata by employing the Uptane plugin
  secondary_partial.

"""

import tuf.schema as SCHEMA
import uptane.formats
import random # for randint for nonces
import time # for sleep

import uptane.client.secondary_partial as sp_module






# Modeling this over with procedural programming
def secondary_at_boot():

  # Step 1: New Time

  new_time = get_new_time_info()

  if new_time is None:
    _note_that_no_time_info_was_provided()
    # No new nonce.

  else: # We have a new time to validate.
    _generate_and_store_new_nonce()
    valid = _validate_new_time()
    if valid:
      _store_validated_time()

    else:
      _note_that_invalid_time_info_was_provided()


  # Step 2: New Metadata

  new_metadata = get_new_metadata()

  if new_metadata is None:
    pass # No new metadata, nothing to do.
  else:
    valid = _validate_new_metadata()
  
    if valid:
      install_



def get_new_time_info():
  """Returns any time information that has been provided us that needs to be
  validated.
  Returns None if no new time info has been provided to us that has not yet
  been validated and stored as current."""
  raise NotImplementedError()

def _note_that_no_time_info_was_provided():
  # Error? Treat as possible freeze attack?
  # Set Freeze bit to True for next send?
  raise NotImplementedError()

def _note_that_invalid_time_info_was_provided():
  # Error? Treat as possible freeze attack?
  # Set Freeze bit to True for next send?
  raise NotImplementedError()

def _validate_new_time():
  """Given time info, return True if it's valid."""
  raise NotImplementedError()
  
def _generate_and_store_new_nonce():
  """"""
  raise NotImplementedError()

def _store_validated_time():
  """Save new time as valid. Save current validated time as previously
  validated time (losing the former value of previously validated time), and
  store newly validated time as current validated time."""
  raise NotImplementedError()
  
def get_new_metadata():
  """Fetch new Director.json, basically. Return None if no new one exists."""
  raise NotImplementedError()

def _validate_new_metadata():
  """Returns True if new metadata is valid and signed by known Director key.
  Confirm that the hash from the signature portion matches the hash of the
  metadata. Confirm that the """
  raise NotImplementedError()








class UptaneSecondaryPVClient:
"""
Procedure for the new 
"""


  def __init__(self, ecu_info, firmware_fileinfo):
    """
    Arguments: 
      ecu_info:
          ecu info, object matching uptane.formats.ECU_SCHEMA
      firmware_fileinfo:
          The image the ecu is currently using, identified by filename in the
          repo, hash of the file, and file sieze. This is an object matching
          tuf.formats.TARGETFILE_SCHEMA

    TODO: Should eventually support multiple images used for a given ECU.
    """
    # Validate the arguments.
    uptane.formats.ECU_SCHEMA.check_match(ecu_info)
    uptane.formats.TARGETFILE_SCHEMA.check_match(image)

    self.ecu_info = ecu_info
    self.firmware_fileinfo = firmware_fileinfo
    self.nonce_next = self._create_nonce() # Nonce for when we need a new one
    self.nonce_sent = None # Value of nonce sent in last report to primary

    self.tuf_updater = \
        tuf.client.updater.Updater('repository', repository_mirrors)




  def report_to_primary(self):
    """Sends version info to the Primary, along with a nonce for future
    timeserver requests."""
    nonce_to_use = self.create_nonce()

    self.nonce_sent = self.nonce_next
    self.nonce_next = self._create_nonce()
    # Consider saving some nonce history beyond just one position.

    # Additional data that may be sent to the primary:
    # Current time (perceived time? last timeserver call?)
    # Previous recorded time (to the extent this makes sense - previous timeserver time?)
    # 
    raise NotImplementedError('Not yet written.')




  def _create_nonce(self):
    """Returns a pseudorandom number for use in protecting from replay attacks
    from the timeserver (or an intervening party)."""
    return random.randint(formats.NONCE_LOWER_BOUND, formats.NONCE_UPPER_BOUND)





  def receive_updates(self):
    """
    Listen for update data from the Primary and store it in extra storage to be
    checked and "installed" on next boot.

    Cycles forever.
    """

    while True:
      raise NotImplementedError('Not yet written.')

      sleep(0.05)




  def validate_new_image(self):
    """
    Given file_info for a new image, validate it against signed metadata.
    """
    raise NotImplementedError('Not yet written.')
