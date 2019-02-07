#!/bin/bash

set -eux

if [[ "$TRAVIS_PYTHON_VERSION" == 2* ]]; then
  export PYTHONPATH="$PWD"
  export PATH="${PWD}/chromedriver:$PATH"

  py.test -x -v itests tests
fi

if [[ "$TRAVIS_PYTHON_VERSION" == 3* ]]; then
  ./mypy.sh
  black --check .
  flake8 --count grouper itests plugins tests
fi
