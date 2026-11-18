from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models import MasterComment, RepairRequest, RequestStatus, User
from app.schemas import (
    MasterCommentCreate,
    MasterCommentRead,
    OrderPartsAndLaborRequest,
    RepairRequestDetailRead,
    RepairRequestRead,
    RepairRequestStatusUpdate,
)
from app.services import order_service

router = APIRouter(prefix="/master", tags=["Мастер"])


@router.get(
    "/orders",
    response_model=list[RepairRequestRead],
    summary="Список заявок, назначенных текущему мастеру",
)
def get_master_orders(
    current_user: Annotated[User, Depends(require_role("master"))],
    db: Annotated[Session, Depends(get_db)],
    order_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
) -> list[RepairRequest]:
    """Возвращает заявки, закреплённые за авторизованным мастером."""
    return order_service.list_master_orders(
        db=db,
        master_user=current_user,
        status_filter=order_status,
    )


@router.patch(
    "/orders/{order_id}/status",
    response_model=RepairRequestDetailRead,
    summary="Изменение статуса заявки с проверкой переходов",
)
def update_order_status(
    order_id: int,
    payload: RepairRequestStatusUpdate,
    current_user: Annotated[User, Depends(require_role("master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> RepairRequest:
    """Переводит заявку в следующий допустимый этап и пишет запись в историю."""
    return order_service.update_master_order_status(
        db=db,
        order_id=order_id,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/orders/{order_id}/comments",
    response_model=MasterCommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавление комментария к заявке",
)
def create_order_comment(
    order_id: int,
    payload: MasterCommentCreate,
    current_user: Annotated[User, Depends(require_role("master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> MasterComment:
    """Добавляет публичный или внутренний комментарий к заявке."""
    return order_service.add_master_comment(
        db=db,
        order_id=order_id,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/orders/{order_id}/parts",
    response_model=RepairRequestDetailRead,
    summary="Фиксация использованных запчастей, диагностики и стоимости работ",
)
def add_order_parts_and_labor(
    order_id: int,
    payload: OrderPartsAndLaborRequest,
    current_user: Annotated[User, Depends(require_role("master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> RepairRequest:
    """Списывает запчасти со склада в транзакции и пересчитывает стоимость заказа."""
    return order_service.apply_parts_and_labor(
        db=db,
        order_id=order_id,
        payload=payload,
        current_user=current_user,
    )
