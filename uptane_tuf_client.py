#
# THIS FILE IS OUTDATED


"""
<Program Name>
  uptane_tuf_client.py

<Purpose>
  Run a TUF client to perform Uptane updates for the PI demonstration.


"""

import tuf
import tuf.repository_tool as repotool
import tuf.client.updater
import uptane_tuf_server
import os # for chdir
import shutil # for copying
import subprocess # to play a sound from the system

from uptane_tuf_server import SERVER_PORT, ROOT_PATH, REPO_NAME, REPO_PATH
from uptane_tuf_server import METADATA_LIVE_PATH
from uptane_tuf_server import CLEAN_REPO_NAME, CLEAN_REPO_PATH, CLEAN_KEYS_DIR
from uptane_tuf_server import CLEAN_METADATA_PATH, CLEAN_IMAGES_DIR

# CONSTANTS
CLEAN_CLIENT_PATH = ROOT_PATH + '/clean_tufclient'
CLIENT_PATH = ROOT_PATH + '/temp_tufclient'
CLIENT_CURRENT_METADATA_PATH = CLIENT_PATH + '/metadata/current'
CLIENT_PREVIOUS_METADATA_PATH = CLIENT_PATH + '/metadata/previous'
CLIENT_TARGETS_PATH = CLIENT_PATH + '/targets'

# COLORS FOR PRINTING
#RED_ON_BLACK = '\033[91m'
#GREEN_ON_BLACK = '\033[92m'
#YELLOW_ON_BLACK = '\033[93m'
RED = '\033[41m\033[30m' # black on red
GREEN = '\033[42m\033[30m' # black on green
END = '\033[0m'

# GLOBALS
updater = None


def clean_slate():
  """
  "Install" a fresh client: copy the original repository files appropriately.
  """
  # The original repository, keystore, and client directories will be copied.

  # Remove existing client, if any.
  if os.path.exists(CLIENT_PATH):
    shutil.rmtree(CLIENT_PATH)

  # Copy clean metadata and keys to the new client.
  shutil.copytree(CLEAN_CLIENT_PATH, CLIENT_PATH)

  # Set the local repository directory containing all of the metadata files.
  tuf.conf.repository_directory = CLIENT_PATH





def update_client():
  """Perform a simple update cycle on the current client."""
  global updater

  # TODO: Make sure this doesn't hide exceptions - or, if it does, be OK with
  # that.
  #tuf.log.remove_console_handler()

  # Does the tuf server url we're about to use have the correct format?
  try:
    tuf.formats.URL_SCHEMA.check_match(uptane_tuf_server.url)
  except tuf.FormatError as e:
    message = 'The repository mirror supplied is invalid.' 
    raise tuf.RepositoryError(message)

  # Set the repository mirrors.  This dictionary is needed by the Updater
  # class of updater.py.
  repository_mirrors = {'mirror': {'url_prefix': uptane_tuf_server.url,
      'metadata_path': 'metadata',
      'targets_path': 'targets',
      'confined_target_dirs': ['']}}

  # Create the repository object using the repository name 'repository'
  # and the repository mirrors defined above.
  updater = tuf.client.updater.Updater('repository', repository_mirrors)

  # Refresh top-level metadata.
  updater.refresh()

  # Fetch the target info specified by the director role.
  # (Note that this info is not final; it's simply what the director
  # specifies. When we call updater.target() on each file path, that is when
  # all delegation is validated.)
  directed_target_info = updater.targets_of_role('director')
  directed_filepaths = [f['filepath'] for f in directed_target_info]

  trustworthy_directed_target_info = []
  trustworthy_directed_filepaths = []

  failed_targets = False

  # Update each of these targets.
  # I think I see a vulnerability in using the trusted order from above. I
  # think that a compromised delegate can reorder targets by declaring targets
  # not delegated to him. I don't know if that makes a difference, though; the
  # order of target filenames themselves shouldn't matter, I think.
  # TODO: Confirm. (Using targets_of_role kinda sucks.)
  for filepath in directed_filepaths:
    print('Checking image for updated info: ' + filepath)

    try:
      fileinfo = updater.target(filepath) # raises exception; catch it and deal

    except tuf.UnknownTargetError as e:
      print()
      print(RED + 'Error: Missing file.\a')
      print('Director has listed a file that cannot be validated on the '
          'repository:\n   ' + filepath)
      print('This file will be skipped.' + END)
      print('If this continues to occur, it may be that one or the other of\n'
        'the director or the repository been compromised.')
      print()
      failed_targets = True
      show_stop_sign()


    except: #TODO: handle TUF errors here.
      print('Caught unhandled exception from updater.target. Re-raising:')
      raise

    else:
      trustworthy_directed_target_info.append(fileinfo)
      trustworthy_directed_filepaths.append(fileinfo['filepath'])
      print('Done checking image for updated info: ' + filepath)
      # TODO: Note if any change occurred by digging into previous metadata.


  for target_info in trustworthy_directed_target_info:
    try:
      updater.download_target(target_info, CLIENT_TARGETS_PATH)

    except tuf.NoWorkingMirrorError as e:
      analyze_noworkingmirror_and_report(e, target_info)
      failed_targets = True

    else:
      report_success(target_info)

  if not failed_targets:
    report_all_successes()






def analyze_noworkingmirror_and_report(nwm_error, target_info):
  """
  Analyze a tuf.NoWorkingMirrorError and synthesize what the problem was,
  and print info.
  """
  individual_mirror_errors = nwm_error.mirror_errors
  #print(str(individual_mirror_errors))

  # For now, simple logic, assuming one mirror. Expand later to list error
  # count by type, etc. Grab the one and only error from the dictionary.
  assert len(individual_mirror_errors) == 1, 'Reporting function is ' + \
      'written to handle only one mirror currently, for the demonstration.'
  (mirror, mirror_error) = individual_mirror_errors.popitem()

  if isinstance(mirror_error, tuf.BadHashError):
    print()
    print(RED + 'Error: ☠ Untrustworthy File: ' + target_info['filepath'] + END)
    print()
    print('The mirror hosting ' + mirror)
    print('is providing an untrustworthy file. The file obtained from the')
    print('mirror does not match trusted metadata for that file and has been')
    print('rejected.')
    print('  File hash mismatch:')
    print('    Observed: ' + mirror_error.observed_hash)
    print('    Expected: ' + mirror_error.expected_hash)
    print()
    print('The mismatched file has been discarded. If retrying continues to')
    print('fail, it may be that the mirror has been compromised, or that')
    print('there is a man-in-the-middle attack along your network route.')
    print()
    show_stop_sign()
    play_sound_womp_womp()


  elif isinstance(mirror_error, tuf.DownloadLengthMismatchError):
    print()
    print(RED + 'Error: ☠ Untrustworthy File - Length mismatch ☠\a' + END)
    print()
    print('The mirror hosting ' + mirror)
    print('is providing an untrustworthy file. The file obtained from the')
    print('mirror does not match trusted metadata for that file and has been')
    print('rejected.')
    print('  File length mismatch:')
    print('    Observed: ' + str(mirror_error.observed_length))
    print('    Expected: ' + str(mirror_error.expected_length))
    print('')
    print('The mismatched file has been discarded. If retrying continues to')
    print('fail, it may be that the mirror has been compromised, or that')
    print('there is a man-in-the-middle attack along your network route.')
    show_stop_sign()
    play_sound_womp_womp()


  elif isinstance(mirror_error, tuf.ContradictionInMultiRoleDelegation):
    # Please note that there are other potential multi-role delegation
    # conflicts. The Director/Images pair is not the only possible multi-role
    # delegation in the system at all, but for the purpose of this demo, it
    # will be. The errors are distinguishable with some work, in any event.
    print()
    print(RED + 'Error: ☠ Director and mirror do not agree on file info. ☠\a' + END)
    print()
    print('The mirror hosting ' + mirror)
    print('is providing a file that does not match what the Director has')
    print('directed us to install. Metadata from the mirror and director does')
    print('not match. The downloaded file has been discarded. If retrying')
    print('continues to yield this error, it is likely that one of them is')
    print('unusually out of date, or that one or the other has been')
    print('compromised or that there is a man-in-the-middle attack along your')
    print('network route.')
    print()
    show_stop_sign()
    play_sound_womp_womp()


  elif isinstance(mirror_error, tuf.ExpiredMetadataError):
    #!
    # TODO: Could be local or remote metadata, though. Need more info.
    #!
    print()
    print(RED + 'Error: Expired metadata error.\a' + END)
    print()
    print('The metadata in use for ' + mirror)
    print(' is expired.')


  elif isinstance(mirror_error, tuf.ReplayedMetadataError):
    print()
    print(RED + 'Error: Replay Attack Detected.\a' + END)
    print()
    print('The mirror for ' + mirror)
    print('provided an old version of the metadata for a role.')
    print()
    print('  Metadata role at issue: ' + str(mirror_error.metadata_role))
    print('  Outdated version of metadata on the mirror: ' +
        str(mirror_error.previous_version))
    print('  Version of metadata we already have:        ' +
        str(mirror_error.current_version))
    print('')


  # Unsure if this would occur here or if it would be caught deeper in the
  # stack and raised as a replay error here. TODO: Check.
  elif isinstance(mirror_error, tuf.BadVersionNumberError):
    print()
    print(RED + 'Error: Encountered incorrect version number.\a')
    print()
    raise

  # I don't know if this one would occur for the client request. This might be
  # exclusively used by repository_tool, and so we wouldn't expect it here.
  # TODO: Should check.
  elif isinstance(mirror_error, tuf.UnsignedMetadataError):
    print()
    print(RED + 'Error: Encountered unsigned metadata.' + END)
    print()
    raise


  else:
    print()
    print(RED + 'UNEXPECTED error: Type of error was: ' + str(type(mirror_error)) + END)
    print()
    play_sound_lose_horn()
    raise






def report_success(target_info):
  print()
  print(GREEN + 'Successfully validated target: ' + target_info['filepath'] + END)
  print()
  
def report_all_successes():
  print()
  print(GREEN + 'Successfully validated all targets.' + END)
  show_check_ok()




def play_sound_lose_horn():
  subprocess.call(['afplay',
      ROOT_PATH + '/sounds/price-is-right-losing-horn.mp3'])

def play_sound_womp_womp():
  #subprocess.call(['afplay',
  #    ROOT_PATH + '/sounds/womp-womp.mp3'])
  pass

def show_stop_sign():
  subprocess.call(['open', ROOT_PATH + '/sounds/stop_sign.png'])
  
def show_check_ok():
  subprocess.call(['open', ROOT_PATH + '/sounds/check_ok.png'])
  



def main():
  """Set up a new installation and update it, then exit."""
  clean_slate()
  update_client()





if __name__ == '__main__':
  main()
