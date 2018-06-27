"""
demo_single_command_run.py

<Purpose>
  A simple script to execute the demo outlined in README.md, sequentially.

  The primary purpose is for a fairly quick additional round of testing,
  to make sure that any changes made don't break the demo. Currently, checking
  to make sure everything ran correctly requires that you scan up through the
  output and check the yellow instructions against the preceding banners.
  More code is required to automate those checks, allowing this to be run
  as a test script, but this is helpful for now.

  To run the demo this way, run the following from the main uptane directory
  (which contains, for example, setup.py).
    python demo/demo_automation.py

  If 10 instructions in yellow text appear (e.g. "The preceding banner should
  be: NO UPDATE") and the banners indicated match, then the demo has run
  correctly.

  Note that this does not take the place of the test suite for the reference
  implementation, which is in tests/.

  # TODO: Add checks after each step to make sure that things run as expected.
  # This can then be used as a test script.

"""
import demo
import demo.demo_timeserver as dt
import demo.demo_director as dd
import demo.demo_image_repo as di
import demo.demo_primary as dp
import demo.demo_secondary as ds
import time # for brief pauses (since file movements are occurring)
import atexit # to trigger cleanup on exit
import shutil # to delete some directories when we're done
import os # paths and individual file deletion

from uptane import RED, GREEN, YELLOW, WHITE, ENDCOLORS


def main():
  """This function runs all the demo instructions in README.md."""

  # Trigger cleanup of associated files when this process is exited. We
  # register a listener to run the cleanup when this process exits rather than
  # just running the cleanup commands at the end of the script. This is because
  # we want to support the use of an interactive shell. It would be bad to
  # delete the repository files used right at the end of the README.md
  # instructions because the user may want to try some more things out before
  # exiting, so we just wait until the process exits.
  atexit.register(cleanup)

  # Start demo Image Repo, including http server and xmlrpc listener (listener
  # is for webdemo)
  di.clean_slate()

  # Start demo Director, including http server and xmlrpc listener (for
  # manifests, registrations, and webdemo)
  dd.clean_slate()

  # Start demo Timeserver, including xmlrpc listener (for requests from demo
  # Primary)
  dt.listen()


  # Start demo Primary client and (full verification) Secondary client
  dp.clean_slate()
  ds.clean_slate()

  # Run an update cycle on both clients, in order.
  dp.update_cycle()
  ds.update_cycle()

  # Declare, in yellow text in the output, that the expected preceding banner
  # indicates that no update was delivered.
  announce_expected_banner('NO UPDATE')


  # Prepare a firmware update: create the firmware file, sign it with
  # the appropriate Director and Image Repo roles, and post that metadata
  # where the services will host it.
  firmware_fname = filepath_in_repo = 'firmware.img'
  vin='democar'; ecu_serial='TCUdemocar'
  open(firmware_fname, 'w').write('Fresh firmware image')
  di.add_target_to_imagerepo(firmware_fname, filepath_in_repo)
  di.write_to_live()
  dd.add_target_to_director(firmware_fname, filepath_in_repo, vin, ecu_serial)
  dd.write_to_live(vin_to_update=vin)


  # Update the clients, resulting in this firmware being "installed" on the
  # Secondary.
  brief_sleep()
  dp.update_cycle()
  brief_sleep()
  ds.update_cycle() # UPDATED banner
  announce_expected_banner('UPDATED')


  # Run and then undo attack 3.1. (See README.md)
  dd.mitm_arbitrary_package_attack(vin, firmware_fname)
  brief_sleep()
  dp.update_cycle() # DEFENDED banner
  announce_expected_banner('DEFENDED')
  dd.undo_mitm_arbitrary_package_attack(vin, firmware_fname)


  # Run and then undo attack 3.2. (See README.md)
  di.mitm_arbitrary_package_attack(firmware_fname)
  brief_sleep()
  dp.update_cycle() # DEFENDED banner
  announce_expected_banner('DEFENDED')
  di.undo_mitm_arbitrary_package_attack(firmware_fname)


  # Prepare, run, and then undo attack 3.3. (See README.md)
  dd.backup_timestamp(vin)
  dd.write_to_live(vin)
  brief_sleep()
  dp.update_cycle()
  dd.replay_timestamp(vin)
  brief_sleep()
  dp.update_cycle() # REPLAYED banner
  announce_expected_banner('REPLAYED')
  dd.restore_timestamp(vin)


  # Run attack 3.4 and leave it running. (See README.md)
  dd.add_target_and_write_to_live(
      filename='firmware.img',
      file_content='evil content',
      vin=vin,
      ecu_serial=ecu_serial)
  brief_sleep()
  dp.update_cycle()
  announce_expected_banner('DEFENDED')


  # Run attack 3.5 and leave it running. (See README.md)
  di.add_target_and_write_to_live(
      filename='firmware.img',
      file_content='evil content')
  brief_sleep()
  dp.update_cycle()
  brief_sleep()
  ds.update_cycle() # COMPROMISED banner
  announce_expected_banner('COMPROMISED')


  # Recover from combined attacks 3.4 and 3.5. (See README.md)
  di.revoke_compromised_keys()
  di.add_target_and_write_to_live(
      filename='firmware.img',
      file_content='Fresh firmware image')
  dd.revoke_compromised_keys()
  dd.add_target_and_write_to_live(
      filename='firmware.img',
      file_content='Fresh firmware image',
      vin=vin,
      ecu_serial=ecu_serial)
  brief_sleep()
  dp.update_cycle()
  brief_sleep()
  ds.update_cycle() # UPDATED banner
  announce_expected_banner('UPDATED')


  # Run and then undo attack 3.7. (See README.md)
  dd.sign_with_compromised_keys_attack(vin)
  brief_sleep()
  dp.update_cycle() # DEFENDED banner
  announce_expected_banner('DEFENDED')
  brief_sleep()
  dd.undo_sign_with_compromised_keys_attack(vin)
  brief_sleep()
  dp.update_cycle()
  brief_sleep()
  ds.update_cycle() # NO UPDATE NEEDED banner
  announce_expected_banner('NO UPDATE NEEDED')





def cleanup():
  if os.path.isdir('director'):
    shutil.rmtree('director')

  if os.path.isdir('imagerepo'):
    shutil.rmtree('imagerepo')

  if os.path.isfile('firmware.img'):
    os.remove('firmware.img')



def announce_expected_banner(banner_name):
  print(YELLOW + '\n\n\nThe preceding banner should be: ' + banner_name +
      '\n\n\n' + ENDCOLORS)



def brief_sleep():
  """
  The demo code is written for manual use and file changes in the hosted
  folders may introduce some lag, so some pauses are added for automated use.
  """
  time.sleep(0.5)



if __name__ == '__main__':
  main()
