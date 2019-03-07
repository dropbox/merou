from datetime import datetime
from typing import NamedTuple

Permission = NamedTuple(
    "Permission", [("name", str), ("description", str), ("created_on", datetime)]
)
