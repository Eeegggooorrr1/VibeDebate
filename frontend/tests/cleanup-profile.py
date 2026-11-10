import asyncio
import sys
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from vibedebate.core.config import create_database_settings
from vibedebate.models.user import User, UserInterest


async def main():
    subject = str(UUID(sys.argv[1]))
    engine = create_async_engine(create_database_settings().url)
    try:
        async with engine.begin() as connection:
            user_ids = select(User.id).where(User.keycloak_sub == subject)
            await connection.execute(delete(UserInterest).where(UserInterest.user_id.in_(user_ids)))
            await connection.execute(delete(User).where(User.keycloak_sub == subject))
    finally:
        await engine.dispose()


asyncio.run(main())
