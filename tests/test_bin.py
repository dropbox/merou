import subprocess


def test_api():
    out = subprocess.check_output(["bin/grouper-api", "--help"])
    assert out.startswith("usage: grouper-api")


def test_ctl():
    out = subprocess.check_output(["bin/grouper-ctl", "--help"])
    assert out.startswith("usage: grouper-ctl")


def test_fe():
    out = subprocess.check_output(["bin/grouper-fe", "--help"])
    assert out.startswith("usage: grouper-fe")
