#!/bin/bash

set -eux

if [[ "$TRAVIS_PYTHON_VERSION" == 2* ]]; then
  export PYTHONPATH="$PWD"
  export PATH="/usr/lib/chromium-browser:$PATH"
  py.test -v tests/
  flake8 --count grouper/
fi

if [[ "$TRAVIS_PYTHON_VERSION" == 3* ]]; then
  ./mypy.sh
fi
