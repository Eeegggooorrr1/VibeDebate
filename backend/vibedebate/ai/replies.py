from uuid import UUID

from vibedebate.ai.contracts import AIMessage
from vibedebate.ai.prompts import ENV


def reply_context(message_id: UUID | None, content: str | None) -> list[AIMessage]:
    if message_id is None or content is None:
        return []

    return [
        AIMessage(
            role="system",
            content=ENV.get_template("components/reply_context.jinja").render(
                reference={
                    "message_id": str(message_id),
                    "role": "assistant",
                    "content": content,
                }
            ),
        )
    ]
