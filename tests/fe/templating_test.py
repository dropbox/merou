import itertools
import json
import os
from base64 import b64encode
from hashlib import sha256

import grouper.fe
from grouper.fe.settings import FrontendSettings
from grouper.fe.templating import FrontendTemplateEngine


def test_included_resources():
    # type: () -> None
    settings = FrontendSettings()
    static_path = os.path.join(os.path.dirname(grouper.fe.__file__), "static")
    engine = FrontendTemplateEngine(settings, "", static_path, package="tests.fe")
    template = engine.get_template("base.json.tmpl")
    content = json.loads(template.render())

    # Check that all external JavaScript and CSS have integrity attributes.
    for resource in itertools.chain(content["external_js"], content["external_css"]):
        assert resource["integrity"], "{} has integrity".format(resource["url"])

    # Check that all internal JavaScript and CSS both exist and have matching hashes.
    for resource in itertools.chain(content["internal_js"], content["internal_css"]):
        resource_hash = sha256()
        with open(os.path.join(static_path, resource["url"]), "rb") as f:
            resource_hash.update(f.read())
        assert resource["integrity"] == "sha256-" + b64encode(resource_hash.digest()).decode()
