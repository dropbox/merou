from typing import cast, NamedTuple, TYPE_CHECKING

from grouper.fe.settings import FrontendSettings
from grouper.templating import BaseTemplateEngine

if TYPE_CHECKING:
    from typing import Iterable, List

# An external web resource with SRI.
ExternalResource = NamedTuple("ExternalResource", [("url", str), ("integrity", str)])

# External CSS loaded on every Grouper page.  All URLs are relative to a CDNJS mirror.
EXTERNAL_CSS = [
    ExternalResource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/css/bootstrap.min.css",
        integrity="sha256-6VA0SGkrc43SYPvX98q/LhHwm2APqX5us6Vuulsafps=",
    ),
    ExternalResource(
        url="/ajax/libs/font-awesome/4.1.0/css/font-awesome.min.css",
        integrity="sha256-t2kyTgkh+fZJYRET5l9Sjrrl4UDain5jxdbqe8ejO8A=",
    ),
    ExternalResource(
        url="/ajax/libs/bootstrap-datetimepicker/3.0.0/css/bootstrap-datetimepicker.min.css",
        integrity="sha256-Ov0GCM7wZ2/frH8veSLcBKbKthwLhC5WasvbBuJ2okc=",
    ),
    ExternalResource(
        url="/ajax/libs/datatables/1.10.10/css/dataTables.bootstrap.min.css",
        integrity="sha256-z84A8SU1XXNN76l7Y+r65zvMYxgGD4v5wqg90I24Prw=",
    ),
    ExternalResource(
        url="/ajax/libs/chosen/1.4.2/chosen.min.css",
        integrity="sha256-VGpryMO0mXR1A03airrHc3/J1YldD3xKadKpXXktWY8=",
    ),
]

# External fonts.  These are all loaded indirectly via CSS, not directly by Grouper, and the
# integrity attribute isn't used.  They're included here to assist with generating the CSP header.
# All URLs are relative to a CDNJS mirror.
EXTERNAL_FONTS = [
    ExternalResource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.eot",
        integrity="",
    ),
    ExternalResource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.svg",
        integrity="",
    ),
    ExternalResource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.ttf",
        integrity="",
    ),
    ExternalResource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.woff",
        integrity="",
    ),
    ExternalResource(
        url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.eot", integrity=""
    ),
    ExternalResource(
        url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.svg", integrity=""
    ),
    ExternalResource(
        url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.ttf", integrity=""
    ),
    ExternalResource(
        url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.woff", integrity=""
    ),
    ExternalResource(url="/ajax/libs/font-awesome/4.1.0/fonts/FontAwesome.ttf", integrity=""),
]

# External images.  These are all loaded indirectly via CSS, not directly by Grouper, and the
# integrity attribute isn't used.  They're included here to assist with generating the CSP header.
# All URLs are relative to a CDNJS mirror.
EXTERNAL_IMG = [
    ExternalResource(url="/ajax/libs/chosen/1.4.2/chosen-sprite.png", integrity=""),
    ExternalResource(url="/ajax/libs/chosen/1.4.2/chosen-sprite@2x.png", integrity=""),
]

# External JavaScript loaded on every Grouper page.  All URLs are relative to a CDNJS mirror.
EXTERNAL_JS = [
    ExternalResource(
        url="/ajax/libs/jquery/2.1.1/jquery.min.js",
        integrity="sha256-wNQJi8izTG+Ho9dyOYiugSFKU6C7Sh1NNqZ2QPmO0Hk=",
    ),
    ExternalResource(
        url="/ajax/libs/lodash.js/2.4.1/lodash.min.js",
        integrity="sha256-gOpnA1vUitDpr6qV2ONTzFxXQKgnwvBCOklJH6hHqyE=",
    ),
    ExternalResource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/js/bootstrap.min.js",
        integrity="sha256-iY0FoX8s/FEg3c26R6iFw3jAtGbzDwcA5QJ1fiS0A6E=",
    ),
    ExternalResource(
        url="/ajax/libs/moment.js/2.7.0/moment.min.js",
        integrity="sha256-FQODX4G5IRIuYRmkc+gFKbr7DXrrqFrPjZkLVJSDQZQ=",
    ),
    ExternalResource(
        url="/ajax/libs/datatables/1.10.10/js/jquery.dataTables.min.js",
        integrity="sha256-YKbJo9/cZwgjue3I4jsFKdE+oGkrSpqZz6voxlmn2Fo=",
    ),
    ExternalResource(
        url="/ajax/libs/bootstrap-datetimepicker/3.0.0/js/bootstrap-datetimepicker.min.js",
        integrity="sha256-8e6Htoin9PzZslStDJ7tnwZa9lIIaXCQy2sDOA2P6WI=",
    ),
    ExternalResource(
        url="/ajax/libs/chosen/1.4.2/chosen.jquery.min.js",
        integrity="sha256-nOTrbQXdTPaimxT0mqnbsQGNDis1wmMPxII8apvxt3I=",
    ),
]


class FrontendTemplateEngine(BaseTemplateEngine):
    """Frontend-specific template engine."""

    def __init__(self, settings, deployment_name):
        # type: (FrontendSettings, str) -> None
        super(FrontendTemplateEngine, self).__init__(settings, "grouper.fe")
        template_globals = {
            "cdnjs_prefix": settings.cdnjs_prefix,
            "deployment_name": deployment_name,
            "external_css": EXTERNAL_CSS,
            "external_js": EXTERNAL_JS,
        }
        self.environment.globals.update(template_globals)

    def csp_header(self):
        # type: () -> str
        """Return the value for the Content-Security-Policy header."""
        policy = "frame-ancestors 'none'; form-action 'self'; default-src 'none'"
        policy += "; img-src 'self' " + " ".join(self._cdnjs_urls(EXTERNAL_IMG))
        policy += "; script-src 'self' " + " ".join(self._cdnjs_urls(EXTERNAL_JS))
        policy += "; style-src 'self' " + " ".join(self._cdnjs_urls(EXTERNAL_CSS))
        policy += "; font-src " + " ".join(self._cdnjs_urls(EXTERNAL_FONTS))
        return policy

    def _cdnjs_urls(self, resources):
        # type: (Iterable[ExternalResource]) -> List[str]
        """Return the URLs on the preferred CDNJS mirror for the given resources."""
        cdnjs_prefix = cast(FrontendSettings, self.settings).cdnjs_prefix
        return ["{}{}".format(cdnjs_prefix, r.url) for r in resources]
