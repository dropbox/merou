from tornado.web import RequestHandler
from grouper import perf_profile


# Don't use GraphHandler here as we don't want to count
# these as requests.
class PerfProfile(RequestHandler):
    def get(self, trace_uuid):
        from grouper.model_soup import Session
        try:
            flamegraph_svg = perf_profile.get_flamegraph_svg(Session(), trace_uuid)
        except perf_profile.InvalidUUID:
            pass
        else:
            self.set_header("Content-Type", "image/svg+xml")
            self.write(flamegraph_svg)
