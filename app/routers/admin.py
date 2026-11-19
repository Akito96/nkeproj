from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models import RepairRequest, RequestStatus, Service, User, UserRole
from app.schemas import (
    AdminStatsResponse,
    OrderAssignMasterRequest,
    RepairRequestDetailRead,
    RepairRequestRead,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services import (
    order_service,
    service_catalog_service,
    stats_service,
    user_service,
)

router = APIRouter(prefix="/admin", tags=["Администрирование"])


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Агрегированная статистика мастерской за период",
)
def get_admin_statistics(
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
    date_from: Annotated[
        date | None, Query(description="Начало периода (YYYY-MM-DD)")
    ] = None,
    date_to: Annotated[
        date | None, Query(description="Конец периода (YYYY-MM-DD)")
    ] = None,
) -> AdminStatsResponse:
    """Возвращает сводные показатели и данные для графиков администратора."""
    return stats_service.get_admin_stats(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/orders",
    response_model=list[RepairRequestRead],
    summary="Реестр всех заявок мастерской",
)
def list_all_orders(
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
    order_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
    master_id: int | None = Query(default=None),
    client_id: int | None = Query(default=None),
) -> list[RepairRequest]:
    """Возвращает все заявки с фильтрацией по статусу, мастеру и клиенту."""
    return order_service.list_all_orders(
        db=db,
        status_filter=order_status,
        master_id=master_id,
        client_id=client_id,
    )


@router.patch(
    "/orders/{order_id}/assign",
    response_model=RepairRequestDetailRead,
    summary="Назначение мастера на заявку",
)
def assign_master(
    order_id: int,
    payload: OrderAssignMasterRequest,
    admin_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> RepairRequest:
    """Назначает активного мастера ответственным за выполнение заявки."""
    return order_service.assign_master_to_order(
        db=db,
        order_id=order_id,
        master_id=payload.master_id,
        admin_user=admin_user,
    )


@router.get(
    "/services",
    response_model=list[ServiceRead],
    summary="Список всех услуг (включая неактивные)",
)
def list_services_admin(
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=True),
) -> list[Service]:
    """Возвращает полный список услуг для управления справочником."""
    return service_catalog_service.list_all_services(
        db=db, include_inactive=include_inactive
    )


@router.post(
    "/services",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создание услуги",
)
def create_service(
    payload: ServiceCreate,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> Service:
    """Добавляет новую услугу в прайс-лист."""
    return service_catalog_service.create_service(db, payload)


@router.patch(
    "/services/{service_id}",
    response_model=ServiceRead,
    summary="Обновление услуги",
)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> Service:
    """Редактирует данные услуги."""
    return service_catalog_service.update_service(db, service_id, payload)


@router.delete(
    "/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление услуги",
)
def delete_service(
    service_id: int,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Удаляет услугу из справочника."""
    service_catalog_service.delete_service(db, service_id)


@router.get(
    "/employees",
    response_model=list[UserRead],
    summary="Список сотрудников (мастера и администраторы)",
)
def list_employees(
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[UserRole | None, Query()] = None,
) -> list[User]:
    """Возвращает список сотрудников мастерской."""
    return user_service.list_users(db=db, role=role, employees_only=True)


@router.post(
    "/employees",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавление сотрудника",
)
def create_employee(
    payload: UserCreate,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Создаёт учётную запись сотрудника с ролью master или admin."""
    return user_service.create_user(db=db, payload=payload, employees_only=True)


@router.patch(
    "/employees/{user_id}",
    response_model=UserRead,
    summary="Обновление данных сотрудника",
)
def update_employee(
    user_id: int,
    payload: UserUpdate,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Редактирует профиль или роль сотрудника."""
    return user_service.update_user(
        db=db, user_id=user_id, payload=payload, employees_only=True
    )


@router.delete(
    "/employees/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление сотрудника",
)
def delete_employee(
    user_id: int,
    admin_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Удаляет учётную запись сотрудника."""
    user_service.delete_user(
        db=db, user_id=user_id, current_admin=admin_user, employees_only=True
    )


@router.get(
    "/users",
    response_model=list[UserRead],
    summary="Список всех пользователей",
)
def list_users(
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[UserRole | None, Query()] = None,
) -> list[User]:
    """Возвращает всех пользователей системы с опциональным фильтром по роли."""
    return user_service.list_users(db=db, role=role, employees_only=False)


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Профиль пользователя по ID",
)
def get_user(
    user_id: int,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Возвращает профиль пользователя."""
    return user_service.get_user(db=db, user_id=user_id)


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создание пользователя с любой ролью",
)
def create_user(
    payload: UserCreate,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Создаёт учётную запись пользователя (client, master или admin)."""
    return user_service.create_user(db=db, payload=payload, employees_only=False)


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Обновление пользователя",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    _admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Обновляет профиль, роль или активность пользователя."""
    return user_service.update_user(
        db=db, user_id=user_id, payload=payload, employees_only=False
    )


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление пользователя",
)
def delete_user(
    user_id: int,
    admin_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Удаляет учётную запись пользователя."""
    user_service.delete_user(
        db=db, user_id=user_id, current_admin=admin_user, employees_only=False
    )
