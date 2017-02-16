from cStringIO import StringIO
import csv
import re

import sshpubkey
from typing import Optional  # noqa

from grouper.api.handler_base import GraphHandler
from grouper.constants import TOKEN_FORMAT
from grouper.models.base.session import Session
from grouper.models.public_key import PublicKey
from grouper.models.user import User
from grouper.models.user_token import UserToken
from grouper.perf_profile import get_stopwatch as sw
from grouper.util import try_update



def get_individual_user_info(handler, name, cutoff, service_account):
    # type: (GraphHandler, str, int, Optional[bool]) -> None
    """This is a helper function to consolidate duplicate code from the service account and user
    endpoints into one location.

    Args:
        handler: the GraphHandler for this request
        name: the name we're looking up for this request
        cutoff: the maximum distance of groups to use for permission checking
        service_account: a boolean indicating if this request is for a service account or not. This
            can be None if you want to support users and service accounts (deprecated)

    Returns:
        None
    """
    acc = "Service Account" if service_account else "User"
    with handler.graph.lock, sw().timer('single_user_info'):
        if name not in handler.graph.user_metadata:
            return handler.notfound("{} ({}) not found.".format(acc, name))
        md = handler.graph.user_metadata[name]
        if service_account is not None and md["role_user"] != service_account:
            return handler.notfound("{} ({}) not found.".format(acc, name))

        details = handler.graph.get_user_details(name, cutoff)
        out = {"user": {"name": name}}
        # Updates the output with the user's metadata
        try_update(out["user"], md)
        # Updates the output with the user's details (such as permissions)
        try_update(out, details)
        return handler.success(out)


class Users(GraphHandler):
    def get(self, name=None):
        cutoff = int(self.get_argument("cutoff", 100))
        # Deprecated 2016-08-10, use the ServiceAccounts endpoint to lookup service accounts
        include_service_accounts = self.get_argument("include_role_users", "no") == "yes"

        if name is not None:
            # We don't require `include_service_accounts` when querying for a specific user,
            # because there are too many existing integrations that expect the
            # /users/foo@example.com endpoint to work for both. :(
            return get_individual_user_info(self, name, cutoff, service_account=None)

        with self.graph.lock:
            return self.success({
                "users": sorted([k
                                for k, v in self.graph.user_metadata.iteritems()
                                if (include_service_accounts or not v["role_user"])]),
            })


class UsersPublicKeys(GraphHandler):
    def get(self):
        fh = StringIO()
        w_csv = csv.writer(fh, lineterminator="\n")

        # header
        w_csv.writerow([
            'username',
            'created_at',
            'type',
            'size',
            'fingerprint',
            'comment',
            ])

        user_key_list = Session().query(PublicKey, User).filter(User.id == PublicKey.user_id)
        for key, user in user_key_list:
            w_csv.writerow([
                user.name,
                key.created_on.isoformat(),
                key.key_type,
                key.key_size,
                key.fingerprint,
                sshpubkey.PublicKey.from_str(key.public_key).comment,
                ])

        self.set_header("Content-Type", "text/csv")
        self.write(fh.getvalue())


class Groups(GraphHandler):
    def get(self, name=None):
        cutoff = int(self.get_argument("cutoff", 100))

        with self.graph.lock:
            if not name:
                return self.success({
                    "groups": [
                        group
                        for group in self.graph.groups
                    ],
                })

            if name not in self.graph.groups:
                return self.notfound("Group (%s) not found." % name)

            details = self.graph.get_group_details(name, cutoff)

            out = {"group": {"name": name}}
            try_update(out["group"], self.graph.group_metadata.get(name, {}))
            try_update(out, details)
            return self.success(out)


class Permissions(GraphHandler):
    def get(self, name=None):
        with self.graph.lock:
            if not name:
                return self.success({
                    "permissions": [
                        permission
                        for permission in self.graph.permissions
                    ],
                })

            if name not in self.graph.permissions:
                return self.notfound("Permission (%s) not found." % name)

            details = self.graph.get_permission_details(name)

            out = {"permission": {"name": name}}
            try_update(out, details)
            return self.success(out)


class TokenValidate(GraphHandler):
    validator = re.compile(TOKEN_FORMAT)

    def post(self):
        supplied_token = self.get_body_argument("token")
        match = TokenValidate.validator.match(supplied_token)
        if not match:
            return self.error(((1, "Token format not recognized"),))

        sess = Session()

        token_name = match.group("token_name")
        token_secret = match.group("token_secret")
        owner = User.get(sess, name=match.group("name"))

        token = UserToken.get(sess, owner, token_name)
        if token is None:
            return self.error(((2, "Token specified does not exist"),))
        if not token.enabled:
            return self.error(((3, "Token is disabled"),))
        if not token.check_secret(token_secret):
            return self.error(((4, "Token secret mismatch"),))

        return self.success({
            "owner": owner.username,
            "identity": str(token),
            "act_as_owner": True,
            "valid": True,
        })


class ServiceAccounts(GraphHandler):
    def get(self, name=None):
        cutoff = int(self.get_argument("cutoff", 100))
        if name is not None:
            return get_individual_user_info(self, name, cutoff, service_account=True)

        with self.graph.lock:
            return self.success({
                "service_accounts": sorted([k
                                for k, v in self.graph.user_metadata.iteritems()
                                if v["role_user"]]),
            })


class NotFound(GraphHandler):
    def get(self):
        return self.notfound("Endpoint not found")
