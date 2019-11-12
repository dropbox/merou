from dataclasses import dataclass


@dataclass(frozen=True)
class Checkpoint:
    checkpoint: int
    time: int
