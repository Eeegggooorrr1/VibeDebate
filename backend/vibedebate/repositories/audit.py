from dataclasses import dataclass
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from vibedebate.models.user import AdminAuditLog
from vibedebate.models.enums import AdminAction


@dataclass
class AuditRepository:
    session: AsyncSession

    async def create_audit_entry(
        self,
        admin_user_id: UUID,
        target_user_id: UUID,
        action: AdminAction,
        reason: str,
    ) -> None:
        self.session.add(
            AdminAuditLog(
                admin_user_id=admin_user_id,
                target_type="user",
                target_id=target_user_id,
                action=action,
                reason=reason,
            )
        )
        await self.session.flush()
