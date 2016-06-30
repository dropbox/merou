from expvar.stats import stats
from tornado.web import RequestHandler


# this guys shouldn't count as requests so we use tornado's RequestHandler
class Stats(RequestHandler):
    def get(self):
        """Returns all gathered stats. This includes a 'mimic_head' query
        parameter which lets process management/monitoring without support for
        HEAD queries to use this endpoint for health checks."""
        mimic_head = self.get_argument("mimic_head", False)
        if mimic_head:
            return self.head()
        else:
            return self.write(stats.to_dict())

    def head(self):
        """Support process management/monitoring of health checks with stat
        gauges via http status code."""
        gauge_keys = self.get_arguments("gauge")
        try:
            res = all(stats.get_gauge(k) for k in gauge_keys)
        except KeyError:
            res = False

        status_code = 200 if res else 500
        self.set_status(status_code)

        return self.write("")
