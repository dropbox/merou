=====
merou
=====

.. image:: https://travis-ci.org/dropbox/merou.svg?branch=master
    :alt: Build Status
    :target: https://travis-ci.org/dropbox/merou

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :alt: Code Style: Black
    :target: https://github.com/ambv/black

Description
-----------

Merou is an application to allow users to create and manage
memberships to their own groups.  It supports both Python 2.7 and Python 3
(only tested with Python 3.7 currently).  Python 3 support is new and may
still have some glitches.

**Note**: We renamed the project to avoid `a namespace conflict
<https://github.com/Internet2/grouper>`_, but it isn't reflected in the
codebase yet.

To get updates about Merou, `join our mailing list
<https://goo.gl/forms/mbw70IQ26Mj188pi1>`_.

Installation
------------

Standard Python package installation instructions apply. You will need
development headers for MySQL and Python 3 available.

On Debian-based systems:

.. code:: bash

    apt-get install libmysqlclient-dev libpython3-dev
    pip3 install -e git+https://github.com/dropbox/merou#egg=grouper

Alternately, you can install libpython2.7-dev and use pip2 to run Grouper
under Python 2.

Next you need to configure grouper to find a SQL-style backing database
and stand up processes to serve the read-write web UI and read-only
programmatic API. There's an sample configuration file, suitable for
local development and testing, in ``config/dev.yaml``.


Running a Test instance
-----------------------

Grouper runs behind a reverse proxy that handles authentication and so
expects a valid, authenticated, user account. I've included a test proxy
for running on development instances.

Creating a development instance:

.. code:: bash

    export PYTHONPATH=$(pwd)
    export GROUPER_SETTINGS=$(pwd)/config/dev.yaml

    # Setup the database.
    bin/grouper-ctl sync_db

    ## You can either run all the various servers and the reverse-proxy
    ## via a helper script:
    tools/run-dev --user $USER@example.com

    ## Or separately:
    # Run the development reverse proxy
    bin/grouper-ctl -vv user_proxy $USER@example.com

    # Run the frontend server
    bin/grouper-fe -vv

    # Run the graph/api server
    bin/grouper-api -vv


Setting up the first groups and permissions
-------------------------------------------

In order to bootstrap your new Grouper environment, you will want to
create a user for yourself and add it to the ``grouper-administrators``
group.

.. code:: bash

    export PYTHONPATH=$(pwd)
    export GROUPER_SETTINGS=$(pwd)/config/dev.yaml

    bin/grouper-ctl -vv\
        user create $USER@example.com

    # Give the user administrative access to the Grouper instance
    bin/grouper-ctl -vv \
        group add_member --owner grouper-administrators $USER@example.com


Running the tests
-----------------

Some tests require a recent (>= 2.31) version of chromium-driver, which
can be installed via apt or Homebrew:

.. code:: bash

    apt install chromium-driver

(This may be called chromium-chromedriver in older versions.)  Once
chromium-driver is installed, the tests can be run using pytest:

.. code:: bash

    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pytest
    flake8
    mypy .

`requirements-dev.txt` assumes you are using Python 3. If you are instead
using Python 2, use `requirements-dev2.txt`, which will skip installing
mypy and black (both of which are only available under Python 3).

If you see test failures and suspect incompatible library versions (e.g.,
an existing tornado install at a different major release than that in our
`requirements.txt`), then you can try using a virtual environment.

.. code:: bash

    $ virtualenv ~/merou-venv -p /usr/bin/python3
    $ source ~/merou-venv/bin/activate
    (merou-venv) $ pip install -r requirements.txt
    (merou-venv) $ pip install -r requirements-dev.txt
    (merou-venv) $ pytest
    (merou-venv) $ deactivate
    $

All Merou code is formatted with black, which is installed by the
`requirements-dev.txt` requirements file for Python 3. After installation,
you can reformat all source code with:

.. code:: bash

    black .

All new code must be formatted with the version of black indicated in
`requirements-dev.txt` in order to pass Travis CI tests.
