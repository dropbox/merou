from tornado.process import task_id

from grouper.plugin import get_plugins


def set_defaults():
    # type: () -> None
    instance = task_id()
    if instance is None:
        instance = 0

    default_tags = {
        "instance": str(instance),
    }

    for plugin in get_plugins():
        plugin.set_default_stats_tags(default_tags)


def log_rate(key, val, count=1):
    # type: (str, float, int) -> None
    for plugin in get_plugins():
        plugin.log_rate(key, val, count)


def log_gauge(key, val):
    # type: (str, float) -> None
    for plugin in get_plugins():
        plugin.log_gauge(key, val)
