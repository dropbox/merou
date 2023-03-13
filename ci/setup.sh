#!/bin/bash

set -eux

wget 'https://chromedriver.storage.googleapis.com/2.37/chromedriver_linux64.zip'
echo "y" | unzip chromedriver_linux64.zip -d chromedriver

echo "Creating Database: $1"

if [ "$1" = 'mysql' ]; then
    mysql -e 'CREATE DATABASE merou CHARACTER SET utf8mb4;'
fi

pip3 install -r requirements.txt
pip3 install -r requirements-dev.txt
