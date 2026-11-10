from dataclasses import dataclass, field
from typing import Any
from uuid import UUID
from vibedebate.schemas.responses.debate import MessageResponse
from vibedebate.ai.contracts import AIMessage


@dataclass
class PreparedTurn:
    user: MessageResponse
    response: MessageResponse
    replay: bool
    messages: list[AIMessage] = field(default_factory=list)
    first_attack: bool = False
    context: dict[str, Any] = field(default_factory=dict)
    user_id: UUID | None = None
    debate_id: UUID | None = None
