import logging

import sshpubkeys

from grouper.models.public_key import PublicKey
from grouper.oneoff import BaseOneOff


class RefreshPublicKeys(BaseOneOff):
    def run(self, session, dry_run=True):
        for key in session.query(PublicKey):
            pubkey = sshpubkeys.SSHKey(key.public_key, strict=True)

            logging.info("Processing Key (id={})".format(key.id))

            try:
                pubkey.parse()
            except sshpubkeys.InvalidKeyException as e:
                logging.error("Invalid Key (id={}): {}".format(key.id, e.message))
                continue

            if not dry_run:
                key.fingerprint = pubkey.hash_md5().replace(b"MD5:", b"")
                key.fingerprint_sha256 = pubkey.hash_sha256().replace(b"SHA256:", b"")
                key.key_size = pubkey.bits
                key.key_type = pubkey.key_type
                key.comment = pubkey.comment

                session.commit()
