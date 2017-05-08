# Demo Web Frontend Instructions

Note that code for the demo web frontend is in another repository,
[uptane_web_app](https://github.com/uptane/uptane_web_app]).


## Starting the Web Frontend
The other services and the web frontend need to be in sync. I will provide
instructions here as if none of them are running.
1. Start Director Repo, Image Repo, and Timeserver via console (Windows 1-3), as normal per the demo instructions in the [Uptane readme](../blob/develop/README.md).
2. Start the web frontend:
    `python3 web2py.py -a 'admin-password' -c server.crt -k server.key -i 127.0.0.1 -p 8000`
    - Note that this needs to be somewhere where Uptane is installed. For example, if Uptane is installed in a virtual environment, then source that virtual environment before running this command.
3. Open the web frontend in a browser, in two instances, one in private browsing (Or you can use two different browsers.), so that you can log in as two separate users simultaneously:
    - https://localhost:8000/UPTANE/default/index
    - Window 6: Login 1, accessing the Image Repository:
        - user: supplier1 / password: supplier1pass
    - Window 7: Login 2, accessing the Director Repository:
        - user: oem1 / password: oem1pass
    - In my case, I can run these two commands:
    `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --ignore-certificate-errors --app=https://localhost:8000/UPTANE/default/index/ --incognito`
    `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --ignore-certificate-errors --app=https://localhost:8000/UPTANE/default/index/`

**The following steps 4-6 are no longer necessary**, because the Director and Image
Repo now start with these settings. If the values in the web frontend's database
do not match these, however, follow these steps to correct them:
4. In the web frontend for the Director Repository (Window 7):
    - Delete any existing rows (vehicles)
5. In the web frontend for the Image Repository (Window 6):
    - (Make sure to have done the previous step first.)
    - Delete any existing rows (images)
    - Upload new images by filling in ECU Type, Update Version, and Update Image. The order of these doesn't matter. The filenames should match. Where the files are found doesn't matter, and neither do the contents really, but these files are included in uptane_web_app/applications/UPTANE/test_uploads/
        - INFO / 1.0 / INFO1.0.txt
        - BCU / 1.1 / BCU1.1.txt
        - BCU / 1.2 / BCU1.2.txt
        - TCU / 1.0 / TCU1.0.txt
        - TCU / 1.1 / TCU1.1.txt
        - TCU / 1.2 / TCU1.2.txt
6. In the web frontend for the Director Repository:
    - Click Add Record and fill this in:
        - VIN: democar
        - Note: <anything, doesn't matter>
        - ECU List: TCU-1.0, INFO-1.0, BCU-1.1
        - Click the Checkin Date field and choose a date and time (any time in the past or now)
        - Click Submit

The servers are now ready.


## Starting the Clients
1. Start a demo Primary client in a console:
    - python
    - import demo.demo_primary as dp
    - dp.clean_slate(vin='democar', ecu_serial='INFOdemocar')
2. Start a demo Secondary client in a console, when the Primary is done starting:
    - python
    - import demo.demo_secondary as ds
    - ds.clean_slate(vin='democar', ecu_serial='TCUdemocar')
    - Note that if the Primary port isn't 30701 (generally, if you were running multiple Primaries when the Primary started), you need the additional parameter primary_port=<port>. You can get that port from the messages produced by the Primary when it starts.


## Performing a normal update:
1. Assign an update to democar
    - In the Director Repository web frontend window:
        - Select the democar row and click View Vehicle Data
        - Uncheck TCU 1.0 and check TCU 1.1
        - Click Create Bundle
2. Instruct the demo Primary to fetch new images and metadata for the vehicle
    - In the Primary's console window:
        - dp.update_cycle()
3. When that is finished, instruct the Secondary to update from the Primary
    - In the Secondary's console window:
        - ds.update_cycle()
4. You should see an Updated banner





-----------------------------
# DEVELOPMENT NOTES

Modifying the behavior of the hack buttons

XMLRPC calls made in:
uptane_web_app/applications/UPTANE/controllers/default.py, around line 640


