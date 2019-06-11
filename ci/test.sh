#!/bin/bash

set -eux

# Add chromedriver to PATH, manually installed by ci/setup.sh.
export PATH="${PWD}/chromedriver:$PATH"

# Tests run under Python 2.  Run once with SQLite and again with MySQL.
if [[ "$TRAVIS_PYTHON_VERSION" == 2* ]]; then
    MEROU_TEST_DATABASE='mysql://travis:@localhost/merou' pytest -x -v
    pytest -x -v
fi

# Tests run under Python 3.  Run once with SQLite and again with MySQL, and
# also do static analysis.
if [[ "$TRAVIS_PYTHON_VERSION" == 3* ]]; then
    MEROU_TEST_DATABASE='mysql://travis:@localhost/merou' pytest -x -v
    pytest -x -v
    mypy .
    mypy --py2 .
    black --check .
    flake8
fi
