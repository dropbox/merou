
# These regexes must not include line anchors ('^', '$'). Those will be added by the
# ValidateRegex library function and anybody else who needs them.
NAME_VALIDATION = r"(?P<name>[@\-\w\.]+)"

# This regex needs to exactly match the above, EXCEPT that the name should be "name2". So if the
# above regex changes, change this one. This is kind of gross. :\
NAME2_VALIDATION = r"(?P<name2>[@\-\w\.]+)"

# Regexes for validating permission/argument names
PERMISSION_VALIDATION = r"(?P<name>(?:[a-z0-9]+[_\-\.]?)*[a-z0-9]+)"
PERMISSION_WILDCARD_VALIDATION = r"(?P<name>(?:[a-z0-9]+[_\-\.]?)*[a-z0-9]+(?:\.\*)?)"
ARGUMENT_VALIDATION = r"(?P<argument>|\*|[\w=/.:-]+\*?)"

# Global permission names to prevent stringly typed things
PERMISSION_GRANT = "grouper.permission.grant"
PERMISSION_CREATE = "grouper.permission.create"
PERMISSION_AUDITOR = "grouper.permission.auditor"

# Permissions that are always created and are reserved.
SYSTEM_PERMISSIONS = [
    (PERMISSION_CREATE, "Ability to create permissions within Grouper."),
    (PERMISSION_GRANT, "Ability to grant a permission to a group."),
    (PERMISSION_AUDITOR, "Ability to own or manage groups with audited permissions."),
]

# A list of regular expressions that are reserved anywhere names are created. I.e., if a regex
# in this list is matched, a permission cannot be created in the UI. Same with group names.
# These are case insensitive.
RESERVED_NAMES = [
    r"^grouper",
    r"^admin",
    r"^test",
]

# Maximum length a name can be. This applies to user names and permission arguments.
MAX_NAME_LENGTH = 128
