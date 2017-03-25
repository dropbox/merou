#!/bin/bash -eu
rm -f pypy2-v5.6.0-src.tar.bz2
wget https://bitbucket.org/pypy/pypy/downloads/pypy2-v5.6.0-src.tar.bz2
sha256sum -c sha256.sums
