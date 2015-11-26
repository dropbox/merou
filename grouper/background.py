from datetime import datetime
import logging
from threading import Thread
from time import sleep

from sqlalchemy.exc import OperationalError

from grouper.email_util import process_async_emails
from grouper.models import get_db_engine, Session
from grouper.util import get_database_url


class BackgroundThread(Thread):
    """Background thread for running periodic tasks.

    Currently, this sends asynchronous mail messages and handles edge expiration and notification.

    This class thread will exist on multiple servers in a standard Grouper production environment
    so we need to ensure that it's race-safe.
    """
    def __init__(self, settings, sentry_client, *args, **kwargs):
        """Initialize new BackgroundThread

        Args:
            settings (Settings): The current Settings object for this application.
        """
        self.settings = settings
        Thread.__init__(self, *args, **kwargs)

    def capture_exception(self):
        if self.sentry_client:
            self.sentry_client.captureException()

    def run(self):
        while True:
            logging.debug("Sending emails...")
            try:
                session = Session()
                process_async_emails(self.settings, session, datetime.utcnow())
                session.commit()
                session.close()
            except OperationalError:
                Session.configure(bind=get_db_engine(get_database_url(self.settings)))
                logging.critical("Failed to connect to database.")
                self.capture_exception()
            except:
                self.capture_exception()
                raise

            sleep(60)
