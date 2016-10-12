# uptanedemo
Early demonstration code for UPTANE. Python 3 is preferred during development.

## Instructions on use of the uptane demo code
### Installation
(As usual, virtual environments are recommended for development and testing, but not necessary.)

Run the following:
```
pip install cffi==1.7.0 pycrypto==2.6.1 pynacl==1.0.1 cryptography
pip install git+git://github.com/awwad/tuf.git@pinning
```

If you're going to be running the ASN.1 encoding scripts, you'll also need to `pip install pyasn1`

### Running
The code below is intended to be run IN FIVE PYTHON SHELLS:
- One for the Main Repository ("supplier"), speaking HTTP
- One for the Director Repository, speaking HTTP
- One for the Director Service, speaking XMLRPC (receives manifests)
- One for the Timeserver, speaking XMLRPC (receives requests for signed times)
- One for a client to perform full metadata verification

Each shell should be run in a python environment (the same environment is
fine) that has the awwad/tuf:pinning version of TUF installed (see [above](#installation)).

*WINDOW 1: the Supplier repository*
```
import uptane_test_instructions as u
u.ServeMainRepo()
```

*WINDOW 2: the Director repository*
```
import uptane_test_instructions as u
u.ServeDirectorRepo()
```

*WINDOW 3: the Director service (receives manifests)*
```
import uptane.director.director as director
d = director.Director()
d.listen()
```

*WINDOW 4: the Timeserver service:*
```
import uptane.director.timeserver as timeserver
timeserver.listen(use_new_keys=True)
```

*WINDOW 5: In the client's window:*
(ONLY AFTER THE OTHERS HAVE FINISHED STARTING UP AND ARE HOSTING)
```
import uptane_test_instructions as u
u.client()
```

