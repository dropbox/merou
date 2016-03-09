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

New versions will be updated to PyPI pretty regularly so it should be as
easy as:

.. code:: bash

    pip install grouper

Next you need to configure grouper to find a SQL-style backing database and
stand up processes to serve the read-write web UI and read-only programmatic
API.


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

There are three administrative flags, corresponding to full authority to
administer groups, users, and permissions. These flags can be set for any
account and grant powers independent of the usual way and are given out manually
via the following commands:

.. code:: bash

    export PYTHONPATH=$(pwd)
    export GROUPER_SETTINGS=$(pwd)/config/dev.yaml

    bin/grouper-ctl -vv\
        user create $USER@example.com

    # Give the user administrative access to the Grouper instance
    bin/grouper-ctl -vv \
        group add_member --owner grouper-administrators $USER@example.com
