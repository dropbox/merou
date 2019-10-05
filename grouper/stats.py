from grouper.plugin import get_plugin_proxy


def log_background_run(success):
    # type: (bool) -> None
    """Log a background processor run

    Arg(s):
        success: whether the run succeeded
    """
    get_plugin_proxy().log_background_run(success)


def log_graph_update_duration(duration_ms):
    # type: (int) -> None
    """Log a graph update duration

    Arg(s):
        duration_ms: the graph update latency
    """
    get_plugin_proxy().log_graph_update_duration(duration_ms)


def log_periodic_graph_update(success):
    # type: (bool) -> None
    """Log a periodic graph update run

    Arg(s):
        success: whether the run succeeded
    """
    get_plugin_proxy().log_periodic_graph_update(success)


def log_request(handler, status, duration_ms):
    # type: (str, int, int) -> None
    """Log information about a handled request

    Arg(s):
        handler: name of the handler class that handled the request
        status: the response status of the request (e.g., 200, 404, etc.)
        duration_ms: the request processing latency
    """
    get_plugin_proxy().log_request(handler, status, duration_ms)
