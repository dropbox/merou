import logging
import os
import sys
from contextlib import closing
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING

from grouper.models.base.session import Session

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.plugins.proxy import PluginProxy
    from grouper.settings import Settings
    from typing import Any, NoReturn


class DbRefreshThread(Thread):
    """Background thread for refreshing the in-memory cache of the graph."""

    def __init__(self, settings, plugins, graph, refresh_interval, *args, **kwargs):
        # type: (Settings, PluginProxy, GroupGraph, int, *Any, **Any) -> None
        self.settings = settings
        self.plugins = plugins
        self.graph = graph
        self.refresh_interval = refresh_interval
        self.logger = logging.getLogger(__name__)
        Thread.__init__(self, *args, **kwargs)

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

                self.plugins.log_periodic_graph_update(success=True)
            except Exception:
                self.plugins.log_periodic_graph_update(success=False)
                self.plugins.log_exception(None, None, *sys.exc_info())
                logging.exception("Failed to refresh graph")
                self.crash()

            sleep(self.refresh_interval)
