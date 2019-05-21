from typing import TYPE_CHECKING

from tornado.web import RequestHandler

from grouper.models.base.session import Session
from grouper.perf_profile import FLAMEGRAPH_SUPPORTED, get_flamegraph_svg, InvalidUUID

if TYPE_CHECKING:
    from typing import Any


# Don't use GrouperHandler here as we don't want to count these as requests.
class PerfProfile(RequestHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        trace_uuid = kwargs["trace_uuid"]  # type: str
        if not FLAMEGRAPH_SUPPORTED:
            return self.send_error(
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
