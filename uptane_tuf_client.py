"""
<Program Name>
  uptane_tuf_client.py

<Purpose>
  Run a TUF client to perform Uptane updates.


"""

import tuf
import tuf.repository_tool as repotool
import tuf.client.updater as updater
import uptane_tuf_server
import os # for chdir
import shutil # for copying

from uptane_tuf_server import SERVER_PORT, ROOT_PATH, REPO_NAME, REPO_PATH
from uptane_tuf_server import METADATA_LIVE_PATH
from uptane_tuf_server import CLEAN_REPO_NAME, CLEAN_REPO_PATH, CLEAN_KEYS_DIR
from uptane_tuf_server import CLEAN_METADATA_PATH, CLEAN_IMAGES_DIR


CLEAN_CLIENT_PATH = ROOT_PATH + '/clean_tufclient'
CLIENT_PATH = ROOT_PATH + '/temp_tufclient'
#CLIENT_REPO_PATH = CLIENT_PATH + '/client_repo_copy'
CLIENT_KEYS_PATH = CLIENT_PATH + '/keystore'
CLIENT_CURRENT_METADATA_PATH = CLIENT_REPO_PATH + '/metadata/current'
CLIENT_PREVIOUS_METADATA_PATH = CLIENT_REPO_PATH + '/metadata/previous'


def set_up_client():
  # "Install" a fresh client: copy the original repository files appropriately.

  # The original repository, keystore, and client directories will be copied.

  # Remove existing client, if any.
  #for p in [CLIENT_PATH]: #[CLIENT_REPO_PATH, CLIENT_KEYS_PATH]:
  if os.path.exists(CLIENT_PATH):
    shutil.rmtree(CLIENT_PATH)

  # Create client directories.
  #for p in [CLIENT_PATH, CLIENT_REPO_PATH]:
  #  if not os.path.exists(p):
  #    os.makedirs(p)

  # Copy clean metadata and keys to the new client.
  shutil.copytree(CLEAN_CLIENT_PATH, CLIENT_PATH)  
  #shutil.copytree(CLEAN_METADATA_PATH, CLIENT_CURRENT_METADATA_PATH)
  #shutil.copytree(CLEAN_METADATA_PATH, CLIENT_PREVIOUS_METADATA_PATH)
  #shutil.copytree(CLEAN_KEYS_DIR, CLIENT_KEYS_PATH)

  # Set the local repository directory containing all of the metadata files.
  tuf.conf.repository_directory = CLIENT_PATH





def update_client():

  # Does the tuf server url we're about to use have the correct format?
  try:
    tuf.formats.URL_SCHEMA.check_match(uptane_tuf_server.url)
  except tuf.FormatError as e:
    message = 'The repository mirror supplied is invalid.' 
    raise tuf.RepositoryError(message)

  # # Set the local repository directory containing all of the metadata files.
  # tuf.conf.repository_directory = CLIENT_REPO_PATH

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

  #info_for_all_potential_targets = updater.all_targets()
  #filepaths_for_all_potential_targets = [f['filepath'] for f in
  #    info_for_all_potential_targets]

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








def main():
  # Set up a new installation and update it, then exit.
  set_up_client()
  update_client()





if __name__ == '__main__':
  main()
