#!/bin/bash -eu

# Run with bzl --build-image build_tools/docker/drbe-v1 cexec ./build.sh

if [ ! -d /dbxce ]; then
    echo "Run with: bzl --build-image build_tools/docker/drbe-v1 cexec ./build.sh"
    exit 1
fi

# XXX: this is bad but not too bad
sudo apt-get update
# this libary is in drte but we are missing the headers
sudo apt-get install --force-yes -y libffi-dev
# Make the headers avaliable in the default location so we don't need
# pkg-config
sudo mkdir -p /usr/include/libffi
sudo ln -s /usr/include/x86_64-linux-gnu/ffi.h /usr/include/libffi/ffi.h
sudo ln -s /usr/include/x86_64-linux-gnu/ffitarget.h /usr/include/libffi/ffitarget.h
sudo mkdir -p /usr/lib/libffi
sudo ln -s /usr/drte/v1/lib/x86_64-linux-gnu/libffi.so.6 /usr/lib/libffi/libffi.so.6
sudo ln -s /usr/drte/v1/lib/x86_64-linux-gnu/libffi.so.6.0.0 /usr/lib/libffi/libffi.so.6.0.0

VERSION=5.6.0

export LDFLAGS="-Wl,-rpath=/usr/drte/v1/lib/x86_64-linux-gnu,-I/usr/drte/v1/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2,--enable-new-dtags"
export CC=/usr/bin/gcc-4.9

rm -rf pypy2-v$VERSION-src
tar xf pypy2-v$VERSION-src.tar.bz2
patch -p 1 -d pypy2-v$VERSION-src < distutils_cc.patch
patch -p 1 -d pypy2-v$VERSION-src < arcane-package-loading-behavior.patch
patch -p 1 -d pypy2-v$VERSION-src < fix_library_file.patch

pushd pypy2-v$VERSION-src/pypy/goal
python  ../../rpython/bin/rpython --opt=jit --no-shared targetpypystandalone.py --withoutmod-pyexpat
popd

pushd pypy2-v$VERSION-src/pypy/tool/release
./package.py --without-tk --without-gdbm --targetdir  ../../../../pypy-5.6.0-dbx8.tar.bz2
popd
