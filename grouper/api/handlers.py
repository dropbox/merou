from expvar.stats import stats
from tornado.web import RequestHandler


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
        self.error([(404, message)])


class Users(GraphHandler):
    def get(self, username=None):
        cutoff = int(self.get_argument("cutoff", 100))

        with self.graph.lock:
            if not username:
                return self.success({
                    "users": [
                        user
                        for user in self.graph.users
                    ],
                })

            if username not in self.graph.users:
                return self.notfound("User (%s) not found." % username)

            details = self.graph.get_user_details(username, cutoff)

            out = {"user": {"name": username}}
            out["user"].update(self.graph.user_metadata.get(username, {}))
            out.update(details)
            return self.success(out)


class Groups(GraphHandler):
    def get(self, groupname=None):
        cutoff = int(self.get_argument("cutoff", 100))

        with self.graph.lock:
            if not groupname:
                return self.success({
                    "groups": [
                        group
                        for group in self.graph.groups
                    ],
                })

            if groupname not in self.graph.groups:
                return self.notfound("Group (%s) not found." % groupname)

            details = self.graph.get_group_details(groupname, cutoff)

            out = {"group": {"name": groupname}}
            out.update(details)
            return self.success(out)


# Don't use GraphHandler here as we don't want to count
# these as requests.
class Stats(RequestHandler):
    def get(self):
        return self.write(stats.to_dict())


class NotFound(GraphHandler):
    def get(self):
        return self.notfound("Endpoint not found")
