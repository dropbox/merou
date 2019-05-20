from typing import TYPE_CHECKING

from grouper.plugin.base import BasePlugin

if TYPE_CHECKING:
    from tests.setup import SetupTest


class MockStats(BasePlugin):
    def __init__(self):
        # type: () -> None
        self.update_ms = 0.0

    def log_rate(self, key, val, count=1):
        # type: (str, float, int) -> None
        assert key == "graph_update_ms"
        assert count == 1
        self.update_ms = val


def test_graph_update_stats(setup):
    # type: (SetupTest) -> None
    """Test that update timings are logged by a graph update."""
    mock_stats = MockStats()
    setup.plugin_proxy.add_plugin(mock_stats)

    # Create a user and a group, which will trigger a graph update.
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    assert mock_stats.update_ms > 0.0
