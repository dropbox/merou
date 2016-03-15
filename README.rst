=======
grouper
=======

.. image:: https://travis-ci.org/dropbox/grouper.png?branch=master
    :alt: Build Status
    :target: https://travis-ci.org/dropbox/grouper


Description
-----------

Grouper is an application to allow users to create and manage
memberships to their own groups.

**Warning**: This project is still very much in flux and likely
to have schema changes that will need to be manually applied.

Installation
------------

Standard Python package installation instructions apply. You will need
development headers for MySQL and Python 2 available.

On Debian-based systems:

.. code:: bash

    apt-get install libmysqlclient-dev libpython2.7-dev
    pip install -e git+https://github.com/dropbox/grouper#egg=grouper

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
