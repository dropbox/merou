import inspect
import os
from importlib import import_module
from typing import TYPE_CHECKING

from annex import Annex

from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist

if TYPE_CHECKING:
    from typing import Callable, List, Type, TypeVar

    T = TypeVar("T")


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
