from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib

from grouper.fe.template_util import get_template_env


def send_email(session, recipients, subject, template, settings, context):
    return send_async_email(
        session, recipients, subject, template, settings, context, send_after=datetime.utcnow())


def send_async_email(
        session, recipients, subject, template, settings, context, send_after, async_key=None):
    """Construct a message object from a template and schedule it

    This is the main email sending method to send out a templated email. This is used to
    asynchronously queue up the email for sending.

    Args:
        recipients (str or list(str)): Email addresses that will receive this mail. This
            argument is either a string (which might include comma separated email addresses)
            or it's a list of strings (email addresses).
        subject (str): Subject of the email.
        template (str): Name of the template to use.
        context (dict(str: str)): Context for the template library.
        settings (Settings): grouper.settings.Settings object grouper was run with
        send_after (DateTime): Schedule the email to go out after this point in time.
        async_key (str, optional): If you set this, it will be inserted into the db so that
            you can find this email in the future.

    Returns:
        Nothing.
    """
    # TODO(herb): get around circular depdendencies; long term remove call to
    # send_async_email() from grouper.models
    from grouper.models import AsyncNotification

    if isinstance(recipients, basestring):
        recipients = recipients.split(",")

    msg = get_email_from_template(recipients, subject, template, settings, context)

    for rcpt in recipients:
        notif = AsyncNotification(
            key=async_key,
            email=rcpt,
            subject=subject,
            body=msg.as_string(),
            send_after=send_after,
        )
        notif.add(session)
    session.commit()


def cancel_async_emails(session, async_key):
    """Cancel pending async emails by key

    If you scheduled an asynchronous email with an async_key previously, this method can be
    used to cancel any unsent emails.

    Args:
        async_key (str): The async_key previously provided for your emails.
    """
    # TODO(herb): get around circular depdendencies; long term remove call to
    # send_async_email() from grouper.models
    from grouper.models import AsyncNotification

    session.query(AsyncNotification).filter(
        AsyncNotification.key == async_key,
        AsyncNotification.sent == False
    ).update({"sent": True})


def process_async_emails(settings, session, now_ts, dry_run=False):
    """Send emails due before now

    This method finds and immediately sends any emails that have been scheduled to be sent before
    the now_ts.  Meant to be called from the background processing thread.

    Args:
        settings (Settings): The current Settings object for this application.
        session (Session): Object for db session.
        now_ts (datetime): The time to use as the cutoff (send emails before this point).
        dry_run (boolean, Optional): If True, do not actually send any email, just generate
            and return how many emails would have been sent.

    Returns:
        int: Number of emails that were sent.
    """
    # TODO(herb): get around circular depdendencies; long term remove call to
    # send_async_email() from grouper.models
    from grouper.models import AsyncNotification

    emails = session.query(AsyncNotification).filter(
        AsyncNotification.sent == False,
        AsyncNotification.send_after < now_ts,
    ).all()
    sent_ct = 0
    for email in emails:
        # For atomicity, attempt to set the sent flag on this email to true if
        # and only if it's still false.
        update_ct = session.query(AsyncNotification).filter(
            AsyncNotification.id == email.id,
            AsyncNotification.sent == False
        ).update({"sent": True})

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


def get_email_from_template(recipient_list, subject, template, settings, context):
    """Construct a message object from a template

    This creates the full MIME object that can be used to send an email with mixed HTML
    and text parts.

    FIXME(herb): we depend on the FE settings object right now. Since we're only
    getting called from the FE that's fine for now but we should clean this up.

    Args:
        recipient_list (list(str)): Email addresses that will receive this mail.
        subject (str): Subject of the email.
        template (str): Name of the template to use.
        settings (Settings): grouper.settings.Settings object grouper is run with
        context (dict(str: str)): Context for the template library.

    Returns:
        MIMEMultipart: Constructed object for the email message.
    """
    template_env = get_template_env()
    sender = settings["from_addr"]

    context["url"] = settings["url"]

    text_template = template_env.get_template(
        "email/{}_text.tmpl".format(template)
    ).render(**context)
    html_template = template_env.get_template(
        "email/{}_html.tmpl".format(template)
    ).render(**context)

    text = MIMEText(text_template, "plain")
    html = MIMEText(html_template, "html")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipient_list)
    msg.attach(text)
    msg.attach(html)

    return msg


def send_email_raw(settings, recipient_list, msg_raw):
    """Send raw email (from string)

    Given some recipients and the string version of a message, this sends it immediately
    through the SMTP library.

    Args:
        settings (Settings): Grouper Settings object for current run.
        recipient_list (list(str)): Email addresses to send this email to.
        msg_raw (str): The message to send. This should be the output of one of the methods
            that generates a MIMEMultipart object.

    Returns:
        Nothing.
    """
    if not settings["send_emails"]:
        logging.debug(msg_raw)
        return

    sender = settings["from_addr"]
    smtp = smtplib.SMTP(settings["smtp_server"])
    smtp.sendmail(sender, recipient_list, msg_raw)
    smtp.quit()
