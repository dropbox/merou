from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from grouper.constants import AUDIT_SECURITY, USER_ADMIN
from grouper.models.public_key import PublicKey
from grouper.models.user import User
from itests.pages.users import PublicKeysPage, UserViewPage
from itests.setup import frontend_server
from plugins import group_ownership_policy
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_escaped_at_sign(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/users/gary%40a.co"))
        page = UserViewPage(browser)
        assert page.subheading == "gary@a.co"


def test_disable_last_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.add_user_to_group("cbguder@a.co", "admins")
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/users/gary@a.co"))
        page = UserViewPage(browser)

        page.click_disable_button()
        modal = page.get_disable_user_modal()
        modal.confirm()

        assert page.current_url.endswith("/users/gary@a.co")
        assert page.has_alert(group_ownership_policy.EXCEPTION_MESSAGE)


def test_list_public_keys(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("cbguder@a.co", "admins")
        setup.grant_permission_to_group(AUDIT_SECURITY, "public_keys", "admins")

    user = User.get(setup.session, name="cbguder@a.co")
    assert user

    # Pagination defaults to 100 keys per page
    with setup.transaction():
        for i in range(120):
            key = PublicKey(
                user=user,
                public_key="KEY:{}".format(i),
                fingerprint="MD5:{}".format(i),
                fingerprint_sha256="SHA256:{}".format(i),
                key_size=4096,
                key_type="ssh-rsa",
                comment="",
            )
            key.add(setup.session)

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/users/public-keys"))
        page = PublicKeysPage(browser)

        row = page.find_public_key_row("SHA256:0")
        assert row.user == user.username
        assert row.key_size == "4096"
        assert row.key_type == "ssh-rsa"

        assert page.find_public_key_row("SHA256:99")

        with pytest.raises(NoSuchElementException):
            page.find_public_key_row("SHA256:100")


def test_user_view_hides_aliased_permissions(
    tmpdir: LocalPath, setup: SetupTest, browser: Chrome
) -> None:
    with setup.transaction():
        setup.add_user_to_group("oliver@a.co", "sad-team")
        setup.grant_permission_to_group("owner", "sad-team", "sad-team")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/users/oliver@a.co"))
        page = UserViewPage(browser)

        assert len(page.find_permission_rows("owner", "sad-team")) == 1
        assert page.find_permission_rows("ssh", "owner=sad-team") == []
        assert page.find_permission_rows("sudo", "sad-team") == []
