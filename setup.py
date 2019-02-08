#!/usr/bin/env python2

import os

from setuptools import setup

# this defines __version__ for use below without assuming grouper is in the
# path or importable during build
with open("grouper/version.py", "r") as version:
    code = compile(version.read(), "grouper/version.py", "exec")
    exec(code)

# Installation requirements.
with open("requirements.txt") as requirements:
    required = requirements.read().splitlines()

# Test suite requirements.
with open("requirements-dev.txt") as requirements:
    test_required = requirements.read().splitlines()

package_data = {}


def get_package_data(package, base_dir):
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirpath = dirpath[len(package) + 1 :]  # Strip package dir
        for filename in filenames:
            package_data.setdefault(package, []).append(os.path.join(dirpath, filename))
        for dirname in dirnames:
            get_package_data(package, dirname)


get_package_data("grouper", "grouper/fe/static")
get_package_data("grouper", "grouper/fe/templates")

kwargs = {
    "name": "grouper",
    "version": str(__version__),  # noqa
    "packages": ["grouper", "grouper.fe", "grouper.api", "grouper.ctl"],
    "package_data": package_data,
    "scripts": ["bin/grouper-api", "bin/grouper-fe", "bin/grouper-ctl"],
    "description": "Self-service Nested Group Management Server.",
    # TODO(lfaraone): Check whether this is still needed for PyPI
    "long_description": open("README.rst").read(),
    "author": "Gary M. Josack",
    "maintainer": "Gary M. Josack",
    "author_email": "gary@dropbox.com",
    "maintainer_email": "gary@dropbox.com",
    "license": "Apache",
    "install_requires": required,
    "setup_requires": ["pytest-runner"],
    "tests_require": test_required,
    "url": "https://github.com/dropbox/grouper",
    "download_url": "https://github.com/dropbox/grouper/archive/master.tar.gz",
    "classifiers": [
        "Programming Language :: Python",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
}

setup(**kwargs)
