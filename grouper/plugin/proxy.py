from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ssl import SSLContext  # noqa: F401
    from typing import Any, Dict, List, Iterable, Optional, Union  # noqa: F401
    from sqlalchemy.orm import Session  # noqa: F401
    from sshpubkeys import SSHKey  # noqa: F401
    from tornado.httpserver import HTTPRequest  # noqa: F401
    from grouper.models.audit_log import AuditLog  # noqa: F401
    from grouper.models.group import Group  # noqa: F401
    from grouper.models.user import User  # noqa: F401
    from grouper.plugin.base import BasePlugin  # noqa: F401


class PluginProxy(object):
    def __init__(self, plugins):
        # type: (List[BasePlugin]) -> None
        self._plugins = plugins

    def check_machine_set(self, name, machine_set):
        # type: (str, str) -> None
        for plugin in self._plugins:
            plugin.check_machine_set(name, machine_set)

    def configure(self, service_name):
        # type: (str) -> None
        for plugin in self._plugins:
            plugin.configure(service_name)

    def get_owner_by_arg_by_perm(self, session):
        # type: (Session) -> Iterable[Dict[str, Dict[str, Group]]]
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

    def log_exception(self, request, status, exception, stack):
        # type: (HTTPRequest, int, Exception, List) -> None
        for plugin in self._plugins:
            plugin.log_exception(request, status, exception, stack)

    def log_gauge(self, key, val):
        # type: (str, float) -> None
        for plugin in self._plugins:
            plugin.log_gauge(key, val)

    def log_rate(self, key, val, count=1):
        # type: (str, float, int) -> None
        for plugin in self._plugins:
            plugin.log_rate(key, val, count)

    def set_default_stats_tags(self, tags):
        # type: (Dict[str, str]) -> None
        for plugin in self._plugins:
            plugin.set_default_stats_tags(tags)

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
