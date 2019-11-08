"""Routes and handlers for the Grouper frontend.

Provides the variable HANDLERS, which contains tuples of route regexes and handlers.  Do not
provide additional handler arguments as a third argument of the tuple.  A standard set of
additional arguments will be injected when the Tornado Application object is created.
"""

from typing import TYPE_CHECKING

from grouper.constants import (
    NAME2_VALIDATION,
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

HANDLERS = [
    (r"/", Index),
    (r"/audits", AuditsView),
    (r"/audits/(?P<audit_id>[0-9]+)/complete", AuditsComplete),
    (r"/audits/create", AuditsCreate),
    (r"/github/link_begin/(?P<user_id>[0-9]+)", GitHubLinkBeginView),
    (r"/github/link_complete/(?P<user_id>[0-9]+)", GitHubLinkCompleteView),
    (r"/groups", GroupsView),
    (r"/groups/{}/service/create".format(NAME_VALIDATION), ServiceAccountCreate),
    (
        r"/groups/{}/service/{}/grant".format(NAME_VALIDATION, SERVICE_ACCOUNT_VALIDATION),
        ServiceAccountPermissionGrant,
    ),
    (r"/permissions/create", PermissionsCreate),
    (r"/permissions/request", PermissionRequest),
    (r"/permissions/requests", PermissionsRequests),
    (r"/permissions/requests/(?P<request_id>[0-9]+)", PermissionsRequestUpdate),
    (r"/permissions/{}".format(PERMISSION_VALIDATION), PermissionView),
    (r"/permissions", PermissionsView),
    (r"/permissions/{}/disable".format(PERMISSION_VALIDATION), PermissionDisable),
    (r"/permissions/{}/enable-auditing".format(PERMISSION_VALIDATION), PermissionEnableAuditing),
    (r"/permissions/{}/disable-auditing".format(PERMISSION_VALIDATION), PermissionDisableAuditing),
    (r"/permissions/grant/{}".format(NAME_VALIDATION), PermissionsGrant),
    (
        r"/permissions/{}/revoke/(?P<mapping_id>[0-9]+)".format(PERMISSION_VALIDATION),
        PermissionsRevoke,
    ),
    (r"/search", Search),
    (r"/users", UsersView),
    (r"/service", RoleUsersView),
    (r"/users/public-keys", UsersPublicKey),
    (r"/users/tokens", UsersUserTokens),
    (r"/user/requests", UserRequests),
]  # type: List[Tuple[str, Type[RequestHandler]]]

# We currently allow users to be referenced by either the name or the user ID, but it's not clear
# the latter is ever useful and it leaks database user IDs into the UI.  Consider moving any new
# routes into the HANDLERS definition above using only USERNAME_VALIDATION.
for regex in (r"(?P<user_id>[0-9]+)", USERNAME_VALIDATION):
    HANDLERS.extend(
        [
            (r"/users/{}".format(regex), UserView),
            (r"/users/{}/disable".format(regex), UserDisable),
            (r"/users/{}/enable".format(regex), UserEnable),
            (r"/users/{}/github/clear".format(regex), UserClearGitHub),
            (r"/users/{}/shell".format(regex), UserShell),
            (r"/users/{}/public-key/add".format(regex), PublicKeyAdd),
            (r"/users/{}/public-key/(?P<key_id>[0-9]+)/delete".format(regex), PublicKeyDelete),
            (r"/users/{}/tokens/add".format(regex), UserTokenAdd),
            (r"/users/{}/tokens/(?P<token_id>[0-9]+)/disable".format(regex), UserTokenDisable),
            (r"/users/{}/passwords/add".format(regex), UserPasswordAdd),
            (r"/users/{}/passwords/(?P<pass_id>[0-9]+)/delete".format(regex), UserPasswordDelete),
            (r"/service/{}".format(regex), RoleUserView),
            (r"/service/{}/enable".format(regex), ServiceAccountEnable),
        ]
    )

# We currently allow groups to be referenced by either the name or the group ID, but it's not clear
# the latter is ever useful and it leaks database group IDs into the UI.  Consider moving any new
# routes into the HANDLERS definition above using only NAME_VALIDATION.
for regex in (r"(?P<group_id>[0-9]+)", NAME_VALIDATION):
    HANDLERS.extend(
        [
            (r"/groups/{}".format(regex), GroupView),
            (r"/groups/{}/edit".format(regex), GroupEdit),
            (
                r"/groups/{}/edit/(?P<member_type>user|group)/{}".format(regex, NAME2_VALIDATION),
                GroupEditMember,
            ),
            (r"/groups/{}/disable".format(regex), GroupDisable),
            (r"/groups/{}/enable".format(regex), GroupEnable),
            (r"/groups/{}/join".format(regex), GroupJoin),
            (r"/groups/{}/add".format(regex), GroupAdd),
            (r"/groups/{}/remove".format(regex), GroupRemove),
            (r"/groups/{}/leave".format(regex), GroupLeave),
            (r"/groups/{}/requests".format(regex), GroupRequests),
            (r"/groups/{}/requests/(?P<request_id>[0-9]+)".format(regex), GroupRequestUpdate),
        ]
    )

# We currently allow groups and service accounts to be referenced by either the name or the group
# or user ID, but it's not clear the latter is ever useful and it leaks database group and user IDs
# into the UI.  Consider moving any new routes into the HANDLERS definition above using only
# NAME_VALIDATION and SERVICE_ACCOUNT_VALIDATION.
for regex in (r"(?P<group_id>[0-9]+)", NAME_VALIDATION):
    for service_regex in (r"(?P<account_id>[0-9]+)", SERVICE_ACCOUNT_VALIDATION):
        HANDLERS.extend(
            [
                (r"/groups/{}/service/{}".format(regex, service_regex), ServiceAccountView),
                (
                    r"/groups/{}/service/{}/disable".format(regex, service_regex),
                    ServiceAccountDisable,
                ),
                (r"/groups/{}/service/{}/edit".format(regex, service_regex), ServiceAccountEdit),
                (
                    r"/groups/{}/service/{}/revoke/(?P<mapping_id>[0-9]+)".format(
                        regex, service_regex
                    ),
                    ServiceAccountPermissionRevoke,
                ),
            ]
        )

HANDLERS.extend(
    [
        (r"/help", Help),
        (r"/debug/health", HealthCheck),
        (r"/debug/profile/(?P<trace_uuid>[\-\w]+)", PerfProfile),
        (r"/.*", NotFound),
    ]
)
