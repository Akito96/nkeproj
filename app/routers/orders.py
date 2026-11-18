from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models import RepairRequest, RequestStatus, User
from app.schemas import RepairRequestCreate, RepairRequestDetailRead, RepairRequestRead
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Заявки"])


@router.post(
    "",
    response_model=RepairRequestDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создание новой заявки на ремонт",
)
def create_order(
    current_user: Annotated[User, Depends(require_role("client", "admin"))],
    db: Annotated[Session, Depends(get_db)],
    device_type: Annotated[str, Form(...)],
    problem_description: Annotated[str, Form(...)],
    device_brand: Annotated[str, Form()] = "Не указан",
    device_model: Annotated[str, Form()] = "Не указана",
    serial_number: Annotated[str | None, Form()] = None,
    appearance: Annotated[str | None, Form()] = None,
    service_id: Annotated[int | None, Form()] = None,
    photos: Annotated[list[UploadFile] | None, File()] = None,
) -> RepairRequest:
    """Создаёт заявку на ремонт и прикрепляет до 5 фотографий."""
    try:
        payload = RepairRequestCreate(
            service_id=service_id,
            device_type=device_type,
            device_brand=device_brand,
            device_model=device_model,
            serial_number=serial_number,
            appearance=appearance,
            problem_description=problem_description,
        )
    except ValidationError as exc:
        details = [
            {
                "loc": ["body", *err["loc"]],
                "msg": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=details,
        ) from exc

    return order_service.create_order(
        db=db,
        current_user=current_user,
        payload=payload,
        photos=photos,
    )


@router.get(
    "/my",
    response_model=list[RepairRequestRead],
    summary="История моих заявок",
)
def get_my_orders(
    current_user: Annotated[User, Depends(require_role("client", "admin"))],
    db: Annotated[Session, Depends(get_db)],
    order_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
) -> list[RepairRequest]:
    """Возвращает список заявок текущего пользователя."""
    return order_service.list_my_orders(
        db=db,
        current_user=current_user,
        status_filter=order_status,
    )


@router.get(
    "/{order_id}",
    response_model=RepairRequestDetailRead,
    summary="Детали заявки и история статусов",
)
def get_order_by_id(
    order_id: int,
    current_user: Annotated[User, Depends(require_role("client", "master", "admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> RepairRequest:
    """Возвращает карточку заявки с историей переходов статусов."""
    return order_service.get_order_detail(
        db=db,
        order_id=order_id,
        current_user=current_user,
    )
