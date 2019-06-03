from datetime import datetime
from typing import NamedTuple

PublicKey = NamedTuple(
    "PublicKey",
    [
        ("public_key", str),
        ("fingerprint", str),
        ("fingerprint_sha256", str),
        ("created_on", datetime),
    ],
)
