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

# GLOBALS
updater_instance = None


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
  directed_target_info = updater.targets_of_role('targets/director')
  directed_filepaths = [f['filepath'] for f in directed_target_info]

  trustworthy_directed_target_info = []
  trustworthy_directed_filepaths = []

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
    print('----------\a')
    print('Error: ☠ Untrustworthy File ☠')
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
    print('----------\a')
    print()
    play_sound_lose_horn()


  elif isinstance(mirror_error, tuf.DownloadLengthMismatchError):
    print()
    print('----------\a')
    print('Error: ☠ Untrustworthy File - Length mismatch ☠')
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
    print('----------\a')


  elif isinstance(mirror_error, tuf.ContradictionInMultiRoleDelegation):
    # Please note that there are other potential multi-role delegation
    # conflicts. The Director/Images pair is not the only possible multi-role
    # delegation in the system at all, but for the purpose of this demo, it
    # will be. The errors are distinguishable with some work, in any event.
    print()
    print('----------\a')
    print('Error: Director and mirror do not agree on file info.')
    print()
    print('The mirror hosting ' + mirror)
    print('is providing a file that does not match what the Director has')
    print('directed us to install. Metadata from the mirror and director does')
    print('not match. The downloaded file has been discarded. If retrying')
    print('continues to yield this error, it is likely that one of them is')
    print('unusually out of date, or that one or the other has been')
    print('compromised or that there is a man-in-the-middle attack along your')
    print('network route.')
    print('----------\a')
    print()


  elif isinstance(mirror_error, tuf.ExpiredMetadataError):
    #!
    # TODO: Could be local or remote metadata, though. Need more info.
    #!
    print()
    print('----------\a')
    print('Error: Expired metadata error.')
    print()
    print('The metadata in use for ' + mirror)
    print(' is expired.')
    print('----------\a')


  elif isinstance(mirror_error, tuf.ReplayedMetadataError):
    print()
    print('----------\a')
    print('Error: Replay Attack Detected.')
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
    print('----------\a')


  # Unsure if this would occur here or if it would be caught deeper in the
  # stack and raised as a replay error here. TODO: Check.
  elif isinstance(mirror_error, tuf.BadVersionNumberError):
    print()
    print('----------')
    print('Error: Encountered incorrect version number.')
    print()
    print('----------')
    raise

  # I don't know if this one would occur for the client request. This might be
  # exclusively used by repository_tool, and so we wouldn't expect it here.
  # TODO: Should check.
  elif isinstance(mirror_error, tuf.UnsignedMetadataError):
    print()
    print('----------\a')
    print('Error: Encountered unsigned metadata.')
    print()
    print('----------\a')
    raise


  else:
    print()
    print('----------\a')
    print('UNEXPECTED error: Type of error was: ' + str(type(mirror_error)))
    print()
    print('----------\a')
    play_sound_lose_horn()
    raise






def play_sound_lose_horn():
  subprocess.call(['afplay',
      '/Users/s/w/uptanedemo/sounds/price-is-right-losing-horn.mp3'])






def main():
  """Set up a new installation and update it, then exit."""
  clean_slate()
  update_client()





if __name__ == '__main__':
  main()
