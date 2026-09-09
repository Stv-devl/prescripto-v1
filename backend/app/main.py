"""FastAPI application entrypoint: logging, middlewares, lifespan, routes."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import DEV_SEED_EMAIL, email_delivery_warning, settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers

logging.basicConfig(level=logging.INFO)
logging.getLogger("app").setLevel(logging.DEBUG if settings.dev_mode else logging.INFO)


async def _seed_dev_data() -> None:
    """Create or find dev tenant + user. Store their IDs for dev_mode bypass.

    Does not set the admin role: reconcile_admin_roles is the single writer,
    and DEV_SEED_EMAIL is promoted whenever dev_mode is on. The email lookup
    carries no tenant_id, like the reconciliation query, because an address
    is unique across every tenant and this path only runs in local.
    """
    import uuid

    from sqlalchemy import select

    from app.api.deps import set_dev_ids
    from app.core.database import async_session
    from app.models.tenant import Tenant
    from app.models.user import User

    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == DEV_SEED_EMAIL))
        user = result.scalar_one_or_none()

        if user:
            set_dev_ids(user.id, user.tenant_id)
            return

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            session.add(Tenant(id=tenant_id, name="Dev", plan="free"))
            await session.flush()

        user_id = uuid.uuid4()
        session.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=DEV_SEED_EMAIL,
                hashed_password="dev-no-login",
            )
        )
        await session.commit()
        set_dev_ids(user_id, tenant_id)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logging.getLogger(__name__).info("Starting API in environment=%s", settings.environment)
    delivery_warning = email_delivery_warning(settings)
    if delivery_warning:
        logging.getLogger(__name__).warning(delivery_warning)
    logging.getLogger(__name__).info(
        "Rate-limit client key trusts proxies: %s",
        settings.forwarded_allow_ips or "(unset — socket address only)",
    )
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    if settings.dev_mode:
        await _seed_dev_data()
    from app.core.database import async_session
    from app.services.auth import reconcile_admin_roles

    async with async_session() as session:
        await reconcile_admin_roles(session)
    yield
    await engine.dispose()


app = FastAPI(
    title="Prescripto API",
    description="GED intelligente pour l'economiste de la construction",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
