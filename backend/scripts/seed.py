"""Seed script — creates a dev tenant and a dev user for local development."""

import asyncio
import uuid

from sqlalchemy import select

from app.core.auth import hash_password
from app.core.database import async_session, engine
from app.models.tenant import Tenant
from app.models.user import User

DEV_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEV_EMAIL = "dev@prescripto.fr"
DEV_PASSWORD = "dev123456"


async def seed() -> None:
    async with async_session() as session:
        # Check if tenant already exists
        result = await session.execute(select(Tenant).where(Tenant.id == DEV_TENANT_ID))
        if result.scalar_one_or_none():
            print(f"Seed already applied — tenant {DEV_TENANT_ID} exists.")
            return

        tenant = Tenant(id=DEV_TENANT_ID, name="Dev Cabinet", plan="free")
        session.add(tenant)

        user = User(
            id=DEV_USER_ID,
            tenant_id=DEV_TENANT_ID,
            email=DEV_EMAIL,
            hashed_password=hash_password(DEV_PASSWORD),
            role="owner",
            email_verified=True,
        )
        session.add(user)

        await session.commit()
        print(f"Seed OK — tenant '{tenant.name}' + user '{user.email}' created.")
        print(f"  tenant_id: {DEV_TENANT_ID}")
        print(f"  user_id:   {DEV_USER_ID}")
        print(f"  password:  {DEV_PASSWORD}")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
