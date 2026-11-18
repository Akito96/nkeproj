from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.common import (
    validate_non_negative_decimal,
    validate_non_negative_int,
    validate_text_length,
)


class ServiceCreate(BaseModel):
    """Схема создания ремонтной услуги."""

    title: str
    category: str
    description: str | None = None
    base_price: Decimal
    warranty_days: int = 30
    is_active: bool = True

    @field_validator("title")
    @classmethod
    def check_title(cls, value: str) -> str:
        return validate_text_length(value, "Название услуги", min_len=2, max_len=150)

    @field_validator("category")
    @classmethod
    def check_category(cls, value: str) -> str:
        return validate_text_length(value, "Категория", min_len=2, max_len=80)

    @field_validator("base_price")
    @classmethod
    def check_base_price(cls, value: Decimal) -> Decimal:
        return validate_non_negative_decimal(value, "Базовая стоимость")

    @field_validator("warranty_days")
    @classmethod
    def check_warranty_days(cls, value: int) -> int:
        return validate_non_negative_int(value, "Гарантийный срок (дней)")


class ServiceUpdate(BaseModel):
    """Схема обновления ремонтной услуги."""

    title: str | None = None
    category: str | None = None
    description: str | None = None
    base_price: Decimal | None = None
    warranty_days: int | None = None
    is_active: bool | None = None

    @field_validator("title")
    @classmethod
    def check_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Название услуги", min_len=2, max_len=150)

    @field_validator("category")
    @classmethod
    def check_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Категория", min_len=2, max_len=80)

    @field_validator("base_price")
    @classmethod
    def check_base_price(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Базовая стоимость")

    @field_validator("warranty_days")
    @classmethod
    def check_warranty_days(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_non_negative_int(value, "Гарантийный срок (дней)")


class ServiceRead(BaseModel):
    """Схема чтения ремонтной услуги."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    description: str | None
    base_price: Decimal
    warranty_days: int
    is_active: bool


class ServiceListResponse(BaseModel):
    """Постраничный список ремонтных услуг."""

    items: list[ServiceRead]
    total: int
    page: int
    size: int
    pages: int
