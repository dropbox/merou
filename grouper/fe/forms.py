from datetime import datetime
import re
import sshpubkey

from wtforms import SelectField, TextField, TextAreaField, validators
from wtforms.validators import ValidationError
from wtforms_tornado import Form

from .. import constants
from .. import models


class ValidateRegex(object):
    def __init__(self, regex):
        # We assume any regex passed to us does not have line anchors.
        self.regex = r'^' + regex + r'$'
        self._re = re.compile(self.regex)

    def __call__(self, form, field):
        if not self._re.match(field.data):
            raise ValidationError("Field must match '{}'".format(self.regex))


class ValidateDate(object):
    def __call__(self, form, field):
        try:
            if field.data:
                datetime.strptime(field.data, "%m/%d/%Y")
        except ValueError:
            raise ValidationError(
                "{} does not match format 'MM/DD/YYYY'".format(field.data))


class ValidatePublicKey(object):
    # TODO: Add ability to specify things like bit depth, key type, etc, as requirements
    # for what kind of keys are allowed.
    def __call__(self, form, field):
        try:
            sshpubkey.PublicKey.from_str(field.data)
        except sshpubkey.exc.PublicKeyParseError:
            raise ValidationError("Public key appears to be invalid.")


class PublicKeyForm(Form):
    public_key = TextAreaField("Public Key", [
        validators.Required(),
        ValidatePublicKey(),
    ])


class PermissionGrantForm(Form):
    permission = SelectField("Permission", [
        validators.Required(),
    ], choices=[["", "(select one)"]], default="")
    argument = TextField("Argument", [
        validators.Length(min=0, max=128),
        ValidateRegex(constants.ARGUMENT_VALIDATION),
    ])


class PermissionForm(Form):
    name = TextField("Name", [
        validators.Length(min=3, max=64),
        validators.Required(),
        ValidateRegex(constants.PERMISSION_VALIDATION),
    ])
    description = TextAreaField("Description")


class GroupForm(Form):
    groupname = TextField("Name", [
        validators.Length(min=3, max=32),
        validators.Required(),
        ValidateRegex(constants.GROUP_VALIDATION),
    ])
    description = TextAreaField("Description")
    canjoin = SelectField("Who Can Join?", choices=[
        ("canjoin", "Anyone"), ("canask", "Must Ask"),
    ], default="canask")


class GroupRequestModifyForm(Form):
    status = SelectField("New Status", [
        validators.Required(),
    ])
    reason = TextAreaField("Reason", [
        validators.Required(),
    ])


class GroupJoinForm(Form):
    member = SelectField("Member", [
        validators.Length(min=3, max=32),
        validators.Required(),
        ValidateRegex(r"(?:User|Member): {}".format(constants.GROUP_VALIDATION)),
    ])
    role = SelectField("Role", [
        validators.Length(min=3, max=32),
        validators.Required(),
    ], choices=[
        (role, role.title())
        for role in models.GROUP_EDGE_ROLES
    ], default="member")
    reason = TextAreaField("Reason", [
        validators.Required(),
    ])
    expiration = TextField("Expiration", [
        ValidateDate(),
    ], id="join-form-expiration")
