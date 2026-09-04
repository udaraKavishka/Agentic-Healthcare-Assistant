from httpx import AsyncClient


async def test_health_reports_healthy(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
