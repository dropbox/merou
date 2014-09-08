#!/usr/bin/env python

import os

import setuptools
from distutils.core import setup

execfile('grouper/version.py')

with open('requirements.txt') as requirements:
    required = requirements.read().splitlines()

package_data = {}
def get_package_data(package, base_dir):
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirpath = dirpath[len(package)+1:]  # Strip package dir
        for filename in filenames:
            package_data.setdefault(package, []).append(os.path.join(dirpath, filename))
        for dirname in dirnames:
            get_package_data(package, dirname)

get_package_data("grouper", "grouper/fe/static")
get_package_data("grouper", "grouper/fe/templates")

kwargs = {
    "name": "grouper",
    "version": str(__version__),
    "packages": ["grouper", "grouper.fe", "grouper.api"],
    "package_data": package_data,
    "scripts": ["bin/grouper-api", "bin/grouper-fe"],
    "description": "Self-service Nested Group Management Server.",
    # PyPi, despite not parsing markdown, will prefer the README.md to the
    # standard README. Explicitly read it here.
    "long_description": open("README").read(),
    "author": "Gary M. Josack",
    "maintainer": "Gary M. Josack",
    "author_email": "gary@dropbox.com",
    "maintainer_email": "gary@dropbox.com",
    "license": "Apache",
    "install_requires": required,
    "url": "https://github.com/dropbox/grouper",
    "download_url": "https://github.com/dropbox/grouper/archive/master.tar.gz",
    "classifiers": [
        "Programming Language :: Python",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ]
}

setup(**kwargs)
