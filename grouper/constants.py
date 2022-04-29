# These regexes must not include line anchors ('^', '$'). Those will be added by the
# ValidateRegex library function and anybody else who needs them.

# Used for group names.
NAME_VALIDATION = r"(?P<name>[@\-\w\.]+)"

# These regexes are specifically to validate usernames.  SERVICE_ACCOUNT_VALIDATION is the same as
# USERNAME_VALIDATION but with a distinct capture group name so that it doesn't conflict with a
# NAME_VALIDATION regex in the same URL.
#
# This matches a subset of valid email addresses, currently matching Dropbox internal needs, and
# may need to become more flexible in the future (via configuration, for instance).  It disallows
# periods in the LHS of the identity for Dropbox policy reasons.
#
# + is disallowed in the LHS of the email address on the grounds that for the internal corporate
# use case, it doesn't make sense to allow people to create a user whose identity is an alias, or
# to allow people to potentially create multiple users mapping to the same underlying account.
USERNAME_VALIDATION = r"(?P<name>[\w-]+@(?:[\w\-]+\.)+\w{2,})"
SERVICE_ACCOUNT_VALIDATION = r"(?P<accountname>[\w-]+@(?:[\w\-]+\.)+\w{2,})"

# UserToken validators
TOKEN_SECRET_VALIDATION = r"(?P<token_secret>[a-f0-9]{40})"
TOKEN_NAME_VALIDATION = r"(?P<token_name>[A-Za-z0-9]+)"
TOKEN_FORMAT = r"^{}/{}:{}$".format(
    USERNAME_VALIDATION, TOKEN_NAME_VALIDATION, TOKEN_SECRET_VALIDATION
)

# Regexes for validating permission/argument names
PERMISSION_VALIDATION = r"(?P<name>(?:[a-z0-9]+[_\-\.])*[a-z0-9]+)"
ARGUMENT_VALIDATION = r"(?P<argument>|[\^\*\w\[\]\$=+/.: -]+)"

# Global permission names to prevent stringly typed things
PERMISSION_GRANT = "grouper.permission.grant"
PERMISSION_CREATE = "grouper.permission.create"
PERMISSION_AUDITOR = "grouper.permission.auditor"
PERMISSION_ADMIN = "grouper.admin.permissions"
USER_ADMIN = "grouper.admin.users"
GROUP_ADMIN = "grouper.admin.groups"
AUDIT_SECURITY = "grouper.audit.security"
AUDIT_MANAGER = "grouper.audit.manage"
AUDIT_VIEWER = "grouper.audit.view"
USER_DISABLE = "grouper.user.disable"
USER_ENABLE = "grouper.user.enable"

# Permissions that are always created and are reserved.
SYSTEM_PERMISSIONS = [
    (PERMISSION_CREATE, "Ability to create permissions within Grouper."),
    (PERMISSION_GRANT, "Ability to grant a permission to a group."),
    (PERMISSION_AUDITOR, "Ability to own or manage groups with audited permissions."),
    (PERMISSION_ADMIN, "Ability to manipulate any permission."),
    (USER_ADMIN, "Ability to to disable/enable any User account and modify its attributes."),
    (GROUP_ADMIN, "Ability to approve/deny/revoke membership to any group."),
    (AUDIT_SECURITY, "Ability to audit security related activity on the system."),
    (AUDIT_MANAGER, "Ability to start and view global audits, and toggle if a perm is audited."),
    (AUDIT_VIEWER, "Ability to view audit results and status."),
    (USER_ENABLE, "Ability to enable a disabled user without preserving group membership."),
    (USER_DISABLE, "Ability to disable an enabled user."),
]

# The name of the administrator group that's created during schema initialization.  (Grouper
# doesn't depend on the name of this group and is happy for it to be renamed later.)
DEFAULT_ADMIN_GROUP = "grouper-administrators"

# Used to construct name tuples in notification engine.
ILLEGAL_NAME_CHARACTER = "|"

# A list of regular expressions that are reserved anywhere names are created. I.e., if a regex
# in this list is matched, a permission cannot be created in the UI. Same with group names.
# These are case insensitive.
RESERVED_NAMES = [
    r"^grouper",
    r"^admin",
    r"^test",
    r"^[^.]*$",
    r"^[0-9]+$",  # Reserved in order to select user or group by id.
    r".*\|.*",
]

# Maximum length a name can be. This applies to user names.
MAX_NAME_LENGTH = 128

# Maximum length a permission argument can be. This applies to permission_requests and
# permissions_map arguments.
MAX_ARGUMENT_LENGTH = 128

# Grouper used UserMetadata data_keys
USER_METADATA_SHELL_KEY = "shell"
USER_METADATA_GITHUB_USERNAME_KEY = "github_username"
