#!/bin/bash

set -eux

# Add chromedriver to PATH, manually installed by ci/setup.sh.
export PATH="${PWD}/chromedriver:$PATH"

# `Run once with SQLite and again with MySQL, and also do static analysis.
MEROU_TEST_DATABASE='mysql://travis:@localhost/merou' pytest -x -v
pytest -x -v
mypy .
black --check .
flake8
