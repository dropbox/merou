import inspect
import os
from importlib import import_module
from typing import Callable, List, Type, TypeVar

from annex import Annex

from grouper.plugin.base import BasePlugin
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.plugin.proxy import PluginProxy

T = TypeVar("T")

_plugin_proxy = PluginProxy([])


def initialize_plugins(plugin_dirs, plugin_module_paths, service_name):
    # type: (List[str], List[str], str) -> None
    plugins = load_plugins(BasePlugin, plugin_dirs, plugin_module_paths, service_name)

    global _plugin_proxy
    _plugin_proxy = PluginProxy(plugins)


def get_plugin_proxy():
    # type: () -> PluginProxy
    global _plugin_proxy
    return _plugin_proxy


def load_plugins(base_plugin, plugin_dirs, plugin_module_paths, service_name):
    # type: (Type[T], List[str], List[str], str) -> List[T]
    """Load plugins from a list of directories and modules"""
    for plugin_dir in plugin_dirs:
        if not os.path.exists(plugin_dir):
            raise PluginsDirectoryDoesNotExist("{} doesn't exist".format(plugin_dir))

    plugins = Annex(
        base_plugin=base_plugin,
        plugin_dirs=plugin_dirs,
        raise_exceptions=True,
        additional_plugin_callback=_load_plugin_modules(base_plugin, plugin_module_paths),
    )

    for plugin in plugins:
        plugin.configure(service_name)

    return list(plugins)


def _load_plugin_modules(base_plugin, plugin_module_paths):
    # type: (Type[T], List[str]) -> Callable
    def callback():
        plugins = []

        for module_path in plugin_module_paths:
            module = import_module(module_path)
            for name in dir(module):
                obj = getattr(module, name)
                if inspect.isclass(obj) and issubclass(obj, base_plugin) and obj != base_plugin:
                    plugins.append(obj)

        return plugins

    return callback
