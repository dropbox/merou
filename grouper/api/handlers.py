import csv
import re
import sys
import traceback
from contextlib import closing
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING

from tornado.web import HTTPError, RequestHandler

from grouper.constants import TOKEN_FORMAT
from grouper.graph import NoSuchGroup, NoSuchUser
from grouper.models.base.session import Session
from grouper.models.public_key import PublicKey
from grouper.models.user import User as SQLUser
from grouper.models.user_token import UserToken
from grouper.usecases.list_grants import ListGrantsUI
from grouper.usecases.list_permissions import ListPermissionsUI
from grouper.usecases.list_users import ListUsersUI
from grouper.util import try_update

if TYPE_CHECKING:
    from grouper.entities.pagination import PaginatedList
    from grouper.entities.permission import Permission
    from grouper.entities.permission_grant import UniqueGrantsOfPermission
    from grouper.entities.user import User
    from grouper.graph import GroupGraph
    from grouper.plugin.proxy import PluginProxy
    from grouper.usecases.factory import UseCaseFactory
    from types import TracebackType
    from typing import Any, Dict, Iterable, Optional, Tuple, Type


def get_individual_user_info(handler, name, service_account):
    # type: (GraphHandler, str, Optional[bool]) -> Dict[str, Any]
    """This is a helper function to retrieve all information about a user.

    Args:
        handler: the GraphHandler for this request
        name: the name of the user whose data is being retrieved
        service_account: a boolean indicating if this request is for a service account or not. This
            can be None if you want to support users and service accounts (deprecated)

    Returns:
        A dictionary containing all of the user's data

    Raises:
        NoSuchUser: When no user with the given name exists, or has the the wrong serviceaccount
            type
    """
    with handler.graph.lock:
        if name not in handler.graph.user_metadata:
            raise NoSuchUser
        md = handler.graph.user_metadata[name]
        if service_account is not None:
            is_service_account = md["role_user"] or "service_account" in md
            if service_account != is_service_account:
                raise NoSuchUser

        details = handler.graph.get_user_details(name, expose_aliases=False)
        out = {"user": {"name": name}}
        # Updates the output with the user's metadata
        try_update(out["user"], md)
        # Updates the output with the user's details (such as permissions)
        try_update(out, details)
        return out


class GraphHandler(RequestHandler):
    def initialize(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.graph = kwargs["graph"]  # type: GroupGraph
        self.usecase_factory = kwargs["usecase_factory"]  # type: UseCaseFactory
        self.plugins = kwargs["plugins"]  # type: PluginProxy

        self._request_start_time = datetime.utcnow()

    def on_finish(self):
        # type: () -> None
        handler = self.__class__.__name__
        response_status = self.get_status()
        duration_ms = int((datetime.utcnow() - self._request_start_time).total_seconds() * 1000)
        self.plugins.log_request(handler, response_status, duration_ms, self.request)

    def log_exception(
        self,
        exc_type,  # type: Optional[Type[BaseException]]
        exc_value,  # type: Optional[BaseException]
        exc_tb,  # type: Optional[TracebackType]
    ):
        # type: (...) -> None
        if isinstance(exc_value, HTTPError):
            status_code = exc_value.status_code
        else:
            status_code = 500
        self.plugins.log_exception(self.request, status_code, exc_type, exc_value, exc_tb)
        super().log_exception(exc_type, exc_value, exc_tb)

    def error(self, errors):
        # type: (Iterable[Tuple[int, Any]]) -> None
        out = [{"code": code, "message": message} for code, message in errors]
        with self.graph.lock:
            checkpoint = self.graph.checkpoint
            checkpoint_time = self.graph.checkpoint_time
        self.write(
            {
                "status": "error",
                "errors": out,
                "checkpoint": checkpoint,
                "checkpoint_time": checkpoint_time,
            }
        )

    def success(self, data):
        # type: (Any) -> None
        with self.graph.lock:
            checkpoint = self.graph.checkpoint
            checkpoint_time = self.graph.checkpoint_time
        self.write(
            {
                "status": "ok",
                "data": data,
                "checkpoint": checkpoint,
                "checkpoint_time": checkpoint_time,
            }
        )

    def raise_and_log_exception(self, exc):
        # type: (Exception) -> None
        try:
            raise exc
        except Exception:
            self.log_exception(*sys.exc_info())

    def notfound(self, message):
        # type: (str) -> None
        self.set_status(404)
        self.raise_and_log_exception(HTTPError(404))
        self.error([(404, message)])

    def write_error(self, status_code, **kwargs):
        # type: (int, **Any) -> None
        """Overrides tornado's uncaught exception handler to return JSON results."""
        if "exc_info" in kwargs:
            typ, value, _ = kwargs["exc_info"]
            self.error([(status_code, traceback.format_exception_only(typ, value))])
        else:
            self.error([(status_code, None)])


class Users(GraphHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        name = kwargs.get("name")  # type: Optional[str]

        # Deprecated 2016-08-10, use the ServiceAccounts endpoint to lookup service accounts
        include_service_accounts = self.get_argument("include_role_users", "no") == "yes"

        if name is not None:
            # We don't require `include_service_accounts` when querying for a specific user,
            # because there are too many existing integrations that expect the
            # /users/foo@example.com endpoint to work for both. :(
            try:
                return self.success(get_individual_user_info(self, name, service_account=None))
            except NoSuchUser:
                return self.notfound(f"User ({name}) not found.")

        with self.graph.lock:
            return self.success(
                {
                    "users": sorted(
                        [
                            k
                            for k, v in self.graph.user_metadata.items()
                            if (
                                include_service_accounts
                                or not ("service_account" in v or v["role_user"])
                            )
                        ]
                    )
                }
            )


class UserMetadata(GraphHandler, ListUsersUI):
    def listed_users(self, users):
        # type: (Dict[str, User]) -> None
        users_dict = {}  # type: Dict[str, Dict[str, Any]]
        for user, data in users.items():
            metadata = {m.key: m.value for m in data.metadata}
            public_keys = [
                {
                    "public_key": k.public_key,
                    "fingerprint": k.fingerprint,
                    "fingerprint_sha256": k.fingerprint_sha256,
                }
                for k in data.public_keys
            ]
            users_dict[user] = {
                "role_user": data.role_user,
                "metadata": metadata,
                "public_keys": public_keys,
            }
        self.success({"users": users_dict})

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        usecase = self.usecase_factory.create_list_users_usecase(self)
        usecase.list_users()


class MultiUsers(GraphHandler):
    """API endpoint for bulk retrieval of user data.

    This returns the same information as the Users and ServiceAccounts endpoints, but supports
    multiple returning the data of multiple users to save on API call overhead.
    """

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        usernames = self.get_arguments("username")
        if not usernames:
            usernames = iter(self.graph.user_metadata)

        with self.graph.lock:
            data = {}
            for username in usernames:
                try:
                    data[username] = get_individual_user_info(self, username, service_account=None)
                except NoSuchUser:
                    continue
            self.success(data)


class UsersPublicKeys(GraphHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        fh = StringIO()
        w_csv = csv.writer(fh, lineterminator="\n")

        # header
        w_csv.writerow(
            [
                "username",
                "created_at",
                "type",
                "size",
                "fingerprint",
                "fingerprint_sha256",
                "comment",
            ]
        )

        with closing(Session()) as session:
            user_key_list = session.query(PublicKey, SQLUser).filter(
                SQLUser.id == PublicKey.user_id
            )
            for key, user in user_key_list:
                w_csv.writerow(
                    [
                        user.name,
                        key.created_on.isoformat(),
                        key.key_type,
                        key.key_size,
                        key.fingerprint,
                        key.fingerprint_sha256,
                        key.comment,
                    ]
                )

        self.set_header("Content-Type", "text/csv")
        self.write(fh.getvalue())


class Grants(GraphHandler, ListGrantsUI):
    def listed_grants(self, grants):
        # type: (Dict[str, UniqueGrantsOfPermission]) -> None
        grants_dict = {
            k: {
                "users": v.users,
                "role_users": v.role_users,
                "service_accounts": v.service_accounts,
            }
            for k, v in grants.items()
        }
        self.success({"permissions": grants_dict})

    def listed_grants_of_permission(self, permission, grants):
        # type: (str, UniqueGrantsOfPermission) -> None
        grants_dict = {
            "users": grants.users,
            "role_users": grants.role_users,
            "service_accounts": grants.service_accounts,
        }
        self.success({"permission": permission, "grants": grants_dict})

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        permission = kwargs.get("name")  # type: Optional[str]
        usecase = self.usecase_factory.create_list_grants_usecase(self)
        if permission:
            usecase.list_grants_of_permission(permission)
        else:
            usecase.list_grants()


class Groups(GraphHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        name = kwargs.get("name")  # type: Optional[str]
        with self.graph.lock:
            if not name:
                return self.success({"groups": self.graph.groups})

            try:
                details = self.graph.get_group_details(name, expose_aliases=False)
            except NoSuchGroup:
                return self.notfound("Group (%s) not found." % name)

            return self.success(details)


class Permissions(GraphHandler, ListPermissionsUI):
    def listed_permissions(self, permissions, can_create):
        # type: (PaginatedList[Permission], bool) -> None
        self.success({"permissions": [p.name for p in permissions.values]})

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        name = kwargs.get("name")  # type: Optional[str]
        if not name:
            usecase = self.usecase_factory.create_list_permissions_usecase(self)
            usecase.simple_list_permissions()
            return

        with self.graph.lock:
            if name not in self.graph.permissions:
                return self.notfound("Permission (%s) not found." % name)

            details = self.graph.get_permission_details(name, expose_aliases=False)

            out = {"permission": {"name": name}}
            try_update(out, details)
            self.success(out)


class TokenValidate(GraphHandler):
    validator = re.compile(TOKEN_FORMAT)

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        supplied_token = self.get_body_argument("token")
        match = TokenValidate.validator.match(supplied_token)
        if not match:
            return self.error(((1, "Token format not recognized"),))

        token_name = match.group("token_name")
        token_secret = match.group("token_secret")
        username = match.group("name")

        with closing(Session()) as session:
            token = UserToken.get_by_value(session, username, token_name)
            if token is None:
                return self.error(((2, "Token specified does not exist"),))
            if not token.enabled:
                return self.error(((3, "Token is disabled"),))
            if not token.check_secret(token_secret):
                return self.error(((4, "Token secret mismatch"),))
            return self.success(
                {"owner": username, "identity": str(token), "act_as_owner": True, "valid": True}
            )


class ServiceAccounts(GraphHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        name = kwargs.get("name")  # type: Optional[str]
        if name is not None:
            try:
                return self.success(get_individual_user_info(self, name, service_account=True))
            except NoSuchUser:
                return self.notfound(f"User ({name}) not found.")

        with self.graph.lock:
            return self.success(
                {
                    "service_accounts": sorted(
                        [
                            k
                            for k, v in self.graph.user_metadata.items()
                            if "service_account" in v or v["role_user"]
                        ]
                    )
                }
            )


class NotFound(GraphHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        return self.notfound("Endpoint not found")
