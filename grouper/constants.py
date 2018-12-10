# These regexes must not include line anchors ('^', '$'). Those will be added by the
# ValidateRegex library function and anybody else who needs them.

_NAME_VALIDATION = r"(?P<{}>[@\-\w\.]+)"
NAME_VALIDATION = _NAME_VALIDATION.format("name")

# This regex needs to exactly match the above, EXCEPT that the name should be "name2".
# This is kind of gross. :\ We have to do this because the name of the capture group becomes the
# argument to route handler, named arguments have to be unique, and at least one route (edit
# member) requires occurrences of the name validation regex.
NAME2_VALIDATION = _NAME_VALIDATION.format("name2")

# These regexes are specifically to validate usernames.  SERVICE_ACCOUNT_VALIDATION is the same as
# USERNAME_VALIDATION but with a distinct capture group name so that it doesn't conflict with a
# NAME_VALIDATION regex in the same URL.
USERNAME_VALIDATION = r"(?P<name>[\w-]+@\w+[\.\w]+)"
SERVICE_ACCOUNT_VALIDATION = r"(?P<accountname>[\w-]+@\w+[\.\w]+)"

# UserToken validators
TOKEN_SECRET_VALIDATION = r"(?P<token_secret>[a-f0-9]{40})"
TOKEN_NAME_VALIDATION = r"(?P<token_name>[A-Za-z0-9]+)"
TOKEN_FORMAT = r"^{}/{}:{}$".format(
    USERNAME_VALIDATION,
    TOKEN_NAME_VALIDATION,
    TOKEN_SECRET_VALIDATION,
)

# Regexes for validating permission/argument names
PERMISSION_VALIDATION = r"(?P<name>(?:[a-z0-9]+[_\-\.])*[a-z0-9]+)"
PERMISSION_WILDCARD_VALIDATION = r"(?P<name>(?:[a-z0-9]+[_\-\.])*[a-z0-9]+(?:\.\*)?)"
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
TAG_EDIT = "grouper.tag.edit"

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
    (TAG_EDIT, "Ability to edit the permissions granted to a tag."),
]

# Used to construct name tuples in notification engine.
ILLEGAL_NAME_CHARACTER = '|'

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

# Maximum length a name can be. This applies to user names and permission arguments.
MAX_NAME_LENGTH = 128

# Grouper used UserMetadata data_keys
USER_METADATA_SHELL_KEY = "shell"
