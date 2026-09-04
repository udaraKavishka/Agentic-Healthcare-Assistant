from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from assistant.api.app import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
