"""
start_servers.py

<Purpose>
  A simple script to start the three cloud-side Uptane servers:
    the Director (including its per-vehicle repositories)
    the Image Repository
    the Timeserver

  To run the demo services in non-interactive mode, run:
    python start_servers.py

  To run the demo services in interactive mode, run:
    python -i -c "from demo.start_servers import *; main()"

  In either mode, the demo services will respond to commands sent via XMLRPC.

"""
import threading
import demo
import demo.demo_timeserver as dt
import demo.demo_director as dd
import demo.demo_image_repo as di
from six.moves import xmlrpc_server


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
  main()
