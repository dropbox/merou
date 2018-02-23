from contextlib import closing
import logging
from threading import Thread
from time import sleep

from sqlalchemy.exc import OperationalError

from grouper import stats
from grouper.models.base.session import get_db_engine, Session
from grouper.util import get_database_url


class DbRefreshThread(Thread):
    """Background thread for refreshing the in-memory cache of the graph."""
    def __init__(self, settings, graph, refresh_interval, sentry_client, *args, **kwargs):
        self.settings = settings
        self.graph = graph
        self.refresh_interval = refresh_interval
        self.sentry_client = sentry_client
        self.logger = logging.getLogger(__name__)
        Thread.__init__(self, *args, **kwargs)

    def capture_exception(self):
        if self.sentry_client:
            self.sentry_client.captureException()

    def run(self):
        while True:
            self.logger.debug("Updating Graph from Database.")
            try:
                with closing(Session()) as session:
                    self.graph.update_from_db(session)

                stats.log_gauge("successful-db-update", 1)
                stats.log_gauge("failed-db-update", 0)
            except OperationalError:
                Session.configure(bind=get_db_engine(get_database_url(self.settings)))
                self.logger.critical("Failed to connect to database.")
                stats.log_gauge("successful-db-update", 0)
                stats.log_gauge("failed-db-update", 1)
                self.capture_exception()
            except:
                stats.log_gauge("successful-db-update", 0)
                stats.log_gauge("failed-db-update", 1)
                self.capture_exception()
                raise

            sleep(self.refresh_interval)
