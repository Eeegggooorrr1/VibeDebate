from dataclasses import dataclass
from vibedebate.core.auth.roles import Role


@dataclass(frozen=True)
class CurrentUser:
    subject: str
    display_name: str | None
    roles: frozenset[Role]
    blocked: bool = False
