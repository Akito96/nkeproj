import enum

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей SQLAlchemy 2.0."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserRole(str, enum.Enum):
    """Роли пользователей в информационной системе."""

    CLIENT = "client"
    MASTER = "master"
    ADMIN = "admin"


USER_ROLE_LABELS: dict[UserRole, str] = {
    UserRole.CLIENT: "клиент",
    UserRole.MASTER: "мастер",
    UserRole.ADMIN: "администратор",
}


class RequestStatus(str, enum.Enum):
    """Допустимые статусы жизненного цикла заявки на ремонт."""

    ACCEPTED = "accepted"
    DIAGNOSTICS = "diagnostics"
    IN_REPAIR = "in_repair"
    READY = "ready"
    ISSUED = "issued"


REQUEST_STATUS_LABELS: dict[RequestStatus, str] = {
    RequestStatus.ACCEPTED: "принята",
    RequestStatus.DIAGNOSTICS: "в диагностике",
    RequestStatus.IN_REPAIR: "в ремонте",
    RequestStatus.READY: "готова к выдаче",
    RequestStatus.ISSUED: "выдана",
}


class MovementType(str, enum.Enum):
    """Типы операций движения комплектующих на складе."""

    IN = "in"
    OUT = "out"
    RETURN = "return"
    WRITE_OFF = "write_off"


REQUEST_STATUS_SQL = "'accepted', 'diagnostics', 'in_repair', 'ready', 'issued'"


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Возвращает строковые значения элементов перечисления для SQLAlchemy Enum."""
    return [str(member.value) for member in enum_cls]
