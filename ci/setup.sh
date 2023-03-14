#!/bin/bash

set -eux

wget 'https://chromedriver.storage.googleapis.com/2.37/chromedriver_linux64.zip'
echo "y" | unzip chromedriver_linux64.zip -d chromedriver

echo "Creating Database: $1"

pip3 install -r requirements.txt
pip3 install -r requirements-dev.txt
