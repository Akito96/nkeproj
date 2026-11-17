from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.schemas.common import HealthResponse


def get_app_health() -> HealthResponse:
    """Проверка, что приложение запущено и отвечает."""
    return HealthResponse(status="ok", detail="Сервис работает")


def get_db_health(db: Session) -> HealthResponse:
    """Проверка доступности PostgreSQL простым запросом SELECT 1."""
    try:
        db.execute(select(1))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="База данных недоступна",
        ) from exc
    return HealthResponse(status="ok", detail="Подключение к базе данных установлено")
