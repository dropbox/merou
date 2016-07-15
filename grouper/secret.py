import copy
from enum import Enum
from sqlalchemy.orm import Session  # noqa
from typing import Any  # noqa

from grouper.constants import SECRETS_ADMIN
from grouper.fe.forms import SecretForm
from grouper.group import get_all_groups
from grouper.model_soup import Group
from grouper.models.user import User  # noqa
from grouper.user_group import get_groups_by_user
from grouper.user_permissions import user_has_permission


class SecretError(Exception):
    """Base exception for all exceptions related to secrets. This should be used
    by plugins when raising secret related exceptions as well.
    """
    pass


class SecretRiskLevel(Enum):
    """Risk levels that secrets can have"""
    low = 1
    medium = 2
    high = 3


class Secret(object):
    """This class is the base interface that Grouper uses for all actions involving secrets.
    All instances where Grouper expects a secret from a plugin MUST return an object that
    implements this entire interface (supersets are of course allowed).
    """

    form = SecretForm

    def __init__(self,
                 name,            # type: str
                 distribution,    # type: List[str]
                 owner,           # type: Group
                 notes,           # type: str
                 risk_level,      # type: int
                 risk_info,       # type: str
                 uses,            # type: str
                 new=False        # type: boolean
                 ):
        # type: (...) -> None
        """Creates a new secret object obviously.

        Args:
            name: The name of the secret.
            distribution: A list of strings describing how this secret should be distributed. The
                plugin is responsible for deciding how to interpret this information.
            owner: The group which owns (and is responsible for) this secret.
            notes: Miscellaneous information about the secret.
            risk_level: How bad it would be if this secret was disclosed.
            risk_info: Information about why this secret has that level
            uses: Information about where and how this secret is used.
        """
        self.name = name
        self.distribution = distribution
        self.owner = owner
        self.notes = notes
        self.risk_level = risk_level
        self.risk_info = risk_info
        self.uses = uses
        self.new = new

    def get_secrets_form(self, session, user):
        # type: (Session, User) -> SecretForm
        """Returns the SecretForm representation of this secret object.

        The returned value may be a subclass of SecretForm, and is used for
        autofilling forms when editing information about this secret. This
        also properly sets the choices for all select types for when this
        form is validated.

        Args:
            session: database session
            user: the user that is viewing the form

        Returns:
            A SecretForm with fields prefilled by this object's values
        """
        return self._get_secrets_form_generic(session, user, obj=self)

    @classmethod
    def get_secrets_form_args(cls, session, user, args):
        # type: (Session, User, Dict[str, Any]) -> SecretForm
        """Returns a SecretForm filled out with args.

        The returned value may be a subclass of SecretForm, and is used for
        autofilling forms when editing information about this secret. This
        also properly sets the choices for all select types for when this
        form is validated.

        Args:
            session: database session
            user: the user that is viewing the form
            args: the arguments we're filling into the form

        Returns:
            A SecretForm with fields prefilled with the values in args
        """
        return cls._get_secrets_form_generic(session, user, args)

    @classmethod
    def _get_secrets_form_generic(cls, session, user, args={}, obj=None):
        # type: (Session, User, Dict[str, Any], Secret) -> SecretForm
        """Returns a SecretForm filled out with either args or obj.

        The returned value may be a subclass of SecretForm, and is used for
        autofilling forms when editing information about this secret. This
        also properly sets the choices for all select types for when this
        form is validated.

        Args:
            session: database session
            user: the user that is viewing the form
            args: the arguments we're filling into the form
            obj: a Secret object whose values are filled into the form

        Returns:
            A SecretForm with fields prefilled by either the object's or arg's values
        """
        if obj:
            # Don't want to modify the object we're given
            obj = copy.copy(obj)
            # The form expects the owner to be an id, not a Group
            obj.owner = obj.owner.id
            # The form expects the distribution to be a single string with newlines
            obj.distribution = "\r\n".join(obj.distribution)
        form = cls.form(args, obj=obj)

        form.owner.choices = [[-1, "(select one)"]]
        user_groups = [group for group, group_edge in get_groups_by_user(session, user)]
        is_secret_admin = user_has_permission(session, user, SECRETS_ADMIN)

        # For secret admins, put a star next to groups they're in
        prefix = "* " if is_secret_admin else ""
        for group, group_edge in get_groups_by_user(session, user):
            form.owner.choices.append([int(group.id), prefix + group.name])

        if is_secret_admin:
            for group in get_all_groups(session):
                if group not in user_groups:
                    form.owner.choices.append([int(group.id), group.name])

        form.risk_level.choices = [[-1, "(select one)"]]
        for level in SecretRiskLevel:  # type: ignore: iterating through enums is well defined
            form.risk_level.choices.append([level.value, level.name])

        return form

    @classmethod
    def secret_from_form(cls, session, form, new):
        # type: (Session, SecretForm, bool) -> Secret
        """Returns a Secret (or subclass) derived from the values in the form.

        Args:
            session: database session
            form: the form with the necessary values
            new: whether this is a new Secret

        Returns:
            A Secret filled out with the data in form
        """
        return cls(**cls.args_from_form(session, form, new))

    @classmethod
    def args_from_form(cls, session, form, new):
        # type: (Session, SecretForm, bool) -> Dict[str, Any]
        """Returns a dictionary that can be used as kwargs to construct a
        Secret derived from the values in the form.

        Args:
            session: database session
            form: the form with the necessary values
            new: whether this is a new Secret

        Returns:
            A dictionary filled out with the data in the form
        """
        return {
            "name": form.data["name"],
            "distribution": form.data["distribution"].split("\r\n"),
            "owner": Group.get(session, pk=form.data["owner"]),
            "notes": form.data["notes"],
            "risk_level": form.data["risk_level"],
            "risk_info": form.data["risk_info"],
            "uses": form.data["uses"],
            "new": new,
        }

    def __repr__(self):
        "{}({})".format(self.__name__, self.name)
