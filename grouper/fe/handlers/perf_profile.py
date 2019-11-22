from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.util import GrouperHandler
from grouper.models.base.session import Session
from grouper.perf_profile import FLAMEGRAPH_SUPPORTED, get_flamegraph_svg, InvalidUUID

if TYPE_CHECKING:
    from typing import Any


class PerfProfile(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        trace_uuid = self.get_path_argument("trace_uuid")

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
