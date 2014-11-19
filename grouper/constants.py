
# These regexes must not include line anchors ('^', '$'). Those will be added by the
# ValidateRegex library function and anybody else who needs them.
USER_VALIDATION = r"(?P<username>[\-\w\.]+)"
GROUP_VALIDATION = r"(?P<groupname>[\-\w\.]+)"
# TODO: probably need a PERMISSION_WILDCARD which allows 'foo.*' and PERMISSION shouldn't
PERMISSION_VALIDATION = r"(?P<name>(?:[a-z0-9]+[_\-\.]?)*[a-z0-9]+(?:\.\*)?)"
ARGUMENT_VALIDATION = r"(?P<argument>|\*|(?:[a-z0-9]+[_\-\.]?)*[a-z0-9]+(?:\.\*)?)"

# Permissions that are always created and are reserved.
SYSTEM_PERMISSIONS = [
    ('grouper.permission.create', 'Ability to create permissions within Grouper.'),
    ('grouper.permission.grant', 'Ability to grant a permission to a group.'),
]

# A list of regular expressions that are reserved anywhere names are created. I.e., if a regex
# in this list is matched, a permission cannot be created in the UI. Same with group names.
# These are case insensitive.
RESERVED_NAMES = [
    r"^grouper",
    r"^admin",
    r"^test",
]
