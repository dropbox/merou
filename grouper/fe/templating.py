from __future__ import annotations

import os
from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256
from typing import cast, TYPE_CHECKING

from grouper.fe.settings import FrontendSettings
from grouper.templating import BaseTemplateEngine

if TYPE_CHECKING:
    from typing import Iterable, List, Optional


@dataclass(frozen=True)
class Resource:
    """A web resource that needs to be included in CSP headers."""

    url: str
    integrity: Optional[str]


# External CSS loaded on every Grouper page.  All URLs are relative to a CDNJS mirror.
EXTERNAL_CSS = [
    Resource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/css/bootstrap.min.css",
        integrity="sha256-6VA0SGkrc43SYPvX98q/LhHwm2APqX5us6Vuulsafps=",
    ),
    Resource(
        url="/ajax/libs/font-awesome/4.1.0/css/font-awesome.min.css",
        integrity="sha256-t2kyTgkh+fZJYRET5l9Sjrrl4UDain5jxdbqe8ejO8A=",
    ),
    Resource(
        url="/ajax/libs/bootstrap-datetimepicker/3.0.0/css/bootstrap-datetimepicker.min.css",
        integrity="sha256-Ov0GCM7wZ2/frH8veSLcBKbKthwLhC5WasvbBuJ2okc=",
    ),
    Resource(
        url="/ajax/libs/datatables/1.10.10/css/dataTables.bootstrap.min.css",
        integrity="sha256-z84A8SU1XXNN76l7Y+r65zvMYxgGD4v5wqg90I24Prw=",
    ),
    Resource(
        url="/ajax/libs/chosen/1.4.2/chosen.min.css",
        integrity="sha256-VGpryMO0mXR1A03airrHc3/J1YldD3xKadKpXXktWY8=",
    ),
]

# Paths to internal CSS files, relative to the Tornado static resource path.  These will be turned
# into Resource objects with SRI during initialization.
INTERNAL_CSS = ["css/grouper.css", "css/ext/chosen-bootstrap-1.0.4/chosen.bootstrap.min.css"]

# External fonts.  These are all loaded indirectly via CSS, not directly by Grouper, and the
# integrity attribute isn't used.  They're included here to assist with generating the CSP header.
# All URLs are relative to a CDNJS mirror.
EXTERNAL_FONTS = [
    Resource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.eot",
        integrity="",
    ),
    Resource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.svg",
        integrity="",
    ),
    Resource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.ttf",
        integrity="",
    ),
    Resource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/fonts/glyphicons-halflings-regular.woff",
        integrity="",
    ),
    Resource(url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.eot", integrity=""),
    Resource(url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.svg", integrity=""),
    Resource(url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.ttf", integrity=""),
    Resource(url="/ajax/libs/font-awesome/4.1.0/fonts/fontawesome-webfont.woff", integrity=""),
    Resource(url="/ajax/libs/font-awesome/4.1.0/fonts/FontAwesome.ttf", integrity=""),
]

# External images.  These are all loaded indirectly via CSS, not directly by Grouper, and the
# integrity attribute isn't used.  They're included here to assist with generating the CSP header.
# All URLs are relative to a CDNJS mirror.
EXTERNAL_IMG = [
    Resource(url="/ajax/libs/chosen/1.4.2/chosen-sprite.png", integrity=""),
    Resource(url="/ajax/libs/chosen/1.4.2/chosen-sprite@2x.png", integrity=""),
]

# External JavaScript loaded on every Grouper page.  All URLs are relative to a CDNJS mirror.
EXTERNAL_JS = [
    Resource(
        url="/ajax/libs/jquery/2.1.1/jquery.min.js",
        integrity="sha256-wNQJi8izTG+Ho9dyOYiugSFKU6C7Sh1NNqZ2QPmO0Hk=",
    ),
    Resource(
        url="/ajax/libs/lodash.js/2.4.1/lodash.min.js",
        integrity="sha256-gOpnA1vUitDpr6qV2ONTzFxXQKgnwvBCOklJH6hHqyE=",
    ),
    Resource(
        url="/ajax/libs/twitter-bootstrap/3.1.1/js/bootstrap.min.js",
        integrity="sha256-iY0FoX8s/FEg3c26R6iFw3jAtGbzDwcA5QJ1fiS0A6E=",
    ),
    Resource(
        url="/ajax/libs/moment.js/2.7.0/moment.min.js",
        integrity="sha256-FQODX4G5IRIuYRmkc+gFKbr7DXrrqFrPjZkLVJSDQZQ=",
    ),
    Resource(
        url="/ajax/libs/datatables/1.10.10/js/jquery.dataTables.min.js",
        integrity="sha256-YKbJo9/cZwgjue3I4jsFKdE+oGkrSpqZz6voxlmn2Fo=",
    ),
    Resource(
        url="/ajax/libs/bootstrap-datetimepicker/3.0.0/js/bootstrap-datetimepicker.min.js",
        integrity="sha256-8e6Htoin9PzZslStDJ7tnwZa9lIIaXCQy2sDOA2P6WI=",
    ),
    Resource(
        url="/ajax/libs/chosen/1.4.2/chosen.jquery.min.js",
        integrity="sha256-nOTrbQXdTPaimxT0mqnbsQGNDis1wmMPxII8apvxt3I=",
    ),
]

# Paths to internal JavaScript files, relative to the Tornado static resource path.  These will be
# turned into Resource objects with SRI during initialization.
INTERNAL_JS = ["js/grouper.js"]


class FrontendTemplateEngine(BaseTemplateEngine):
    """Frontend-specific template engine."""

    def __init__(
        self,
        settings: FrontendSettings,
        deployment_name: str,
        static_path: str,
        package: str = "grouper.fe",
    ) -> None:
        super().__init__(settings, package)
        self.static_path = static_path
        template_globals = {
            "cdnjs_prefix": settings.cdnjs_prefix,
            "deployment_name": deployment_name,
            "external_css": EXTERNAL_CSS,
            "external_js": EXTERNAL_JS,
            "internal_css": [self._static_path_to_resource(u) for u in INTERNAL_CSS],
            "internal_js": [self._static_path_to_resource(u) for u in INTERNAL_JS],
        }
        self.environment.globals.update(template_globals)

    def csp_header(self) -> str:
        """Return the value for the Content-Security-Policy header."""
        policy = "frame-ancestors 'none'; form-action 'self'; default-src 'none'"
        policy += "; img-src 'self' " + " ".join(self._cdnjs_urls(EXTERNAL_IMG))
        policy += "; script-src 'self' " + " ".join(self._cdnjs_urls(EXTERNAL_JS))
        policy += "; style-src 'self' " + " ".join(self._cdnjs_urls(EXTERNAL_CSS))
        policy += "; font-src " + " ".join(self._cdnjs_urls(EXTERNAL_FONTS))
        policy += "; require-sri-for script style"
        return policy

    def _cdnjs_urls(self, resources: Iterable[Resource]) -> List[str]:
        """Return the URLs on the preferred CDNJS mirror for the given resources."""
        cdnjs_prefix = cast(FrontendSettings, self.settings).cdnjs_prefix
        return [f"{cdnjs_prefix}{r.url}" for r in resources]

    def _static_path_to_resource(self, url: str) -> Resource:
        """Convert a path to a static resource into a Resource.

        Loads the contents of the file and computes the hash, and then returns a Resource with the
        integrity field filled out.  The URL of the resource will be relative to the static root,
        so will need to be passed to Tornado's static_url() function before substitution into HTML
        templates.
        """
        integrity_hash = sha256()
        with open(os.path.join(self.static_path, url), "rb") as f:
            integrity_hash.update(f.read())
        integrity = "sha256-" + b64encode(integrity_hash.digest()).decode()
        return Resource(url=url, integrity=integrity)
