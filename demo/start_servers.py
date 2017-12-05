"""
start_servers.py

<Purpose>
  A simple script to start the three cloud-side Uptane servers:
    the Director (including its per-vehicle repositories)
    the Image Repository
    the Timeserver

  To run the demo services, run the following from the main uptane
  directory (which contains, for example, setup.py).
    python -i demo/start_servers.py

  That starts the services in an interactive mode (with a prompt from which
  you can manipulate them for the demonstrations).

"""
import threading
import demo
import demo.demo_timeserver as dt
import demo.demo_director as dd
import demo.demo_image_repo as di
from six.moves import xmlrpc_server
import readline, rlcompleter # for tab completion in interactive Python shell


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





if __name__ == '__main__':
  readline.parse_and_bind('tab: complete')
  main()
