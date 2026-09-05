from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from assistant.api.app import app
from assistant.config import settings
from assistant.database.seed import seed


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def hospital_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The provided data.sql, seeded into a database the tests own."""
    target = seed(source=settings.SOURCE_SQL, target=tmp_path / "hospital.db")
    monkeypatch.setattr(settings, "HOSPITAL_DB", target)
    return target
