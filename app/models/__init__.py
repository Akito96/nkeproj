"""ORM-модели. Импорт всех моделей здесь нужен, чтобы Alembic видел их в Base.metadata."""

from app.models.base import (
    REQUEST_STATUS_LABELS,
    USER_ROLE_LABELS,
    Base,
    MovementType,
    RequestStatus,
    UserRole,
)
from app.models.part import Part, RequestPart, StockMovement
from app.models.request import MasterComment, RepairRequest, RequestPhoto, StatusHistory
from app.models.service import Service
from app.models.user import User

__all__ = [
    "REQUEST_STATUS_LABELS",
    "USER_ROLE_LABELS",
    "Base",
    "MasterComment",
    "MovementType",
    "Part",
    "RepairRequest",
    "RequestPart",
    "RequestPhoto",
    "RequestStatus",
    "Service",
    "StatusHistory",
    "StockMovement",
    "User",
    "UserRole",
]
