from typing import TYPE_CHECKING

from grouper.templating import BaseTemplateEngine

if TYPE_CHECKING:
    from grouper.fe.settings import FrontendSettings


class FrontendTemplateEngine(BaseTemplateEngine):
    """Frontend-specific template engine."""

    def __init__(self, settings, deployment_name):
        # type: (FrontendSettings, str) -> None
        super(FrontendTemplateEngine, self).__init__(settings, "grouper.fe")
        template_globals = {
            "cdnjs_prefix": settings.cdnjs_prefix,
            "deployment_name": deployment_name,
        }
        self.environment.globals.update(template_globals)
