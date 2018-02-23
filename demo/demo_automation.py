"""
demo_automation.py

<Purpose>
  A simple script to execute the demo outlined in README.md, sequentially.

  To run the demo this way, run the following from the main uptane directory
  (which contains, for example, setup.py).
    python -i demo/demo_automation.py

  That starts the demo in an interactive mode (with a prompt from which
  you can manipulate them for the demonstrations). The demo is run in full
  before any commands can be entered.

  # TODO: Add checks after each step to make sure that things run as expected.
  # This can then be used as a test script.

"""
import demo
import demo.demo_timeserver as dt
import demo.demo_director as dd
import demo.demo_image_repo as di
import demo.demo_primary as dp
import demo.demo_secondary as ds
#from six.moves import xmlrpc_server
import readline, rlcompleter # for tab completion in interactive Python shell
import time # for brief pauses (since file movements are occurring)

from uptane import RED, GREEN, YELLOW, WHITE, ENDCOLORS

def main():

  # Start demo Image Repo, including http server and xmlrpc listener (for
  # webdemo)
  di.clean_slate()

  # Start demo Director, including http server and xmlrpc listener (for
  # manifests, registrations, and webdemo)
  dd.clean_slate()

  # Start demo Timeserver, including xmlrpc listener (for requests from demo
  # Primary)
  dt.listen()


  # Start demo clients
  dp.clean_slate()
  ds.clean_slate()

  # Run an update cycle on both clients.
  dp.update_cycle()
  ds.update_cycle()
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




def announce_expected_banner(banner_name):
  print(YELLOW + '\n\n\nThe preceding banner should be: ' + banner_name +
      '\n\n\n' + ENDCOLORS)


def brief_sleep():
  time.sleep(0.5)


if __name__ == '__main__':
  readline.parse_and_bind('tab: complete')
  main()
