from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.models.audit_log import AuditLog
    from grouper.models.group import Group
    from grouper.models.user import User
    from sshpubkeys import SSHKey
    from ssl import SSLContext
    from sqlalchemy.orm import Session
    from tornado.httpserver import HTTPRequest
    from types import TracebackType
    from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, Union


class BasePlugin:
    def configure(self, service_name):
        # type: (str) -> None
        """Configure the plugin.

        Called once the plugin is instantiated to identify the executable (grouper-api, grouper-fe,
        or grouper-background).
        """
        pass

    def check_machine_set(self, name, machine_set):
        # type: (str, str) -> None
        """Check whether a service account machine set is valid.

        Args:
            name: Name of the service account being changed
            machine_set: New machine set for a service account

        Raises:
            PluginRejectedMachineSet to reject the change.  The exception message will be shown to
            the user.
        """
        pass

    def check_service_account_name(self, name):
        # type: (str) -> None
        """Check whether a service account name is allowed.

        Args:
            name: Name of a new service account being created (with domain)

        Raises:
            PluginRejectedServiceAccountName to reject the name.  The exception message will be
            shown to the user.
        """
        pass

    def check_permission_argument(self, permission: str, argument: str) -> None:
        """Check permission argument for validity

        Args:
            permission: A Grouper permission name
            argument: The argument for that permission

        Raises:
            PluginRejectedPermissionArgument to reject the argument. The exception message will be
            shown to the user.
        """
        pass

    def get_aliases_for_mapped_permission(self, session, permission, argument):
        # type: (Session, str, str) -> Optional[Iterable[Tuple[str, str]]]
        """Called when building the graph to get aliases of a mapped permission.

        Args:
            session: database session
            permission: the name of the permission
            argument: the argument that the permission was granted with

        Returns:
            A list of (permission, argument) tuples that the permission is an alias for.
        """
        pass

    def get_github_app_client_secret(self):
        # type: () -> bytes
        "Return the client secret for the GitHub app used to authorize users."

    def get_owner_by_arg_by_perm(self, session):
        # type: (Session) -> Optional[Dict[str, Dict[str, List[Group]]]]
        """Called when determining owners for permission+arg granting.

        Args:
            session: database session

        Returns:
            dict of the form {'permission_name': {'argument': [owner1, owner2,
            ...], ...}, ...} where 'ownerN' is a models.Group corresponding to
            the grouper group that owns (read: is able to) grant that
            permission + argument pair.
        """
        pass

    def get_ssl_context(self):
        # type: () -> Optional[SSLContext]
        """Called to get the ssl.SSLContext for the application."""
        pass

    def log_auditlog_entry(self, entry):
        # type: (AuditLog) -> None
        """Called when an audit log entry is saved to the database.

        Args:
            entry: just-saved log object
        """
        pass

    def log_background_run(self, success):
        # type: (bool) -> None
        """Log a background processor run

        Arg(s):
            success: whether the run succeeded
        """
        pass

    def log_exception(
        self,
        request,  # type: Optional[HTTPRequest]
        status,  # type: Optional[int]
        exc_type,  # type: Optional[Type[BaseException]]
        exc_value,  # type: Optional[BaseException]
        exc_tb,  # type: Optional[TracebackType]
    ):
        # type: (...) -> None
        """Called when an exception is triggered.

        Args:
            request: The request being handled (None for non-Tornado exceptions)
            status: The response status (None for non-Tornado exceptions)
            exc_type: The type of the exception
            exc_value: The exception object
            exc_tb: The traceback, in the same form as sys.exc_info()[2]
        """
        pass

    def log_graph_update_duration(self, duration_ms):
        # type: (int) -> None
        """Log a graph update duration

        Arg(s):
            duration_ms: the graph update latency
        """
        pass

    def log_periodic_graph_update(self, success):
        # type: (bool) -> None
        """Log a periodic graph update run

        Arg(s):
            success: whether the run succeeded
        """
        pass

    def log_request(self, handler, status, duration_ms, request):
        # type: (str, int, int, Optional[HTTPRequest]) -> None
        """Log information about a handled request

        Arg(s):
            handler: name of the handler class that handled the request
            status: the response status of the request (e.g., 200, 404, etc.)
            duration_ms: the request processing latency
            request: the Tornado request that was handled
        """
        pass

    def user_created(self, user, is_service_account=False):
        # type: (User, bool) -> None
        """Called when a new user is created

        When new users enter into Grouper, you might have reason to set metadata on those
        users for some reason. This method is called when that happens.

        Args:
            user: Object of new user.
            is_service_account: Whether this user is a service account (role user)

        Returns:
            The return code of this method is ignored.
        """
        pass

    def will_add_public_key(self, key):
        # type: (SSHKey) -> None
        """Called before adding a public key.

        Args:
            key: Parsed public key

        Raises:
            PluginRejectedPublicKey: if the plugin rejects the key
        """
        pass

    def will_disable_user(self, session, user):
        # type: (Session, User) -> None
        """Called before disabling a user.

        Args:
            session: database session
            user: User to be disabled

        Raises:
            PluginRejectedDisablingUser: if the plugin rejects the change
        """
        pass

    def will_update_group_membership(self, session, group, member, **updates):
        # type: (Session, Group, Union[User, Group], **Any) -> None
        """Called before applying changes to a group membership.

        Args:
            session: database session
            group: affected group
            member: affected User or Group
            updates: the updates to the membership (active, expiration, role)

        Raises:
            PluginRejectedGroupMembershipUpdate: if the plugin rejects the update
        """
        pass
