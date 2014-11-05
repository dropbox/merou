import bittle

# These values cannot be reordered. Only add new
# capabilities to the end.
Capabilities = bittle.FlagWord([
    "user_admin",   # Allows a User to disable/enable any User account
                    # as well as set/unset capabilities on a User account.
    "group_admin",  # Allows a User to approve/deny/revoke membership to
                    # any group.
    "permission_admin",  # Allows a User to manipulate any permission.
])
