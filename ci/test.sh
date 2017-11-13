#!/bin/bash

set -eux

if [[ "$TRAVIS_PYTHON_VERSION" == 2* ]]; then
  export PYTHONPATH="$PWD"
  py.test -v tests/
  flake8 --count grouper/
fi

if [[ "$TRAVIS_PYTHON_VERSION" == 3* ]]; then
  ./mypy.sh
fi
