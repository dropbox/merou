#!/bin/bash

set -eux

if [[ "$TRAVIS_PYTHON_VERSION" == 2* ]]; then
  export PYTHONPATH="$PWD"
  export PATH="${PWD}/chromedriver:$PATH"

  py.test -x -v tests/
  py.test -x -v itests/
  flake8 --count grouper/
fi

if [[ "$TRAVIS_PYTHON_VERSION" == 3* ]]; then
  ./mypy.sh
fi
