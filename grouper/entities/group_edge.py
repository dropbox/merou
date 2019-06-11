# TODO(rra): This should be an enum, but quite a lot of code currently uses it as a lookup table by
# index, using the index as the database representation of the role.  THE ORDER IS SIGNIFICANT,
# since it determines the database representation.  Any new role MUST be added to the end, and
# added to relevant tests.
GROUP_EDGE_ROLES = (
    "member",  # Belongs to the group. Nothing more.
    "manager",  # Make changes to the group / Approve requests.
    "owner",  # Same as manager plus enable/disable group and make Users owner.
    "np-owner",  # Same as owner but don't inherit permissions.
)

# Numeric indices into GROUP_EDGE_ROLES that can act as group owner.
OWNER_ROLE_INDICES = {GROUP_EDGE_ROLES.index("owner"), GROUP_EDGE_ROLES.index("np-owner")}

# Numeric indices into GROUP_EDGE_ROLES that can approve membership requests.
APPROVER_ROLE_INDICES = {
    GROUP_EDGE_ROLES.index("owner"),
    GROUP_EDGE_ROLES.index("np-owner"),
    GROUP_EDGE_ROLES.index("manager"),
}
