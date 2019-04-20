import logging
import os
from contextlib import closing
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING

from grouper import stats
from grouper.models.base.session import Session

if TYPE_CHECKING:
    from grouper.error_reporting import SentryProxy
    from grouper.graph import GroupGraph
    from grouper.settings import Settings
    from typing import Any, NoReturn


class DbRefreshThread(Thread):
    """Background thread for refreshing the in-memory cache of the graph."""

    def __init__(self, settings, graph, refresh_interval, sentry_client, *args, **kwargs):
        # type: (Settings, GroupGraph, int, SentryProxy, *Any, **Any) -> None
        self.settings = settings
        self.graph = graph
        self.refresh_interval = refresh_interval
        self.sentry_client = sentry_client
        self.logger = logging.getLogger(__name__)
        Thread.__init__(self, *args, **kwargs)

    def capture_exception(self):
        # type: () -> None
        if self.sentry_client:
            self.sentry_client.captureException()

    def crash(self):
        # type: () -> NoReturn
        os._exit(1)

    def run(self):
        # type () -> None
        initial_url = self.settings.database
        while True:
            self.logger.debug("Updating Graph from Database.")
            try:
                if self.settings.database != initial_url:
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
