from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UserRole, enum_values

if TYPE_CHECKING:
    from app.models.part import StockMovement
    from app.models.request import (
        MasterComment,
        RepairRequest,
        RequestPhoto,
        StatusHistory,
    )


class User(Base):
    """Пользователь системы (клиент, мастер или администратор)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('client', 'master', 'admin')", name="ck_users_role"),
        CheckConstraint("length(trim(full_name)) >= 2", name="ck_users_full_name_len"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=UserRole.CLIENT,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    client_requests: Mapped[list["RepairRequest"]] = relationship(
        back_populates="client", foreign_keys="RepairRequest.client_id"
    )
    master_requests: Mapped[list["RepairRequest"]] = relationship(
        back_populates="master", foreign_keys="RepairRequest.master_id"
    )
    status_changes: Mapped[list["StatusHistory"]] = relationship(back_populates="changed_by")
    comments: Mapped[list["MasterComment"]] = relationship(back_populates="author")
    uploaded_photos: Mapped[list["RequestPhoto"]] = relationship(back_populates="uploaded_by")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="performed_by")
