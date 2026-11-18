import math

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Service
from app.schemas import ServiceCreate, ServiceListResponse, ServiceRead, ServiceUpdate


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


def list_all_services(
    db: Session, include_inactive: bool = True
) -> list[Service]:
    """Возвращает полный список услуг для панели администратора."""
    stmt = select(Service)
    if not include_inactive:
        stmt = stmt.where(Service.is_active.is_(True))
    return list(db.scalars(stmt.order_by(Service.id.asc())).all())


def get_service(db: Session, service_id: int) -> Service:
    """Возвращает услугу по ID или выбрасывает 404."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Услуга не найдена",
        )
    return service


def create_service(db: Session, payload: ServiceCreate) -> Service:
    """Создаёт новую ремонтную услугу с проверкой уникальности названия."""
    existing = db.scalar(select(Service).where(Service.title == payload.title))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Услуга с таким названием уже существует",
        )

    service = Service(
        title=payload.title,
        category=payload.category,
        description=payload.description,
        base_price=payload.base_price,
        warranty_days=payload.warranty_days,
        is_active=payload.is_active,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def update_service(
    db: Session, service_id: int, payload: ServiceUpdate
) -> Service:
    """Обновляет параметры существующей услуги."""
    service = get_service(db, service_id)
    updates = payload.model_dump(exclude_unset=True)

    if "title" in updates and updates["title"] != service.title:
        duplicate = db.scalar(
            select(Service).where(
                Service.title == updates["title"],
                Service.id != service.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Услуга с таким названием уже существует",
            )

    for field, value in updates.items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return service


def delete_service(db: Session, service_id: int) -> None:
    """Удаляет услугу из каталога."""
    service = get_service(db, service_id)
    db.delete(service)
    db.commit()
