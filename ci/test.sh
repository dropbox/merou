#!/bin/bash

set -eux

# Add chromedriver to PATH, manually installed by ci/setup.sh.
export PATH="${PWD}/chromedriver:$PATH"

# Pick the database based on the DB setting.  For the SQLite build, also run
# static analysis (no need to run it twice).
case "$1" in
    mysql)
        MEROU_TEST_DATABASE='mysql://travis:@localhost/merou?charset=utf8mb4' pytest -x -v
        ;;
    sqlite)
        pytest -x -v
        mypy .
        black --check .
        flake8
        ;;
    *)
        echo "Unknown DB setting: $1" >&2
        exit 1
        ;;
esac
