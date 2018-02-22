from contextlib import closing

from tornado.web import RequestHandler

from grouper.models.base.session import Session


class HealthCheck(RequestHandler):
    def get(self):
        with closing(Session()) as session:
            session.execute("SELECT 1")

        return self.write("")
