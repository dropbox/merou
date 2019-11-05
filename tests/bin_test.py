"""Check that the bin wrappers load properly."""

import subprocess
import sys

from tests.path_util import bin_env, src_path


def test_api():
    # type: () -> None
    bin_path = src_path("bin", "grouper-api")
    out = subprocess.check_output([sys.executable, bin_path, "--help"], env=bin_env())
    assert out.decode().startswith("usage: grouper-api")


def test_background():
    # type: () -> None
    bin_path = src_path("bin", "grouper-background")
    out = subprocess.check_output([sys.executable, bin_path, "--help"], env=bin_env())
    assert out.decode().startswith("usage: grouper-background")


def test_ctl():
    # type: () -> None
    bin_path = src_path("bin", "grouper-ctl")
    out = subprocess.check_output([sys.executable, bin_path, "--help"], env=bin_env())
    assert out.decode().startswith("usage: grouper-ctl")


def test_fe():
    # type: () -> None
    bin_path = src_path("bin", "grouper-fe")
    out = subprocess.check_output([sys.executable, bin_path, "--help"], env=bin_env())
    assert out.decode().startswith("usage: grouper-fe")
