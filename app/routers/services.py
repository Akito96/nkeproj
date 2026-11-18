from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import ServiceListResponse
from app.services import service_catalog_service

router = APIRouter(prefix="/services", tags=["Услуги"])


@router.get(
    "",
    response_model=ServiceListResponse,
    summary="Каталог ремонтных услуг",
)
def get_services(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, description="Поиск по названию и описанию"),
    category: str | None = Query(default=None, description="Фильтр по категории"),
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    size: int = Query(default=10, ge=1, le=100, description="Размер страницы"),
) -> ServiceListResponse:
    """Возвращает список активных услуг с поиском, фильтром и пагинацией."""
    return service_catalog_service.list_services(
        db=db,
        search=search,
        category=category,
        page=page,
        size=size,
    )
