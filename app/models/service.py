from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.request import RepairRequest


class Service(Base):
    """Справочник типовых ремонтных услуг сервисного центра."""

    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("base_price >= 0", name="ck_services_base_price_non_negative"),
        CheckConstraint("warranty_days >= 0", name="ck_services_warranty_days_non_negative"),
        Index("ix_services_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    warranty_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    requests: Mapped[list["RepairRequest"]] = relationship(back_populates="service")
