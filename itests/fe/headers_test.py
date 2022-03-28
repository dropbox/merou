from typing import TYPE_CHECKING
from urllib.request import urlopen

from grouper.fe.settings import FrontendSettings
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from tests.setup import SetupTest


def test_csp(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        r = urlopen(url(frontend_url, "/"))
        assert r.getcode() == 200
        headers = r.info()

    # Some basic sanity checks on the Content-Security-Policy.
    assert "Content-Security-Policy" in headers
    csp_header = str(headers["Content-Security-Policy"])
    csp_directive = {}
    for parameter in csp_header.split(";"):
        directive, value = parameter.strip().split(None, 1)
        csp_directive[directive] = value
    assert csp_directive["default-src"] == "'none'"
    assert "unsafe-inline" not in csp_directive["script-src"]
    assert "unsafe-inline" not in csp_directive["style-src"]
    assert "script" in csp_directive["require-sri-for"]
    assert "style" in csp_directive["require-sri-for"]

    # Make sure the cdnjs_prefix setting was honored.
    settings = FrontendSettings()
    assert settings.cdnjs_prefix in csp_directive["script-src"]


def test_referrer_policy(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        r = urlopen(url(frontend_url, "/"))
        assert r.getcode() == 200
        headers = r.info()
        assert str(headers["Referrer-Policy"]) == "same-origin"
