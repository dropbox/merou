import traceback

from expvar.stats import stats
from tornado.web import RequestHandler, HTTPError

from ..models import get_plugins
from ..util import try_update


class GraphHandler(RequestHandler):
    def initialize(self):
        self.graph = self.application.my_settings.get("graph")
        stats.incr("requests")

    def error(self, errors):
        errors = [
            {"code": code, "message": message} for code, message in errors
        ]
        with self.graph.lock:
            checkpoint = self.graph.checkpoint
            checkpoint_time = self.graph.checkpoint_time
            self.write({
                "status": "error",
                "errors": errors,
                "checkpoint": checkpoint,
                "checkpoint_time": checkpoint_time,
            })

    def success(self, data):
        with self.graph.lock:
            checkpoint = self.graph.checkpoint
            checkpoint_time = self.graph.checkpoint_time
            self.write({
                "status": "ok",
                "data": data,
                "checkpoint": checkpoint,
                "checkpoint_time": checkpoint_time,
            })

    def notfound(self, message):
        self.set_status(404)
        self.log_error(HTTPError(404))
        self.error([(404, message)])

    # Overrides tornado's uncaught exception handler.
    def log_exception(self, typ, value, tb):
        self.set_status(500)
        self.log_error(value, tb)
        self.error([(500, traceback.format_exception_only(typ, value))])
        self.finish()

    # Give plugins a chance to provide site-specific error handling.
    def log_error(self, exception, tb=None):
        if tb is None:
            stack = traceback.extract_stack()
        else:
            stack = traceback.extract_tb(tb)
        status = self.get_status()
        for plugin in get_plugins():
            plugin.log_exception(self.request, status, exception, stack)


class Users(GraphHandler):
    def get(self, name=None):
        cutoff = int(self.get_argument("cutoff", 100))
        include_role_users = self.get_argument("include_role_users", "no") == "yes"

        with self.graph.lock:
            if not name:
                return self.success({
                    "users": sorted([k
                                     for k,v in self.graph.user_metadata.iteritems()
                                     if include_role_users or (not v["role_user"])]),
                })

            if name in self.graph.user_metadata:
                md = self.graph.user_metadata[name]
                details = self.graph.get_user_details(name, cutoff)
            else:
                return self.notfound("User (%s) not found." % name)
            out = {"user": {"name": name}}
            try_update(out["user"], md)
            try_update(out, details)
            return self.success(out)


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
            try_update(out["permission"], self.graph.permission_metadata.get(name, {}))
            try_update(out, details)
            return self.success(out)


# Don't use GraphHandler here as we don't want to count
# these as requests.
class Stats(RequestHandler):
    def get(self):
        return self.write(stats.to_dict())


class NotFound(GraphHandler):
    def get(self):
        return self.notfound("Endpoint not found")
