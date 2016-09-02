"""
<Program Name>
  secondary_full.py

<Purpose>
  An Uptane client modeling the behavior of a secondary ECU performing full
  verification, as would be performed during ECU boot.

"""

import tuf.schema as SCHEMA
import uptane.formats
import random # for randint for nonces
import time # for sleep




class SecondaryECUClient():


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
