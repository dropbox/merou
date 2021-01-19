"""Wrappers around Jinja2 templates in the templates subdirectory.

This is a not-yet-fully-complete experiment in improving typing and code safety for rendering
Jinja2 templates.  The goal is for every template page to have a corresponding wrapper class
defined here, and for all handlers to interact with the template only through the wrapper class.
This ensures that the template receives all of the parameters that it expects and that they are
typed correctly, since mypy cannot analyze Jinja2 code.

Keep all wrapper classes in this file so that they will be seen properly by the test suite.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from grouper.fe.alerts import Alert

if TYPE_CHECKING:
    from dataclasses import InitVar
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from grouper.fe.forms import ServiceAccountCreateForm, ServiceAccountPermissionGrantForm
    from grouper.fe.util import GrouperHandler
    from typing import Dict, List, Optional
    from wtforms_tornado import Form


@dataclass(repr=False, eq=False)
class BaseTemplate:
    """Base class for all template wrapper objects.

    All child classes must define an InitVar named template with a default value matching the file
    name of the Jinja2 template for that template object.
    """

    def render(self, handler: GrouperHandler, alerts: Optional[List[Alert]] = None) -> str:
        # The machinations here are to work around dataclass limitations on inheritance and default
        # values.  A child class cannot define a default value for a parent class attribute and
        # then add new attributes with no default value, so the attribute has to exist only in the
        # children, which means getattr is needed since mypy knows BaseTemplate has no template
        # attribute.
        template = handler.template_engine.get_template(getattr(self, "template"))

        # Merge alerts from cookies and passed into the render call.  If there is a form, also
        # merge any errors from the form as well.
        all_alerts = handler.get_alerts()
        if hasattr(self, "form"):
            form: Form = getattr(self, "form")
            all_alerts.extend(self._get_form_alerts(form.errors))
        if alerts:
            all_alerts.extend(alerts)

        # Set some default variables used by all templates.
        namespace = {
            "alerts": all_alerts,
            "is_active": handler.is_active,
            "static_url": handler.static_url,
            "perf_trace_uuid": handler.perf_trace_uuid,
            "update_qs": handler.update_qs,
            "xsrf_form": handler.xsrf_form_html,
            "transfer_qs": handler.transfer_qs,
        }

        # It would be nice to be able to use asdict here, but alas, it tries to deep copies of
        # things that cannot be copied, like WTForms form objects.  Instead, iterate through the
        # fields and update the namespace with the shallow value.
        for field in fields(self):
            namespace[field.name] = getattr(self, field.name)

        # Render the template and return the results.
        return template.render(namespace)

    def _get_form_alerts(self, errors: Dict[str, List[str]]) -> List[Alert]:
        """Create alerts from all errors in a WTForms form."""
        alerts = []
        for field, field_errors in errors.items():
            for error in field_errors:
                alerts.append(Alert("danger", error, field))
        return alerts


@dataclass(repr=False, eq=False)
class PermissionTemplate(BaseTemplate):
    permission: Permission
    access: PermissionAccess
    audit_log_entries: List[AuditLogEntry]

    template: InitVar[str] = "permission.html"


@dataclass(repr=False, eq=False)
class PermissionGroupGrantsTemplate(BaseTemplate):
    permission: Permission
    grants: List[GroupPermissionGrant]
    offset: int
    limit: int
    total: int
    sort_key: str
    sort_dir: str

    template: InitVar[str] = "permission-group.html"


@dataclass(repr=False, eq=False)
class PermissionServiceAccountGrantsTemplate(BaseTemplate):
    permission: Permission
    grants: List[ServiceAccountPermissionGrant]
    offset: int
    limit: int
    total: int
    sort_key: str
    sort_dir: str

    template: InitVar[str] = "permission-service-account.html"


@dataclass(repr=False, eq=False)
class PermissionsTemplate(BaseTemplate):
    permissions: List[Permission]
    offset: int
    limit: int
    total: int
    can_create: bool
    audited_permissions: bool
    sort_key: str
    sort_dir: str

    template: InitVar[str] = "permissions.html"


@dataclass(repr=False, eq=False)
class ServiceAccountCreateTemplate(BaseTemplate):
    owner: str
    form: ServiceAccountCreateForm

    template: InitVar[str] = "service-account-create.html"


@dataclass(repr=False, eq=False)
class ServiceAccountPermissionGrantTemplate(BaseTemplate):
    service: str
    owner: str
    form: ServiceAccountPermissionGrantForm

    template: InitVar[str] = "service-account-permission-grant.html"
