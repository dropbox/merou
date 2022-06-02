from grouper.plugin.base import BasePlugin
from grouper.plugin.exceptions import PluginRejectedPublicKey

MIN_KEY_SIZES = {
    b"ssh-rsa": 4096,
    # All ed25519 keys are sufficiently large.
    b"ssh-ed25519": 0,
}


class SshKeyPolicyPlugin(BasePlugin):
    def will_add_public_key(self, key):
        min_key_size = MIN_KEY_SIZES.get(key.key_type)

        if min_key_size is not None:
            if key.bits < min_key_size:
                raise PluginRejectedPublicKey(
                    "Unsupported key size for {}, minimum key size is {} bits".format(
                        key.key_type, min_key_size
                    )
                )
        else:
            raise PluginRejectedPublicKey("Unsupported key type: {}".format(key.key_type))
