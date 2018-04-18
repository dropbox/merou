import pytest

from fixtures import async_server, browser  # noqa: F401
from grouper.constants import AUDIT_SECURITY
from grouper.models.permission import Permission
from grouper.models.public_key import PublicKey
from pages.exceptions import NoSuchElementException
from pages.users import PublicKeysPage, UserViewPage
from plugins import group_ownership_policy
from tests.constants import SSH_KEY_1
from tests.fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401
from tests.fixtures import fe_app as app  # noqa: F401
from tests.url_util import url
from tests.util import add_member, grant_permission


def test_disable_last_owner(async_server, browser):
    fe_url = url(async_server, "/users/gary@a.co")
    browser.get(fe_url)

    page = UserViewPage(browser)

    page.click_disable_button()

    modal = page.get_disable_user_modal()
    modal.confirm()

    assert page.current_url.endswith("/users/gary@a.co")
    assert page.has_text(group_ownership_policy.EXCEPTION_MESSAGE)


def test_list_public_keys(async_server, browser, session, users, groups):
    permission = Permission.get_or_create(session, name=AUDIT_SECURITY, description="")[0]
    user = users["cbguder@a.co"]
    group = groups["group-admins"]

    add_member(group, user, role="owner")
    grant_permission(group, permission, "public_keys")

    # Pagination defaults to 100 keys per page
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
        key.add(session)

    session.commit()

    fe_url = url(async_server, "/users/public-keys")
    browser.get(fe_url)

    page = PublicKeysPage(browser)

    row = page.find_public_key_row("SHA256:0")
    assert row.user == user.username
    assert row.key_size == "4096"
    assert row.key_type == "ssh-rsa"

    assert page.find_public_key_row("SHA256:99")

    with pytest.raises(NoSuchElementException):
        page.find_public_key_row("SHA256:100")
