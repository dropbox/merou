from contextlib import closing
from typing import TYPE_CHECKING

from tornado.web import RequestHandler

from grouper.models.base.session import Session

if TYPE_CHECKING:
    from typing import Any


class HealthCheck(RequestHandler):
    def initialize(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        pass

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        with closing(Session()) as session:
            session.execute("SELECT 1")
        self.write("")
