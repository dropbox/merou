from grouper.plugin.base import BasePlugin
from grouper.plugin.exceptions import PluginRejectedPublicKey

MIN_KEY_SIZES = {"ssh-rsa": 2048}


class SshKeyPolicyPlugin(BasePlugin):
    def will_add_public_key(self, key):
        min_key_size = MIN_KEY_SIZES.get(key.key_type)

        if min_key_size:
            if key.bits < min_key_size:
                raise PluginRejectedPublicKey(
                    "Unsupported key size for {}, minimum key size is {} bits".format(
                        key.key_type, min_key_size
                    )
                )
        else:
            raise PluginRejectedPublicKey("Unsupported key type: {}".format(key.key_type))
