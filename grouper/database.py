import logging
import os
from contextlib import closing
from threading import Thread
from time import sleep

from grouper import stats
from grouper.models.base.session import Session
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

    def crash(self):
        os._exit(1)

    def run(self):
        initial_url = get_database_url(self.settings)
        while True:
            self.logger.debug("Updating Graph from Database.")
            try:
                if get_database_url(self.settings) != initial_url:
                    self.crash()
                with closing(Session()) as session:
                    self.graph.update_from_db(session)

                stats.log_gauge("successful-db-update", 1)
                stats.log_gauge("failed-db-update", 0)
            except Exception:
                stats.log_gauge("successful-db-update", 0)
                stats.log_gauge("failed-db-update", 1)
                self.capture_exception()
                self.crash()

            sleep(self.refresh_interval)
