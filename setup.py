"""
<Program Name>
  setup.py

<Purpose>
  BUILD SOURCE DISTRIBUTION

  The following shell command generates a TUF source archive that can be
  distributed to other users.  The packaged source is saved to the 'dist'
  folder in the current directory.
  
  $ python setup.py sdist


  INSTALLATION OPTIONS
   
  pip - installing and managing Python packages (recommended):

  # Installing from Python Package Index (https://pypi.python.org/pypi).
  $ pip install uptane

  # Installing from local source archive.
  $ pip install <path to archive>
  
  # Or from the root directory of the unpacked archive.
  $ pip install . 
    

  Alternate installation options:

  Navigate to the root directory of the unpacked archive and
  run one of the following shell commands:
 
  Install to the global site-packages directory.
  $ python setup.py install

  Install to the user site-packages directory.
  $ python setup.py install --user

  Install to a chosen directory.
  $ python setup.py install --home=<directory>

  
  Note: The last two installation options may require modification of
  Python's search path (i.e., 'sys.path') or updating an OS environment
  variable.  For example, installing to the user site-packages directory might
  result in the installation of TUF scripts to '~/.local/bin'.  The user may
  then be required to update his $PATH variable:
  $ export PATH=$PATH:~/.local/bin
"""
from __future__ import unicode_literals
from io import open

import os
from setuptools import setup
from setuptools import find_packages

if os.path.exists('README.md'):
  with open('README.md') as file_object:
    long_description = file_object.read()
else:
  long_description = "Check https://github.com/uptane/uptane/ for details"


setup(
  name = 'uptane',
  version = '0.1.0',
  description = 'A secure updater framework for vehicles employing The ' + \
      'Update Framework',
  long_description = long_description,
  author = 'https://uptane.umtri.umich.edu',
  author_email = 'uptane@googlegroups.com',
  url = 'https://uptane.umtri.umich.edu',
  keywords = 'update updater secure authentication key compromise ' + \
      'revocation automotive automobile vehicle software updates',
  classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Natural Language :: English',
    'Operating System :: POSIX',
    'Operating System :: POSIX :: Linux',
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: Microsoft :: Windows',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: Implementation :: CPython',
    'Topic :: Security',
    'Topic :: Software Development'
  ],
  install_requires = ['iso8601', 'tuf', 'six', 'canonicaljson'],
  test_suite="tests.runtests",
  packages = find_packages(exclude=['tests']),
  scripts = []
)
