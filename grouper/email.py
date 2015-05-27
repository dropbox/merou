from datetime import datetime
import logging
import smtplib
from threading import Thread
from time import sleep

from grouper.models import get_db_engine, Session, AsyncNotification
from grouper.util import get_database_url, send_email_raw

from sqlalchemy.exc import OperationalError


class SendEmailThread(Thread):
    """Background thread for sending emails from the async pool

    This class thread will exist on multiple servers in a standard Grouper production environment
    so we need to ensure that it's race-safe.
    """
    def __init__(self, settings, *args, **kwargs):
        """Initialize new SendEmailThread

        Args:
            settings (Settings): The current Settings object for this application.
        """
        self.settings = settings
        Thread.__init__(self, *args, **kwargs)

    def send_emails(self, session, now_ts, dry_run=False):
        """Send emails due before now

        This method finds and immediately sends any emails that have been scheduled to be sent
        before the now_ts.

        Args:
            session (Session): Object for db session.
            now_ts (datetime): The time to use as the cutoff (send emails before this point).
            dry_run (boolean, Optional): If True, do not actually send any email, just generate
                and return how many emails would have been sent.

        Returns:
            int: Number of emails that were sent.
        """
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
                    send_email_raw(self.settings, email.email, email.body)
                email.sent = True
                sent_ct += 1
            except smtplib.SMTPException:
                # Any sort of error with sending the email and we want to move on to
                # the next email. This email will be retried later.
                pass
        return sent_ct

    def run(self):
        while True:
            logging.debug("Sending emails...")
            try:
                session = Session()
                self.send_emails(session, datetime.utcnow())
                session.commit()
                session.close()
            except OperationalError:
                Session.configure(bind=get_db_engine(get_database_url(self.settings)))
                logging.critical("Failed to connect to database.")
            sleep(60)
