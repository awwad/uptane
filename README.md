# uptanedemo
Early demonstration code for UPTANE.


Instructions on use of the uptane demo code
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