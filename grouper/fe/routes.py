"""Routes and handlers for the Grouper frontend.

Provides the variable HANDLERS, which contains tuples of route regexes and handlers.  Do not
provide additional handler arguments as a third argument of the tuple.  A standard set of
additional arguments will be injected when the Tornado Application object is created.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.constants import (
    NAME_VALIDATION,
    PERMISSION_VALIDATION,
    SERVICE_ACCOUNT_VALIDATION,
    USERNAME_VALIDATION,
)
from grouper.fe.handlers.audits_complete import AuditsComplete
from grouper.fe.handlers.audits_create import AuditsCreate
from grouper.fe.handlers.audits_view import AuditsView
from grouper.fe.handlers.github import GitHubLinkBeginView, GitHubLinkCompleteView, UserClearGitHub
from grouper.fe.handlers.group_add import GroupAdd
from grouper.fe.handlers.group_disable import GroupDisable
from grouper.fe.handlers.group_edit import GroupEdit
from grouper.fe.handlers.group_edit_member import GroupEditMember
from grouper.fe.handlers.group_enable import GroupEnable
from grouper.fe.handlers.group_join import GroupJoin
from grouper.fe.handlers.group_leave import GroupLeave
from grouper.fe.handlers.group_remove import GroupRemove
from grouper.fe.handlers.group_request_update import GroupRequestUpdate
from grouper.fe.handlers.group_requests import GroupRequests
from grouper.fe.handlers.group_view import GroupView
from grouper.fe.handlers.groups_view import GroupsView
from grouper.fe.handlers.help import Help
from grouper.fe.handlers.index import Index
from grouper.fe.handlers.not_found import NotFound
from grouper.fe.handlers.perf_profile import PerfProfile
from grouper.fe.handlers.permission_disable import PermissionDisable
from grouper.fe.handlers.permission_disable_auditing import PermissionDisableAuditing
from grouper.fe.handlers.permission_enable_auditing import PermissionEnableAuditing
from grouper.fe.handlers.permission_grants_group_view import PermissionGrantsGroupView
from grouper.fe.handlers.permission_grants_service_account_view import (
    PermissionGrantsServiceAccountView,
)
from grouper.fe.handlers.permission_request import PermissionRequest
from grouper.fe.handlers.permission_view import PermissionView
from grouper.fe.handlers.permissions_create import PermissionsCreate
from grouper.fe.handlers.permissions_grant import PermissionsGrant
from grouper.fe.handlers.permissions_request_update import PermissionsRequestUpdate
from grouper.fe.handlers.permissions_requests import PermissionsRequests
from grouper.fe.handlers.permissions_revoke import PermissionsRevoke
from grouper.fe.handlers.permissions_view import PermissionsView
from grouper.fe.handlers.public_key_add import PublicKeyAdd
from grouper.fe.handlers.public_key_delete import PublicKeyDelete
from grouper.fe.handlers.role_user_view import RoleUserView
from grouper.fe.handlers.role_users_view import RoleUsersView
from grouper.fe.handlers.search import Search
from grouper.fe.handlers.service_account_create import ServiceAccountCreate
from grouper.fe.handlers.service_account_disable import ServiceAccountDisable
from grouper.fe.handlers.service_account_edit import ServiceAccountEdit
from grouper.fe.handlers.service_account_enable import ServiceAccountEnable
from grouper.fe.handlers.service_account_permission_grant import ServiceAccountPermissionGrant
from grouper.fe.handlers.service_account_permission_revoke import ServiceAccountPermissionRevoke
from grouper.fe.handlers.service_account_view import ServiceAccountView
from grouper.fe.handlers.user_disable import UserDisable
from grouper.fe.handlers.user_enable import UserEnable
from grouper.fe.handlers.user_metadata import UserMetadata
from grouper.fe.handlers.user_password_add import UserPasswordAdd
from grouper.fe.handlers.user_password_delete import UserPasswordDelete
from grouper.fe.handlers.user_requests import UserRequests
from grouper.fe.handlers.user_shell import UserShell
from grouper.fe.handlers.user_token_add import UserTokenAdd
from grouper.fe.handlers.user_token_disable import UserTokenDisable
from grouper.fe.handlers.user_view import UserView
from grouper.fe.handlers.users_public_key import UsersPublicKey
from grouper.fe.handlers.users_user_tokens import UsersUserTokens
from grouper.fe.handlers.users_view import UsersView
from grouper.handlers.health_check import HealthCheck

if TYPE_CHECKING:
    from tornado.web import RequestHandler
    from typing import List, Tuple, Type

# Regex capture groups for specific elements.
_AUDIT_ID = r"(?P<audit_id>[0-9]+)"
_KEY_ID = r"(?P<key_id>[0-9]+)"
_MAPPING_ID = r"(?P<mapping_id>[0-9]+)"
_PASSWORD_ID = r"(?P<password_id>[0-9]+)"
_REQUEST_ID = r"(?P<request_id>[0-9]+)"
_USER_ID = r"(?P<user_id>[0-9]+)"
_TOKEN_ID = r"(?P<token_id>[0-9]+)"
_TRACE_UUID = r"(?P<trace_uuid>[\-\w]+)"

# These come from grouper.constants, but we need to accept escaped @ as well, which requires some
# manipulation of the regex.
_NAME = NAME_VALIDATION.replace("@", "@%")
_SERVICE = SERVICE_ACCOUNT_VALIDATION.replace("@", "(?:@|%40)")
_USERNAME = USERNAME_VALIDATION.replace("@", "(?:@|%40)")

# This regex needs to exactly match _NAME, but the capture group should be member_name to generate
# a different argument to the route handler.
_MEMBER_NAME = _NAME.replace("<name>", "<member_name>")

# Verbatim from grouper.constants, but create an alias for consistency.
_PERMISSION = PERMISSION_VALIDATION
_METADATA_KEY = PERMISSION_VALIDATION.replace("<name>", "<key>")

HANDLERS: List[Tuple[str, Type[RequestHandler]]] = [
    ("/", Index),
    ("/audits", AuditsView),
    (f"/audits/{_AUDIT_ID}/complete", AuditsComplete),
    ("/audits/create", AuditsCreate),
    ("/debug/health", HealthCheck),
    (f"/debug/profile/{_TRACE_UUID}", PerfProfile),
    (f"/github/link_begin/{_USER_ID}", GitHubLinkBeginView),
    (f"/github/link_complete/{_USER_ID}", GitHubLinkCompleteView),
    ("/groups", GroupsView),
    (f"/groups/{_NAME}", GroupView),
    (f"/groups/{_NAME}/edit", GroupEdit),
    (f"/groups/{_NAME}/edit/(?P<member_type>user|group)/{_MEMBER_NAME}", GroupEditMember),
    (f"/groups/{_NAME}/disable", GroupDisable),
    (f"/groups/{_NAME}/enable", GroupEnable),
    (f"/groups/{_NAME}/join", GroupJoin),
    (f"/groups/{_NAME}/add", GroupAdd),
    (f"/groups/{_NAME}/remove", GroupRemove),
    (f"/groups/{_NAME}/leave", GroupLeave),
    (f"/groups/{_NAME}/requests", GroupRequests),
    (f"/groups/{_NAME}/requests/{_REQUEST_ID}", GroupRequestUpdate),
    (f"/groups/{_NAME}/service/create", ServiceAccountCreate),
    (f"/groups/{_NAME}/service/{_SERVICE}", ServiceAccountView),
    (f"/groups/{_NAME}/service/{_SERVICE}/disable", ServiceAccountDisable),
    (f"/groups/{_NAME}/service/{_SERVICE}/edit", ServiceAccountEdit),
    (f"/groups/{_NAME}/service/{_SERVICE}/revoke/{_MAPPING_ID}", ServiceAccountPermissionRevoke),
    (f"/groups/{_NAME}/service/{_SERVICE}/grant", ServiceAccountPermissionGrant),
    ("/help", Help),
    ("/permissions/create", PermissionsCreate),
    ("/permissions/request", PermissionRequest),
    ("/permissions/requests", PermissionsRequests),
    (f"/permissions/requests/{_REQUEST_ID}", PermissionsRequestUpdate),
    ("/permissions", PermissionsView),
    (f"/permissions/{_PERMISSION}", PermissionView),
    (f"/permissions/{_PERMISSION}/groups", PermissionGrantsGroupView),
    (f"/permissions/{_PERMISSION}/service_accounts", PermissionGrantsServiceAccountView),
    (f"/permissions/{_PERMISSION}/disable", PermissionDisable),
    (f"/permissions/{_PERMISSION}/enable-auditing", PermissionEnableAuditing),
    (f"/permissions/{_PERMISSION}/disable-auditing", PermissionDisableAuditing),
    (f"/permissions/grant/{_NAME}", PermissionsGrant),
    (f"/permissions/{_PERMISSION}/revoke/{_MAPPING_ID}", PermissionsRevoke),
    ("/search", Search),
    ("/users", UsersView),
    ("/service", RoleUsersView),
    (f"/service/{_USERNAME}", RoleUserView),
    (f"/service/{_USERNAME}/enable", ServiceAccountEnable),
    (f"/users/{_USERNAME}", UserView),
    (f"/users/{_USERNAME}/disable", UserDisable),
    (f"/users/{_USERNAME}/enable", UserEnable),
    (f"/users/{_USERNAME}/github/clear", UserClearGitHub),
    (f"/users/{_USERNAME}/shell", UserShell),
    (f"/users/{_USERNAME}/metadata/{_METADATA_KEY}", UserMetadata),
    (f"/users/{_USERNAME}/public-key/add", PublicKeyAdd),
    (f"/users/{_USERNAME}/public-key/{_KEY_ID}/delete", PublicKeyDelete),
    (f"/users/{_USERNAME}/tokens/add", UserTokenAdd),
    (f"/users/{_USERNAME}/tokens/{_TOKEN_ID}/disable", UserTokenDisable),
    (f"/users/{_USERNAME}/passwords/add", UserPasswordAdd),
    (f"/users/{_USERNAME}/passwords/{_PASSWORD_ID}/delete", UserPasswordDelete),
    ("/users/public-keys", UsersPublicKey),
    ("/users/tokens", UsersUserTokens),
    ("/user/requests", UserRequests),
    ("/.*", NotFound),
]
