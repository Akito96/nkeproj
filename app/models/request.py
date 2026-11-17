from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import REQUEST_STATUS_SQL, Base, RequestStatus, enum_values

if TYPE_CHECKING:
    from app.models.part import RequestPart, StockMovement
    from app.models.service import Service
    from app.models.user import User


class RepairRequest(Base):
    """Заявка на ремонт устройства (заказ-наряд)."""

    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(f"status IN ({REQUEST_STATUS_SQL})", name="ck_requests_status"),
        CheckConstraint("labor_cost >= 0", name="ck_requests_labor_cost_non_negative"),
        CheckConstraint("parts_cost >= 0", name="ck_requests_parts_cost_non_negative"),
        CheckConstraint("total_cost >= 0", name="ck_requests_total_cost_non_negative"),
        CheckConstraint(
            "length(trim(problem_description)) >= 5",
            name="ck_requests_problem_description_len",
        ),
        Index("ix_requests_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    master_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"), nullable=True
    )

    device_type: Mapped[str] = mapped_column(String(80), nullable=False)
    device_brand: Mapped[str] = mapped_column(String(80), nullable=False)
    device_model: Mapped[str] = mapped_column(String(120), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_description: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic_result: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[RequestStatus] = mapped_column(
        Enum(
            RequestStatus,
            name="request_status",
            native_enum=False,
            create_constraint=False,
            length=30,
            values_callable=enum_values,
        ),
        nullable=False,
        default=RequestStatus.ACCEPTED,
        index=True,
    )
    labor_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    parts_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped["User"] = relationship(back_populates="client_requests", foreign_keys=[client_id])
    master: Mapped["User | None"] = relationship(
        back_populates="master_requests", foreign_keys=[master_id]
    )
    service: Mapped["Service | None"] = relationship(back_populates="requests")
    status_history: Mapped[list["StatusHistory"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    comments: Mapped[list["MasterComment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    photos: Mapped[list["RequestPhoto"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    used_parts: Mapped[list["RequestPart"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="request")


class StatusHistory(Base):
    """Аудит-запись изменения статуса заявки."""

    __tablename__ = "status_history"
    __table_args__ = (
        CheckConstraint(
            f"new_status IN ({REQUEST_STATUS_SQL})", name="ck_status_history_new_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    changed_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    old_status: Mapped[RequestStatus | None] = mapped_column(
        Enum(
            RequestStatus,
            name="request_status",
            native_enum=False,
            create_constraint=False,
            length=30,
            values_callable=enum_values,
        ),
        nullable=True,
    )
    new_status: Mapped[RequestStatus] = mapped_column(
        Enum(
            RequestStatus,
            name="request_status",
            native_enum=False,
            create_constraint=False,
            length=30,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    request: Mapped["RepairRequest"] = relationship(back_populates="status_history")
    changed_by: Mapped["User"] = relationship(back_populates="status_changes")


class MasterComment(Base):
    """Комментарий мастера или администратора к заявке."""

    __tablename__ = "master_comments"
    __table_args__ = (
        CheckConstraint(
            "length(trim(comment_text)) >= 1", name="ck_master_comments_text_not_empty"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    request: Mapped["RepairRequest"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")


class RequestPhoto(Base):
    """Фотография устройства или процесса ремонта, прикреплённая к заявке."""

    __tablename__ = "request_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    request: Mapped["RepairRequest"] = relationship(back_populates="photos")
    uploaded_by: Mapped["User"] = relationship(back_populates="uploaded_photos")
