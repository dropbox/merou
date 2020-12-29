from urllib.parse import urlencode

from sqlalchemy import union_all
from sqlalchemy.sql import label, literal

from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.user import User


class Search(GrouperHandler):
    def get(self):
        query = self.get_argument("query", "")
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

        groups = (
            self.session.query(
                label("type", literal("Group")),
                label("id", Group.id),
                label("name", Group.groupname),
            )
            .filter(Group.enabled == True, Group.groupname.like("%{}%".format(query)))
            .subquery()
        )

        permission_query = query.split("=")[0] if "=" in query else query
        permissions = (
            self.session.query(
                label("type", literal("Permission")),
                label("id", Permission.id),
                label("name", Permission.name),
            )
            .filter(
                Permission.enabled == True, Permission.name.like("%{}%".format(permission_query))
            )
            .subquery()
        )

        users = (
            self.session.query(
                label("type", literal("User")), label("id", User.id), label("name", User.username)
            )
            .filter(User.enabled == True, User.username.like("%{}%".format(query)))
            .subquery()
        )

        results_query = self.session.query("type", "id", "name").select_entity_from(
            union_all(users.select(), permissions.select(), groups.select())
        )
        total = results_query.count()
        results = results_query.offset(offset).limit(limit).all()

        if len(results) == 1:
            result = results[0]

            encoded_params = ""
            if result.type.lower() == "permission" and "=" in query:
                encoded_params = "?" + urlencode({"argument": query.split("=", 1)[1]})

            base_url = "/{}s/{}".format(result.type.lower(), result.name)
            return self.redirect(base_url + encoded_params)

        self.render(
            "search.html",
            results=results,
            search_query=query,
            offset=offset,
            limit=limit,
            total=total,
        )
