from expvar.stats import stats
from tornado.web import RequestHandler


class Stats(RequestHandler):
    def get(self):
        return self.write(stats.to_dict())
