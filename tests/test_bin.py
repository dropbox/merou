import subprocess

from path_util import src_path


def test_api():
    bin_path = src_path("bin", "grouper-api")
    out = subprocess.check_output([bin_path, "--help"])
    assert out.startswith("usage: grouper-api")


def test_background():
    bin_path = src_path("bin", "grouper-background")
    out = subprocess.check_output([bin_path, "--help"])
    assert out.startswith("usage: grouper-background")


def test_ctl():
    bin_path = src_path("bin", "grouper-ctl")
    out = subprocess.check_output([bin_path, "--help"])
    assert out.startswith("usage: grouper-ctl")


def test_fe():
    bin_path = src_path("bin", "grouper-fe")
    out = subprocess.check_output([bin_path, "--help"])
    assert out.startswith("usage: grouper-fe")
