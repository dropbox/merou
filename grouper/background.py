from datetime import datetime
import logging
from threading import Thread
from time import sleep

from sqlalchemy import and_
from sqlalchemy.exc import OperationalError

from grouper.email_util import notify_edge_expiration, process_async_emails
from grouper.models import get_db_engine, GroupEdge, Session
from grouper.perf_profile import prune_old_traces
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
        self.sentry_client = sentry_client
        Thread.__init__(self, *args, **kwargs)

    def capture_exception(self):
        if self.sentry_client:
            self.sentry_client.captureException()

    def expire_edges(self, session):
        """Mark expired edges as inactive and log to the audit log.

        Edges are immediately excluded from the permission graph once they've
        expired, but we also want to note the expiration in the audit log and send
        an email notification.  This function finds all expired edges, logs the
        expiration to the audit log, and sends a notification message.  It's meant
        to be run from the background processing thread.

        Args:
            session (session): database session
        """
        now = datetime.utcnow()

        # Pull the expired edges.
        edges = session.query(GroupEdge).filter(
            GroupEdge.active == True,
            and_(
                GroupEdge.expiration <= now,
                GroupEdge.expiration != None
            )
        ).all()

        # Expire each one.
        for edge in edges:
            notify_edge_expiration(self.settings, session, edge)
            edge.active = False
            session.commit()

    def run(self):
        while True:
            try:
                session = Session()
                logging.debug("Expiring edges....")
                self.expire_edges(session)
                logging.debug("Sending emails...")
                process_async_emails(self.settings, session, datetime.utcnow())
                logging.debug("Pruning old traces....")
                prune_old_traces(session)
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
