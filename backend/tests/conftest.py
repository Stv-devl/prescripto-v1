"""Shared test fixtures for the backend test suite."""

import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

# Settings are validated at import time (app/core/config.py), so the required
# variables must exist before anything from `app` is imported. setdefault keeps
# a developer's own values when they are already set.
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-characters-min")
# `mistral_api_key` has no default either (app/core/config.py). Without this line
# the suite silently depends on a developer's own .env: it runs here and dies at
# collection on a fresh checkout, and on CI. The tests never reach Mistral.
os.environ.setdefault("MISTRAL_API_KEY", "test-mistral-key-never-called")

import fitz  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: E402, F401  — registers every model on Base.metadata
from app.core.database import Base  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.services.ingestion.extraction import ExtractedPage  # noqa: E402


@pytest.fixture(autouse=True)
def _forget_rate_limits() -> Iterator[None]:
    """Empty the rate-limit counters around every case.

    They are process-wide state. A case that deliberately saturates a bucket
    would otherwise leak its count into whatever runs after it, in an order
    nothing guarantees — and the failure would land on a case that has nothing
    to do with rate limiting.
    """
    from app.core import ratelimit

    ratelimit.reset_all()
    yield
    ratelimit.reset_all()


@pytest.fixture(autouse=True)
def _fast_mistral_limiter() -> Iterator[None]:
    """Neutralizes the real 0.25 req/s Mistral limiter's sleep in tests.

    It is a process-wide singleton (app/core/mistral.py) shared across the
    whole session: without this, any test that exercises the real chat
    pipeline (several calls per case) serializes onto a strict 4s cadence and
    the suite takes minutes instead of seconds.
    """
    from app.core.mistral import mistral_large_limiter

    original_interval = mistral_large_limiter._min_interval
    mistral_large_limiter._min_interval = 0.0
    mistral_large_limiter._next_slot = 0.0
    yield
    mistral_large_limiter._min_interval = original_interval


@pytest.fixture(autouse=True)
def _clean_langsmith_env() -> Iterator[None]:
    """Undoes configure_langsmith()'s env writes around every case.

    `Settings()` reads LANGSMITH_TRACING/LANGSMITH_API_KEY/LANGSMITH_PROJECT/
    LANGSMITH_ENDPOINT from the environment by field-name convention, same as
    every other field. `configure_langsmith()` (called once at `graph.py`
    import, and directly by its own tests) writes those exact names back from
    a `Settings` instance — left in place, a bare `Settings()` built later
    would silently pick up whatever an earlier import or case wrote, instead
    of the field's own default.
    """
    _vars = ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT")
    for var in _vars:
        os.environ.pop(var, None)
    yield
    for var in _vars:
        os.environ.pop(var, None)


@pytest.fixture
def tenant_id() -> uuid.UUID:
    """A fixed tenant ID for tests."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Database fixtures ────────────────────────────────────────────
#
# In-memory SQLite. Enough for logic and isolation tests, because the isolation
# barrier is a WHERE clause in Python, not a database feature. NOT enough for
# anything Postgres-specific (JSONB operators, ILIKE, partial indexes, ON
# CONFLICT): those need a real Postgres.


def _enable_sqlite_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
    """Turn SQLite's FK enforcement on for every raw DBAPI connection.

    SQLite ships this OFF by default, so every `ondelete=` in the schema
    (CASCADE, SET NULL) is otherwise silently inert for the whole suite: a
    delete that would violate a foreign key just succeeds, and the child rows
    are left dangling instead of being cascaded or nulled.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """A clean, isolated async session with the full schema created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    event.listens_for(engine.sync_engine, "connect")(_enable_sqlite_foreign_keys)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def tenant_a(db: AsyncSession) -> Tenant:
    """The tenant the test acts as."""
    t = Tenant(id=uuid.uuid4(), name="Tenant A", plan="pro")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest_asyncio.fixture
async def tenant_b(db: AsyncSession) -> Tenant:
    """A second tenant — its data must never be reachable from tenant A."""
    t = Tenant(id=uuid.uuid4(), name="Tenant B", plan="free")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
def tmp_pdf_empty(tmp_path: Path) -> Path:
    """Create a 2-page PDF with no selectable text (simulates a plan)."""
    pdf_path = tmp_path / "plan.pdf"
    doc = fitz.open()
    for _ in range(2):
        doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def tmp_pdf_with_text(tmp_path: Path) -> Path:
    """Create a 3-page PDF with text content."""
    pdf_path = tmp_path / "textual.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} content with enough text " * 20)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def tmp_pdf_many_pages(tmp_path: Path) -> Path:
    """Create a PDF with 51 pages (exceeds max_vision_pages)."""
    pdf_path = tmp_path / "large.pdf"
    doc = fitz.open()
    for _ in range(51):
        doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_extracted_pages() -> list[ExtractedPage]:
    """Sample text-extracted pages for hybrid mode testing."""
    return [
        ExtractedPage(text="Short", page=1, source="page 1"),  # < 50 chars
        ExtractedPage(text="A" * 120, page=2, source="page 2"),  # 50-200 chars → vision
        ExtractedPage(text="B" * 300, page=3, source="page 3"),  # > 200 chars → keep text
    ]


@pytest.fixture
def mock_pixtral_response() -> MagicMock:
    """A mock Mistral chat.complete_async response with text content."""

    @dataclass
    class _Message:
        content: str = "## Description\nMocked vision description for testing."

    @dataclass
    class _Choice:
        message: _Message

    response = MagicMock()
    response.choices = [_Choice(message=_Message())]
    return response


@pytest.fixture
def mock_pixtral_classification_response() -> MagicMock:
    """A mock Pixtral classification response."""

    @dataclass
    class _Message:
        content: str = (
            '{"type": "plan", "lot": "01 - Gros oeuvre", "phase": "PRO", "confidence": 0.9}'
        )

    @dataclass
    class _Choice:
        message: _Message

    response = MagicMock()
    response.choices = [_Choice(message=_Message())]
    return response
