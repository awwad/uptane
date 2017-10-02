## Writing new sample client data

See `demo/reencode_samples.py`


## Writing new sample repository data (including .zip)

Start by merging (into a working branch, not develop!) or cherry-picking the
awwad/long_expiry branch into Uptane's TUF fork so that generated metadata
samples have a 20-year expiry.

Note that on OS X, this required the use of a zip editor, BetterZip, to make
sure that the director and imagerepo directories in the zip weren't contained
in an extraneous additional directory, full_metadata_archive.

- In each mode, DER and JSON:
    - Start the demo ImageRepo and demo Director and keep them running.
    Wait until they've finished starting up.
    - Start the demo Primary and run dp.update_cycle(). Wait until it's done.
    - Go into the demo Primary's temp directory and pluck the .der and .json
    files from the director and imagerepo directories in it and put them in the
    appropriate directory in
    samples/metadata_samples_long_expiry/initial_w_no_update/full_metadata_archive/ (director and imagerepo)
    - Put the director_targets.* into
    samples/metadata_samples_long_expiry/initial_w_no_update/
    - In the demo Director, enter:
        - `dd.add_target_to_director('demo/images/TCU1.1.txt', 'TCU1.1.txt', 'democar', 'TCUdemocar'); dd.write_to_live()`
    - In the demo Primary, enter:
        - `dp.update_cycle()` and wait until it's done.
    - Go into the demo Primary's temp directory and pluck the .der and .json
    files from the director and imagerepo directories in it and put them in the
    appropriate directory in
    samples/metadata_samples_long_expiry/update_to_one_ecu/full_metadata_archive/ (director and imagerepo)
    - Put `director_targets.*` into
    samples/metadata_samples_long_expiry/initial_w_no_update/
- Zip `samples/metadata_samples_long_expiry/initial_w_no_update/full_metadata_archive`
- Zip `samples/metadata_samples_long_expiry/update_to_one_ecu/full_metadata_archive`
- Edit the zips to make sure that the zips contain two folders, director and
imagerepo, and not, instead, those two folders in another folder (e.g.
"full_metadata_archive"). I used BetterZip on OS X.
- Remember to strip the long_expiry code back out.
(git reset --hard or checkout or whatever is appropriate)
