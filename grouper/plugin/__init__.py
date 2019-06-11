from grouper.plugin.proxy import PluginProxy

_plugin_proxy = PluginProxy([])


def set_global_plugin_proxy(plugin_proxy):
    # type: (PluginProxy) -> None
    global _plugin_proxy
    _plugin_proxy = plugin_proxy


def get_plugin_proxy():
    # type: () -> PluginProxy
    global _plugin_proxy
    return _plugin_proxy
