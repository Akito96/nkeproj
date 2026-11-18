from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models import Part, StockMovement, User
from app.schemas import (
    PartCreate,
    PartRead,
    PartUpdate,
    StockMovementCreate,
    StockMovementRead,
)
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["Склад запчастей"])


@router.get(
    "/parts",
    response_model=list[PartRead],
    summary="Список запчастей на складе",
)
def list_parts(
    _current_user: Annotated[User, Depends(require_role("master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
    category: str | None = Query(default=None, description="Фильтр по категории"),
    search: str | None = Query(default=None, description="Поиск по названию или SKU"),
    low_stock_only: bool = Query(
        default=False, description="Показать только позиции с низким остатком"
    ),
) -> list[Part]:
    """Возвращает номенклатуру запчастей с флагом низкого остатка."""
    return inventory_service.list_parts(
        db=db,
        category=category,
        search=search,
        low_stock_only=low_stock_only,
    )


@router.get(
    "/parts/{part_id}",
    response_model=PartRead,
    summary="Карточка запчасти",
)
def get_part(
    part_id: int,
    _current_user: Annotated[User, Depends(require_role("master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> Part:
    """Возвращает данные одной запчасти по ID."""
    return inventory_service.get_part(db, part_id)


@router.post(
    "/parts",
    response_model=PartRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавление запчасти на склад",
)
def create_part(
    payload: PartCreate,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> Part:
    """Создаёт новую номенклатурную позицию запчасти."""
    return inventory_service.create_part(db, payload, current_user)


@router.patch(
    "/parts/{part_id}",
    response_model=PartRead,
    summary="Редактирование запчасти",
)
def update_part(
    part_id: int,
    payload: PartUpdate,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> Part:
    """Обновляет параметры и остаток запчасти на складе."""
    return inventory_service.update_part(db, part_id, payload, current_user)


@router.delete(
    "/parts/{part_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление запчасти",
)
def delete_part(
    part_id: int,
    _current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Удаляет запчасть, если по ней не было движений."""
    inventory_service.delete_part(db, part_id)


@router.get(
    "/movements",
    response_model=list[StockMovementRead],
    summary="Журнал движений склада",
)
def list_movements(
    _current_user: Annotated[User, Depends(require_role("master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
    part_id: int | None = Query(default=None, description="Фильтр по ID запчасти"),
) -> list[StockMovement]:
    """Возвращает историю операций прихода, расхода, возврата и списания."""
    return inventory_service.list_stock_movements(db, part_id=part_id)


@router.post(
    "/movements",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Проведение складской операции",
)
def create_movement(
    payload: StockMovementCreate,
    current_user: Annotated[User, Depends(require_role("master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> StockMovement:
    """Регистрирует движение запчасти и атомарно обновляет остаток."""
    return inventory_service.create_stock_movement(db, payload, current_user)
