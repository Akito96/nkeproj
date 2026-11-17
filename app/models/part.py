from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, MovementType, enum_values

if TYPE_CHECKING:
    from app.models.request import RepairRequest
    from app.models.user import User


class Part(Base):
    """Номенклатурная позиция запчасти на складе сервисного центра."""

    __tablename__ = "parts"
    __table_args__ = (
        CheckConstraint("purchase_price >= 0", name="ck_parts_purchase_price_non_negative"),
        CheckConstraint("retail_price >= 0", name="ck_parts_retail_price_non_negative"),
        CheckConstraint("stock_qty >= 0", name="ck_parts_stock_qty_non_negative"),
        CheckConstraint("min_stock_qty >= 0", name="ck_parts_min_stock_qty_non_negative"),
        Index("ix_parts_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    retail_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    request_usages: Mapped[list["RequestPart"]] = relationship(back_populates="part")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="part")


class RequestPart(Base):
    """Использованные запчасти в конкретной заявке (связь M:N)."""

    __tablename__ = "request_parts"
    __table_args__ = (
        UniqueConstraint("request_id", "part_id", name="uq_request_parts_request_part"),
        CheckConstraint("quantity > 0", name="ck_request_parts_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_request_parts_unit_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    request: Mapped["RepairRequest"] = relationship(back_populates="used_parts")
    part: Mapped["Part"] = relationship(back_populates="request_usages")


class StockMovement(Base):
    """Запись журнала движения комплектующих на складе."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('in', 'out', 'return', 'write_off')",
            name="ck_stock_movements_type",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("requests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    performed_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(
            MovementType,
            name="movement_type",
            native_enum=False,
            create_constraint=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    part: Mapped["Part"] = relationship(back_populates="stock_movements")
    request: Mapped["RepairRequest | None"] = relationship(back_populates="stock_movements")
    performed_by: Mapped["User"] = relationship(back_populates="stock_movements")
