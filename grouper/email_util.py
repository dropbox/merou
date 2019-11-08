from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import cast, TYPE_CHECKING

from grouper.models.async_notification import AsyncNotification
from grouper.models.audit_log import AuditLog
from grouper.models.base.constants import OBJ_TYPES_IDX
from grouper.models.user import User
from grouper.templating import BaseTemplateEngine

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.group import Group
    from grouper.models.group_edge import GroupEdge
    from grouper.settings import Settings
    from typing import Dict, Iterable, Optional, Set, Union

    Context = Dict[str, Union[bool, int, str, Optional[datetime]]]


class UnknownActorDuringExpirationException(Exception):
    """Cannot find actor for audit log entry for an expiring edge.

    When expiring an edge from a group, the edge represets a group rather than a user and neither
    the parent group nor the child group have owners, so the logic to try to find an actor for the
    audit log failed.
    """

    pass


class EmailTemplateEngine(BaseTemplateEngine):
    """Email-specific template engine."""

    def __init__(self, settings: Settings) -> None:
        # TODO(rra): Move email templates out of the grouper.fe package into their own.
        super().__init__(settings, "grouper.fe")


def send_email(
    session: Session,
    recipients: Iterable[str],
    subject: str,
    template: str,
    settings: Settings,
    context: Context,
) -> None:
    send_async_email(
        session, recipients, subject, template, settings, context, send_after=datetime.utcnow()
    )


def send_async_email(
    session: Session,
    recipients: Iterable[str],
    subject: str,
    template: str,
    settings: Settings,
    context: Context,
    send_after: datetime,
    async_key: Optional[str] = None,
) -> None:
    """Construct a message object from a template and schedule it

    This is the main email sending method to send out a templated email. This is used to
    asynchronously queue up the email for sending.

    Args:
        recipients: Email addresses that will receive this mail
        subject: Subject of the email.
        template: Name of the template to use.
        context: Context for the template library.
        settings: Grouper settings
        send_after: Schedule the email to go out after this point in time.
        async_key: If you set this, it will be inserted into the db so that you can find this email
            in the future.
    """
    msg = get_email_from_template(recipients, subject, template, settings, context)

    for rcpt in recipients:
        notif = AsyncNotification(
            key=async_key, email=rcpt, subject=subject, body=msg.as_string(), send_after=send_after
        )
        notif.add(session)
    session.commit()


def cancel_async_emails(session: Session, async_key: str) -> None:
    """Cancel pending async emails by key

    If you scheduled an asynchronous email with an async_key previously, this method can be
    used to cancel any unsent emails.

    Args:
        async_key: The async_key previously provided for your emails.
    """
    session.query(AsyncNotification).filter(
        AsyncNotification.key == async_key, AsyncNotification.sent == False
    ).update({"sent": True})


def process_async_emails(
    settings: Settings, session: Session, now_ts: datetime, dry_run: bool = False
) -> int:
    """Send emails due before now

    This method finds and immediately sends any emails that have been scheduled to be sent before
    the now_ts.  Meant to be called from the background processing thread.

    Args:
        settings: The current Settings object for this application.
        session: Object for db session.
        now_ts: The time to use as the cutoff (send emails before this point).
        dry_run: If True, do not actually send any email, just generate and return how many emails
            would have been sent.

    Returns:
        Number of emails that were sent.
    """
    emails = (
        session.query(AsyncNotification)
        .filter(AsyncNotification.sent == False, AsyncNotification.send_after < now_ts)
        .all()
    )
    sent_ct = 0
    for email in emails:
        # For atomicity, attempt to set the sent flag on this email to true if
        # and only if it's still false.
        update_ct = (
            session.query(AsyncNotification)
            .filter(AsyncNotification.id == email.id, AsyncNotification.sent == False)
            .update({"sent": True})
        )

        # If it's 0, someone else won the race. Bail.
        if update_ct == 0:
            continue

        try:
            if not dry_run:
                send_email_raw(settings, email.email, email.body)
            email.sent = True
            sent_ct += 1
        except smtplib.SMTPException:
            # Any sort of error with sending the email and we want to move on to
            # the next email. This email will be retried later.
            pass
    return sent_ct


def get_email_from_template(
    recipient_list: Iterable[str],
    subject: str,
    template: str,
    settings: Settings,
    context: Context,
) -> MIMEMultipart:
    """Construct a message object from a template

    This creates the full MIME object that can be used to send an email with mixed HTML
    and text parts.

    Args:
        recipient_list: Email addresses that will receive this mail.
        subject: Subject of the email.
        template: Name of the template to use.
        settings: grouper.settings.Settings object grouper is run with
        context: Context for the template library.

    Returns:
        Constructed object for the email message.
    """
    template_engine = EmailTemplateEngine(settings)
    sender = settings.from_addr

    context["url"] = settings.url

    text_template = template_engine.get_template("email/{}.txt".format(template)).render(**context)
    html_template = template_engine.get_template("email/{}.html".format(template)).render(
        **context
    )

    text = MIMEText(text_template, "plain", "utf-8")
    html = MIMEText(html_template, "html", "utf-8")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipient_list)
    msg.attach(text)
    msg.attach(html)

    if "references_header" in context:
        msg["References"] = msg["In-Reply-To"] = cast(str, context["references_header"])

    return msg


def send_email_raw(settings: Settings, recipient_list: Iterable[str], msg_raw: str) -> None:
    """Send raw email (from string)

    Given some recipients and the string version of a message, this sends it immediately
    through the SMTP library.

    Args:
        settings: Grouper Settings object for current run.
        recipient_list: Email addresses to send this email to.
        msg_raw: The message to send. This should be the output of one of the methods that
            generates a MIMEMultipart object.
    """
    if not settings.send_emails:
        logging.debug(msg_raw)
        return

    sender = settings.from_addr
    username = settings.smtp_username
    password = settings.smtp_password
    use_ssl = settings.smtp_use_ssl

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    smtp = smtp_cls(settings.smtp_server)

    if username:
        smtp.login(username, password)

    smtp.sendmail(sender, recipient_list, msg_raw)
    smtp.quit()


def notify_edge_expiration(settings: Settings, session: Session, edge: GroupEdge) -> None:
    """Send notification that an edge has expired.

    Handles email notification and audit logging.

    Args:
        settings: Grouper Settings object for current run.
        session: Object for db session.
        edge: The expiring edge.
    """
    # TODO(herb): get around circular depdendencies; long term remove call to
    # send_async_email() from grouper.models
    from grouper.models.group import Group

    # Pull data about the edge and the affected user or group.
    #
    # TODO(rra): The audit log currently has no way of representing a system action.  Everything
    # must be attributed to a user.  When expiring a user, use the user themselves as the actor for
    # the audit log entry.  When expiring a group, use an arbitrary owner of the group from which
    # they are expiring or, if that fails, an arbitrary owner of the group whose membership is
    # expiring.  If neither group has an owner, raise an exception.  This can all go away once the
    # audit log has a mechanism for recording system actions.
    group_name = edge.group.name
    if OBJ_TYPES_IDX[edge.member_type] == "User":
        user = User.get(session, pk=edge.member_pk)
        assert user
        actor_id = user.id
        member_name = user.username
        recipients = [member_name]
        member_is_user = True
    else:
        subgroup = Group.get(session, pk=edge.member_pk)
        assert subgroup, "Group edge refers to nonexistent group"
        parent_owners = edge.group.my_owners()
        if parent_owners:
            actor_id = list(parent_owners.values())[0].id
        else:
            child_owners = subgroup.my_owners()
            if child_owners:
                actor_id = list(child_owners.values())[0].id
            else:
                msg = "{} and {} both have no owners during expiration of {}'s membership".format(
                    group_name, subgroup.groupname, subgroup.groupname
                )
                raise UnknownActorDuringExpirationException(msg)
        member_name = subgroup.groupname
        recipients = subgroup.my_owners_as_strings()
        member_is_user = False

    # Log to the audit log.  How depends on whether a user's membership has expired or a group's
    # membership has expired.
    audit_data = {
        "action": "expired_from_group",
        "actor_id": actor_id,
        "description": "{} expired out of the group".format(member_name),
    }
    if member_is_user:
        assert user
        AuditLog.log(session, on_user_id=user.id, on_group_id=edge.group_id, **audit_data)
    else:
        # Make an audit log entry for both the subgroup and the parent group so that it will show
        # up in the FE view for both groups.
        assert subgroup
        AuditLog.log(session, on_group_id=edge.group_id, **audit_data)
        AuditLog.log(session, on_group_id=subgroup.id, **audit_data)

    # Send email notification to the affected people.
    email_context = {
        "group_name": group_name,
        "member_name": member_name,
        "member_is_user": member_is_user,
    }
    send_email(
        session=session,
        recipients=recipients,
        subject="Membership in {} expired".format(group_name),
        template="expiration",
        settings=settings,
        context=email_context,
    )


def notify_nonauditor_promoted(
    settings: Settings, session: Session, user: User, auditors_group: Group, group_names: Set[str]
) -> None:
    """Send notification that a nonauditor has been promoted to be an auditor.

    Handles email notification and audit logging.

    Args:
        settings: Grouper Settings object for current run.
        session: Object for db session.
        user: The user that has been promoted.
        auditors_group: The auditors group
        group_names: The audited groups in which the user was previously a non-auditor approver.
    """
    member_name = user.username
    recipients = [member_name]
    auditors_group_name = auditors_group.groupname

    audit_data = {
        "action": "nonauditor_promoted",
        "actor_id": user.id,
        "description": "Added {} to group {}".format(member_name, auditors_group_name),
    }
    AuditLog.log(session, on_user_id=user.id, on_group_id=auditors_group.id, **audit_data)

    email_context = {"auditors_group_name": auditors_group_name, "member_name": member_name}
    send_email(
        session=session,
        recipients=recipients,
        subject='Added as member to group "{}"'.format(auditors_group_name),
        template="nonauditor_promoted",
        settings=settings,
        context=email_context,
    )
