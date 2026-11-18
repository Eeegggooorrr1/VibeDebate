
from sqlalchemy import event
from sqlalchemy.orm import Session

from vibedebate.models.analysis import MessageAnalysis
from vibedebate.models.catalog import Topic, TopicCategory, OpponentPersona
from vibedebate.models.debate import Debate, DebateChat, ChatMessage


def invalidate_on_commit(session, *tags: str) -> None:
    session.info.setdefault("cache_invalidations", set()).update(tags)


@event.listens_for(Session, "before_flush")
def collect_invalidations(session, flush_context, instances):
    if "cache_repository" not in session.info:
        return

    for entity in session.new | session.dirty | session.deleted:
        if isinstance(entity, Debate):
            invalidate_on_commit(
                session, f"debates:{entity.user_id}", f"debate:{entity.id}"
            )
        elif isinstance(entity, DebateChat):
            invalidate_on_commit(
                session, f"debate:{entity.debate_id}", f"chat:{entity.id}"
            )
        elif isinstance(entity, ChatMessage):
            invalidate_on_commit(session, f"messages:{entity.chat_id}")
        elif isinstance(entity, MessageAnalysis):
            invalidate_on_commit(session, f"analysis:{entity.message_id}")
        elif isinstance(entity, (Topic, TopicCategory, OpponentPersona)):
            invalidate_on_commit(session, "catalog")


async def publish_invalidations(session) -> None:
    cache = session.info.get("cache_repository")
    tags = session.info.pop("cache_invalidations", set())
    if cache is not None and tags:
        await cache.invalidate(tags)
