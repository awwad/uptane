# uptanedemo
Early demonstration code for UPTANE.


## Instructions on use of the uptane demo code
### Installation
```
git clone https://github.com/awwad/uptanedemo
cd uptanedemo
virtualenv -p python3 —no-site-packages v3
source v3/bin/activate
cd ..
git clone -b multiroledelegation https://github.com/awwad/tuf.git tuf_for_uptane
cd tuf_for_uptane
pip install -r dev-requirements.txt
cd ../uptanedemo
```

### Running
Open two terminals, one for the server and one for the client.

*In the server terminal*:
```
cd uptanedemo
source v3/bin/activate
python
import uptane_tuf_server as uts
uts.clean_slate()
uts.host_repo()
```

*In the client terminal*:
```
cd uptanedemo
source v3/bin/activate
python
import uptane_tuf_client as utc
utc.clean_slate()
utc.update_client()
```
