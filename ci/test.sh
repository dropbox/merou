#!/bin/bash

set -eux

if [[ "$TRAVIS_PYTHON_VERSION" == 2* ]]; then
    export PATH="${PWD}/chromedriver:$PATH"
    py.test -x -v
fi

if [[ "$TRAVIS_PYTHON_VERSION" == 3* ]]; then
    ./mypy.sh
    black --check .
    flake8 --count
fi
