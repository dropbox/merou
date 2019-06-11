import logging

import sshpubkeys

from grouper.models.public_key import PublicKey
from grouper.oneoff import BaseOneOff
from grouper.plugin import get_plugin_proxy
from grouper.plugin.exceptions import PluginRejectedPublicKey


class CheckPublicKeys(BaseOneOff):
    def run(self, session, dry_run=True):
        for key in session.query(PublicKey):
            pubkey = sshpubkeys.SSHKey(key.public_key, strict=True)

            logging.info("Processing Key (id={})".format(key.id))

            try:
                pubkey.parse()
            except sshpubkeys.InvalidKeyException as e:
                logging.error("Invalid Key (id={}): {}".format(key.id, str(e)))
                continue

            try:
                get_plugin_proxy().will_add_public_key(pubkey)
            except PluginRejectedPublicKey as e:
                logging.error("Bad Key (id={}): {}".format(key.id, str(e)))
                continue
