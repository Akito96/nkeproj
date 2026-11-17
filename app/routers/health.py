from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import HealthResponse
from app.services import health_service

router = APIRouter(prefix="/health", tags=["Служебные"])


@router.get("", response_model=HealthResponse, summary="Проверка работы сервиса")
def health() -> HealthResponse:
    return health_service.get_app_health()


@router.get("/db", response_model=HealthResponse, summary="Проверка подключения к БД")
def health_db(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    return health_service.get_db_health(db)
