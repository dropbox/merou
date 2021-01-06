from __future__ import annotations

import os
from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING

from jinja2.meta import find_undeclared_variables

import grouper.fe
from grouper.fe.settings import FrontendSettings
from grouper.fe.templates import BaseTemplate
from grouper.fe.templating import FrontendTemplateEngine

if TYPE_CHECKING:
    from typing import Set

# These fields are automatically added to the template namespace for all render invocations in
# BaseTemplate or BaseTemplateEngine and thus don't need to be provided by the template dataclass.
DEFAULT_FIELDS = {
    "ROLES",
    "TYPES",
    "alerts",
    "is_active",
    "static_url",
    "update_qs",
    "xsrf_form",
    "transfer_qs",
}

# Unfortunately, the trick that we're using doesn't expand macros, and macros show up as undefined
# variables.  We therefore have to exclude them as well, and we can't look inside the macros to see
# the additional variables they need.  Thankfully, macros cannot access the template context unless
# that is explicitly requested, so they mostly do not add new variables.
MACROS = {"audit_log_panel", "dropdown", "form_field", "paginator", "permission_link"}


def get_template_variables(engine: FrontendTemplateEngine, name: str) -> Set[str]:
    """Return all variables used by the given template, primarily for tests."""
    source = engine.environment.loader.get_source(engine.environment, name)[0]
    ast = engine.environment.parse(source)
    return find_undeclared_variables(ast)


def test_template_consistency() -> None:
    """Check that template dataclasses define all variables needed by their templates.

    For each frontend template that has been wrapped in a dataclass, ask Jinja2 what variables need
    to be defined for that template and then check that the dataclass defines all of those
    variables and no others.  This unfortunately can't check types, but at least it ensures that
    the dataclass is complete.
    """
    static_path = os.path.join(os.path.dirname(grouper.fe.__file__), "static")
    engine = FrontendTemplateEngine(FrontendSettings(), "tests", static_path)

    for template_class in BaseTemplate.__subclasses__():
        assert is_dataclass(template_class)

        template_fields = fields(template_class)
        expected: Set[str] = set()
        for template_field in template_fields:
            if template_field.name == "template":
                template = template_field.default
            else:
                expected.add(template_field.name)
        assert template

        wanted = (get_template_variables(engine, template) - DEFAULT_FIELDS) - MACROS
        assert expected == wanted, f"fields for {template}"
