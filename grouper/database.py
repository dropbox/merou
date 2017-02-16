from contextlib import closing
import logging
from threading import Thread
from time import sleep

from expvar.stats import stats
from sqlalchemy.exc import OperationalError

from grouper.models.base.session import get_db_engine, Session
from grouper.perf_profile import init_stopwatch, stopwatch_emit_stats, get_stopwatch as sw
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
        # get a new stopwatch context for this thread
        init_stopwatch()

        while True:
            self.logger.debug("Updating Graph from Database.")
            try:
                with closing(Session()) as session, sw().timer('sw-db_refresh_thread'):
                    self.graph.update_from_db(session)

                stopwatch_emit_stats()

                stats.set_gauge("successful-db-update", 1)
                stats.set_gauge("failed-db-update", 0)
            except OperationalError:
                Session.configure(bind=get_db_engine(get_database_url(self.settings)))
                self.logger.critical("Failed to connect to database.")
                stats.set_gauge("successful-db-update", 0)
                stats.set_gauge("failed-db-update", 1)
                self.capture_exception()
            except:
                stats.set_gauge("successful-db-update", 0)
                stats.set_gauge("failed-db-update", 1)
                self.capture_exception()
                raise

            sleep(self.refresh_interval)
