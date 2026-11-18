import math

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Service
from app.schemas import ServiceListResponse, ServiceRead


def _list_services_sqlite(
    db: Session,
    search: str | None,
    category: str | None,
    page: int,
    size: int,
) -> ServiceListResponse:
    rows = list(
        db.scalars(
            select(Service)
            .where(Service.is_active.is_(True))
            .order_by(Service.id.asc())
        ).all()
    )

    if category is not None and category.strip():
        clean_category = category.strip().casefold()
        rows = [item for item in rows if item.category.strip().casefold() == clean_category]

    if search is not None and search.strip():
        query_text = search.strip().casefold()
        rows = [
            item
            for item in rows
            if query_text in item.title.casefold()
            or query_text in (item.description or "").casefold()
        ]

    total = len(rows)
    pages = math.ceil(total / size) if total > 0 else 0
    start = (page - 1) * size
    page_items = rows[start : start + size]

    return ServiceListResponse(
        items=[ServiceRead.model_validate(item) for item in page_items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


def list_services(
    db: Session,
    search: str | None = None,
    category: str | None = None,
    page: int = 1,
    size: int = 10,
) -> ServiceListResponse:
    """Возвращает активные услуги с поиском, фильтрацией по категории и пагинацией."""
    if db.get_bind().dialect.name == "sqlite":
        return _list_services_sqlite(db, search, category, page, size)

    stmt = select(Service).where(Service.is_active.is_(True))

    if category is not None and category.strip():
        clean_category = category.strip().lower()
        stmt = stmt.where(func.lower(Service.category) == clean_category)

    if search is not None and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Service.title.ilike(pattern),
                Service.description.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    pages = math.ceil(total / size) if total > 0 else 0

    rows = db.scalars(
        stmt.order_by(Service.id.asc()).offset((page - 1) * size).limit(size)
    ).all()

    return ServiceListResponse(
        items=[ServiceRead.model_validate(item) for item in rows],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
