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

If you're going to be running the ASN.1 encoding scripts (not involved here), you'll also need to `pip install pyasn1`

### Running
Open three python shells, one for the supplier (main repository), one for the director, and one for a full verification client.

*In the Supplier (main repository) Python shell*:
```
import uptane_test_instructions as u
u.mainrepo()
```

*In the Director Python shell*:
```
import uptane_test_instructions as u
u.director()
```

*In the client Python shell*:
```
import uptane_test_instructions as u
u.client()
```
