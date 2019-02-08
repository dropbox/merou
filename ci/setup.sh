#!/bin/bash

set -eux

if [[ "$TRAVIS_PYTHON_VERSION" == 2* ]]; then
    wget 'https://chromedriver.storage.googleapis.com/2.37/chromedriver_linux64.zip'
    unzip chromedriver_linux64.zip -d chromedriver

    mysql -e 'CREATE DATABASE merou;'

    pip install -r requirements-dev.txt
    pip install -r requirements.txt
fi

if [[ "$TRAVIS_PYTHON_VERSION" == 3* ]]; then
    pip install -r requirements3.txt
fi
