from typing import TYPE_CHECKING

from grouper.plugin.base import BasePlugin
from grouper.plugin.load import load_plugins

if TYPE_CHECKING:
    from grouper.models.audit_log import AuditLog
    from grouper.models.group import Group
    from grouper.models.user import User
    from grouper.settings import Settings
    from sshpubkeys import SSHKey
    from ssl import SSLContext
    from sqlalchemy.orm import Session
    from tornado.httpserver import HTTPRequest
    from types import TracebackType
    from typing import Any, Dict, List, Iterable, Optional, Type, Tuple, Union


class PluginProxy:
    """Wrapper to proxy a plugin method call to all loaded plugins."""

    @classmethod
    def load_plugins(cls, settings, service_name):
        # type: (Settings, str) -> PluginProxy
        plugins = load_plugins(
            BasePlugin, settings.plugin_dirs, settings.plugin_module_paths, service_name
        )
        return cls(plugins)

    def __init__(self, plugins):
        # type: (List[BasePlugin]) -> None
        self._plugins = plugins

    def add_plugin(self, plugin):
        # type: (BasePlugin) -> None
        self._plugins.append(plugin)

    def configure(self, service_name):
        # type: (str) -> None
        for plugin in self._plugins:
            plugin.configure(service_name)

    def check_machine_set(self, name, machine_set):
        # type: (str, str) -> None
        for plugin in self._plugins:
            plugin.check_machine_set(name, machine_set)

    def check_service_account_name(self, name):
        # type: (str) -> None
        for plugin in self._plugins:
            plugin.check_service_account_name(name)

    def check_permission_argument(self, permission: str, argument: str) -> None:
        for plugin in self._plugins:
            plugin.check_permission_argument(permission, argument)

    def get_aliases_for_mapped_permission(self, session, permission, argument):
        # type: (Session, str, str) -> Iterable[Tuple[str, str]]
        for plugin in self._plugins:
            aliases = plugin.get_aliases_for_mapped_permission(session, permission, argument)
            if aliases is None:
                continue
            for alias in aliases:
                yield alias

    def get_github_app_client_secret(self):
        # type: () -> bytes
        for plugin in self._plugins:
            secret = plugin.get_github_app_client_secret()
            if secret is not None:
                return secret
        raise ValueError("no github secret available")

    def get_owner_by_arg_by_perm(self, session):
        # type: (Session) -> Iterable[Dict[str, Dict[str, List[Group]]]]
        for plugin in self._plugins:
            owners = plugin.get_owner_by_arg_by_perm(session)
            if owners is not None:
                yield owners

    def get_ssl_context(self):
        # type: () -> Optional[SSLContext]
        for plugin in self._plugins:
            context = plugin.get_ssl_context()
            if context is not None:
                return context
        return None

    def log_auditlog_entry(self, entry):
        # type: (AuditLog) -> None
        for plugin in self._plugins:
            plugin.log_auditlog_entry(entry)

    def log_background_run(self, success):
        # type: (bool) -> None
        for plugin in self._plugins:
            plugin.log_background_run(success)

    def log_exception(
        self,
        request,  # type: Optional[HTTPRequest]
        status,  # type: Optional[int]
        exc_type,  # type: Optional[Type[BaseException]]
        exc_value,  # type: Optional[BaseException]
        exc_tb,  # type: Optional[TracebackType]
    ):
        # type: (...) -> None
        for plugin in self._plugins:
            plugin.log_exception(request, status, exc_type, exc_value, exc_tb)

    def log_graph_update_duration(self, duration_ms):
        # type: (int) -> None
        for plugin in self._plugins:
            plugin.log_graph_update_duration(duration_ms)

    def log_periodic_graph_update(self, success):
        # type: (bool) -> None
        for plugin in self._plugins:
            plugin.log_periodic_graph_update(success)

    def log_request(self, handler, status, duration_ms, request):
        # type: (str, int, int, Optional[HTTPRequest]) -> None
        for plugin in self._plugins:
            plugin.log_request(handler, status, duration_ms, request)

    def user_created(self, user, is_service_account=False):
        # type: (User, bool) -> None
        for plugin in self._plugins:
            plugin.user_created(user, is_service_account)

    def will_add_public_key(self, key):
        # type: (SSHKey) -> None
        for plugin in self._plugins:
            plugin.will_add_public_key(key)

    def will_disable_user(self, session, user):
        # type: (Session, User) -> None
        for plugin in self._plugins:
            plugin.will_disable_user(session, user)

    def will_update_group_membership(self, session, group, member, **updates):
        # type: (Session, Group, Union[User, Group], **Any) -> None
        for plugin in self._plugins:
            plugin.will_update_group_membership(session, group, member, **updates)
