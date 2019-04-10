from tornado.web import RequestHandler

from grouper.models.base.session import Session
from grouper.perf_profile import FLAMEGRAPH_SUPPORTED, get_flamegraph_svg, InvalidUUID


# Don't use GraphHandler here as we don't want to count
# these as requests.
class PerfProfile(RequestHandler):
    def get(self, trace_uuid):
        if not FLAMEGRAPH_SUPPORTED:
            return self.self_error(
                status_code=404,
                reason="Performance profiles not supported (plop or pyflamegraph not installed)",
            )

        try:
            flamegraph_svg = get_flamegraph_svg(Session(), trace_uuid)
        except InvalidUUID:
            pass
        else:
            self.set_header("Content-Type", "image/svg+xml")
            self.write(flamegraph_svg)
