from datetime import timedelta

from sqlalchemy import or_

from grouper.constants import ILLEGAL_NAME_CHARACTER
from grouper.email_util import send_async_email
from grouper.models.async_notification import AsyncNotification
from grouper.settings import settings


def _get_unsent_expirations(session, now_ts):
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
    expiration_token, group_name, member_name = key.split(ILLEGAL_NAME_CHARACTER)
    assert expiration_token == "EXPIRATION"
    return group_name, member_name


def _expiration_key(group_name, member_name):
    async_key = ILLEGAL_NAME_CHARACTER.join(["EXPIRATION", group_name, member_name])
    return async_key


def add_expiration(session, expiration, group_name, member_name, recipients, member_is_user):
    async_key = _expiration_key(group_name, member_name)
    send_after = expiration - timedelta(settings.expiration_notice_days)
    email_context = {
        "expiration": expiration,
        "group_name": group_name,
        "member_name": member_name,
        "member_is_user": member_is_user,
    }
    from grouper.fe.settings import settings as fe_settings

    send_async_email(
        session=session,
        recipients=recipients,
        subject="expiration warning for membership in group '{}'".format(group_name),
        template="expiration_warning",
        settings=fe_settings,
        context=email_context,
        send_after=send_after,
        async_key=async_key,
    )


def cancel_expiration(session, group_name, member_name, recipients=None):
    async_key = _expiration_key(group_name, member_name)
    opt_arg = []
    if recipients is not None:
        exprs = [AsyncNotification.email == recipient for recipient in recipients]
        opt_arg.append(or_(*exprs))
    session.query(AsyncNotification).filter(
        AsyncNotification.key == async_key, AsyncNotification.sent == False, *opt_arg
    ).delete()
    session.commit()
