"""Pydantic-схемы запросов и ответов API."""

from app.schemas.common import HealthResponse
from app.schemas.part import (
    PartCreate,
    PartRead,
    PartUpdate,
    RequestPartCreate,
    RequestPartRead,
    RequestPartUpdate,
    StockMovementCreate,
    StockMovementRead,
)
from app.schemas.request import (
    MasterCommentCreate,
    MasterCommentRead,
    MasterCommentUpdate,
    RepairRequestCreate,
    RepairRequestDetailRead,
    RepairRequestRead,
    RepairRequestStatusUpdate,
    RepairRequestUpdate,
    RequestPhotoCreate,
    RequestPhotoRead,
    StatusHistoryRead,
)
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
from app.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)

__all__ = [
    "HealthResponse",
    "LoginRequest",
    "MasterCommentCreate",
    "MasterCommentRead",
    "MasterCommentUpdate",
    "PartCreate",
    "PartRead",
    "PartUpdate",
    "RepairRequestCreate",
    "RepairRequestDetailRead",
    "RepairRequestRead",
    "RepairRequestStatusUpdate",
    "RepairRequestUpdate",
    "RequestPartCreate",
    "RequestPartRead",
    "RequestPartUpdate",
    "RequestPhotoCreate",
    "RequestPhotoRead",
    "ServiceCreate",
    "ServiceRead",
    "ServiceUpdate",
    "StatusHistoryRead",
    "StockMovementCreate",
    "StockMovementRead",
    "TokenResponse",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
