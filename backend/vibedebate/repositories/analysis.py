from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from vibedebate.repositories.invalidation import invalidate_on_commit

from vibedebate.models.analysis import AnalysisIssue, MessageAnalysis
from vibedebate.models.debate import ChatMessage, DebateChat


@dataclass
class AnalysisRepository:
    session: AsyncSession

    async def create(self, message_id: UUID) -> MessageAnalysis:
        analysis = MessageAnalysis(message_id=message_id, analysis_status="pending")
        self.session.add(analysis)
        await self.session.flush()

        return analysis

    async def get_or_create(self, message_id: UUID) -> MessageAnalysis:
        analysis = await self.session.scalar(
            select(MessageAnalysis)
            .where(MessageAnalysis.message_id == message_id)
            .with_for_update()
        )

        if analysis is None:
            return await self.create(message_id)

        return analysis

    async def issues(self, analysis_id: UUID) -> list[AnalysisIssue]:
        return list(
            await self.session.scalars(
                select(AnalysisIssue)
                .where(AnalysisIssue.analysis_id == analysis_id)
                .order_by(AnalysisIssue.created_at, AnalysisIssue.id)
            )
        )

    async def claim(self, message_id: UUID) -> UUID | None:
        analysis_id = await self._claim_pending(message_id)
        if analysis_id is not None:
            return analysis_id

        created = await self.session.scalar(
            insert(MessageAnalysis)
            .values(message_id=message_id, analysis_status="pending")
            .on_conflict_do_nothing(index_elements=[MessageAnalysis.message_id])
            .returning(MessageAnalysis.id)
        )
        if created is not None:
            return await self._claim_pending(message_id)
        return None

    async def _claim_pending(self, message_id: UUID) -> UUID | None:
        analysis_id = await self.session.scalar(
            update(MessageAnalysis)
            .where(
                MessageAnalysis.message_id == message_id,
                MessageAnalysis.analysis_status == "pending",
            )
            .values(analysis_status="running", started_at=datetime.now(timezone.utc))
            .returning(MessageAnalysis.id)
        )
        if analysis_id is not None:
            invalidate_on_commit(self.session, f"analysis:{message_id}")
        return analysis_id

    async def fail(self, analysis_id: UUID) -> None:
        message_id = await self.session.scalar(
            update(MessageAnalysis)
            .where(
                MessageAnalysis.id == analysis_id,
                MessageAnalysis.analysis_status == "running",
            )
            .values(analysis_status="failed", completed_at=datetime.now(timezone.utc))
            .returning(MessageAnalysis.message_id)
        )
        if message_id:
            invalidate_on_commit(self.session, f"analysis:{message_id}")

    async def recover_stale(self) -> None:
        from datetime import timedelta

        ids = await self.session.scalars(
            update(MessageAnalysis)
            .where(
                MessageAnalysis.analysis_status == "running",
                MessageAnalysis.started_at
                < datetime.now(timezone.utc) - timedelta(minutes=10),
            )
            .values(analysis_status="failed", completed_at=datetime.now(timezone.utc))
            .returning(MessageAnalysis.message_id)
        )
        for message_id in ids:
            invalidate_on_commit(self.session, f"analysis:{message_id}")

    async def complete(
        self,
        analysis_id: UUID,
        message_id: UUID,
        *,
        values: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> DebateChat | None:
        chat = await self.session.scalar(
            select(DebateChat)
            .join(ChatMessage)
            .where(ChatMessage.id == message_id)
            .with_for_update(of=DebateChat)
        )

        analysis = await self.session.get(
            MessageAnalysis, analysis_id, with_for_update=True
        )

        if analysis is None or analysis.analysis_status != "running":
            return

        for field, value in values.items():
            setattr(analysis, field, value)

        analysis.analysis_status = "completed"
        analysis.completed_at = datetime.now(timezone.utc)

        await self.session.execute(
            delete(AnalysisIssue).where(AnalysisIssue.analysis_id == analysis_id)
        )
        self.session.add_all(
            AnalysisIssue(analysis_id=analysis_id, **issue) for issue in issues
        )

        await self.session.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .values(is_substantive=values["is_substantive"])
        )
        return chat
