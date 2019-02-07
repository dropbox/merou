from tornado.process import task_id

from grouper.plugin import get_plugin_proxy


def set_defaults():
    # type: () -> None
    instance = task_id()
    if instance is None:
        instance = 0

    default_tags = {"instance": str(instance)}

    get_plugin_proxy().set_default_stats_tags(default_tags)


def log_rate(key, val, count=1):
    # type: (str, float, int) -> None
    get_plugin_proxy().log_rate(key, val, count)


def log_gauge(key, val):
    # type: (str, float) -> None
    get_plugin_proxy().log_gauge(key, val)
