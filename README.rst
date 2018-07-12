=======
merou
=======

.. image:: https://travis-ci.org/dropbox/merou.png?branch=master
    :alt: Build Status
    :target: https://travis-ci.org/dropbox/merou


Description
-----------

Merou is an application to allow users to create and manage
memberships to their own groups.

**Note**: We recently renamed the project to avoid 
`a namespace conflict <https://github.com/Internet2/grouper>`_,
but it isn't reflected in the codebase yet.

To get updates about Merou, `join our mailing list <https://goo.gl/forms/mbw70IQ26Mj188pi1>`_.

Installation
------------

Standard Python package installation instructions apply. You will need
development headers for MySQL and Python 2 available.

On Debian-based systems:

.. code:: bash

    apt-get install libmysqlclient-dev libpython2.7-dev
    pip install -e git+https://github.com/dropbox/merou#egg=grouper

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

Some tests require a recent (>= 2.31) version of chromedriver, which can be
installed via apt or Homebrew:

.. code:: bash

    apt install chromium-chromedriver

Once chromedriver is installed, the tests can be run using pytest:

.. code:: bash

    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    py.test tests
    py.test itests
