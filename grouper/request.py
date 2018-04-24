from typing import TYPE_CHECKING

from grouper.models.base.constants import OBJ_TYPES_IDX
from grouper.models.group import Group
from grouper.models.user import User

if TYPE_CHECKING:
    from typing import Union  # noqa: F401
    from sqlalchemy.orm import Session  # noqa: F401
    from grouper.models.request import Request  # noqa: F401


def get_on_behalf_by_request(session, request):
    # type: (Session, Request) -> Union[User,Group]
    obj_type = OBJ_TYPES_IDX[request.on_behalf_obj_type]

    if obj_type == "User":
        obj = User
    elif obj_type == "Group":
        obj = Group

    return session.query(obj).filter_by(
        id=request.on_behalf_obj_pk
    ).scalar()
