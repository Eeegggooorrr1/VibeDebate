from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressState:
    count: int = 0
    total: float = 0
    streak: int = 0
    mastered: bool = False
