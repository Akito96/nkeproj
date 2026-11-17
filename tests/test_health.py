from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.database import get_db
from app.main import app


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "detail": "Сервис работает"}


def test_health_db_unavailable_returns_503(client: TestClient) -> None:
    broken_session = MagicMock()
    broken_session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("нет связи"))

    def override_get_db() -> Generator[MagicMock, None, None]:
        yield broken_session

    app.dependency_overrides[get_db] = override_get_db
    response = client.get("/api/health/db")
    assert response.status_code == 503
    assert response.json()["detail"] == "База данных недоступна"


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    origin = settings.cors_origins[0]
    response = client.options(
        "/api/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_uploads_served_as_static(client: TestClient) -> None:
    file_path = Path(settings.upload_dir) / "test_static.txt"
    file_path.write_text("ok", encoding="utf-8")
    try:
        response = client.get("/uploads/test_static.txt")
        assert response.status_code == 200
        assert response.text == "ok"
    finally:
        file_path.unlink()
