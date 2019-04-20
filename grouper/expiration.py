from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import or_

from grouper.constants import ILLEGAL_NAME_CHARACTER
from grouper.email_util import send_async_email
from grouper.models.async_notification import AsyncNotification
from grouper.settings import settings

if TYPE_CHECKING:
    from datetime import datetime
    from grouper.email_util import Context
    from grouper.model.base.session import Session
    from typing import Iterable, List, Optional, Tuple


def _get_unsent_expirations(session, now_ts):
    # type: (Session, datetime) -> List[Tuple[str, str, str]]
    """Get upcoming group membership expiration notifications as a list of (group_name,
    member_name, email address) tuples.
    """
    tuples = []
    emails = (
        session.query(AsyncNotification)
        .filter(
            AsyncNotification.key.like("EXPIRATION%"),
            AsyncNotification.sent == False,
            AsyncNotification.send_after < now_ts,
        )
        .all()
    )
    for email in emails:
        group_name, member_name = _expiration_key_data(email.key)
        user = email.email
        tuples.append((group_name, member_name, user))
    return tuples


def _expiration_key_data(key):
    # type: (str) -> Tuple[str, str]
    expiration_token, group_name, member_name = key.split(ILLEGAL_NAME_CHARACTER)
    assert expiration_token == "EXPIRATION"
    return group_name, member_name


def _expiration_key(group_name, member_name):
    # type: (str, str) -> str
    async_key = ILLEGAL_NAME_CHARACTER.join(["EXPIRATION", group_name, member_name])
    return async_key


def add_expiration(
    session,  # type: Session
    expiration,  # type: datetime
    group_name,  # type: str
    member_name,  # type: str
    recipients,  # type: List[str]
    member_is_user,  # type: bool
):
    # type: (...) -> None
    async_key = _expiration_key(group_name, member_name)
    send_after = expiration - timedelta(settings().expiration_notice_days)
    email_context = {
        "expiration": expiration,
        "group_name": group_name,
        "member_name": member_name,
        "member_is_user": member_is_user,
    }  # type: Context

    send_async_email(
        session=session,
        recipients=recipients,
        subject="expiration warning for membership in group '{}'".format(group_name),
        template="expiration_warning",
        settings=settings(),
        context=email_context,
        send_after=send_after,
        async_key=async_key,
    )


def cancel_expiration(session, group_name, member_name, recipients=None):
    # type: (Session, str, str, Optional[Iterable[str]]) -> None
    async_key = _expiration_key(group_name, member_name)
    opt_arg = []
    if recipients is not None:
        exprs = [AsyncNotification.email == recipient for recipient in recipients]
        opt_arg.append(or_(*exprs))
    session.query(AsyncNotification).filter(
        AsyncNotification.key == async_key, AsyncNotification.sent == False, *opt_arg
    ).delete()
    session.commit()
