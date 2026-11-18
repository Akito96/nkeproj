from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.base import MovementType
from app.schemas.common import (
    validate_non_negative_decimal,
    validate_non_negative_int,
    validate_positive_int,
    validate_text_length,
)


class PartCreate(BaseModel):
    """Схема добавления запчасти на склад."""

    sku: str
    name: str
    category: str
    purchase_price: Decimal
    retail_price: Decimal
    stock_qty: int = 0
    min_stock_qty: int = 2

    @field_validator("sku")
    @classmethod
    def check_sku(cls, value: str) -> str:
        return validate_text_length(value, "Артикул (SKU)", min_len=2, max_len=64)

    @field_validator("name")
    @classmethod
    def check_name(cls, value: str) -> str:
        return validate_text_length(value, "Наименование запчасти", min_len=2, max_len=180)

    @field_validator("category")
    @classmethod
    def check_category(cls, value: str) -> str:
        return validate_text_length(value, "Категория", min_len=2, max_len=80)

    @field_validator("purchase_price")
    @classmethod
    def check_purchase_price(cls, value: Decimal) -> Decimal:
        return validate_non_negative_decimal(value, "Закупочная цена")

    @field_validator("retail_price")
    @classmethod
    def check_retail_price(cls, value: Decimal) -> Decimal:
        return validate_non_negative_decimal(value, "Отпускная цена")

    @field_validator("stock_qty")
    @classmethod
    def check_stock_qty(cls, value: int) -> int:
        return validate_non_negative_int(value, "Остаток на складе")

    @field_validator("min_stock_qty")
    @classmethod
    def check_min_stock_qty(cls, value: int) -> int:
        return validate_non_negative_int(value, "Минимальный остаток")


class PartUpdate(BaseModel):
    """Схема обновления номенклатуры запчасти."""

    sku: str | None = None
    name: str | None = None
    category: str | None = None
    purchase_price: Decimal | None = None
    retail_price: Decimal | None = None
    stock_qty: int | None = None
    min_stock_qty: int | None = None

    @field_validator("sku")
    @classmethod
    def check_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Артикул (SKU)", min_len=2, max_len=64)

    @field_validator("name")
    @classmethod
    def check_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Наименование запчасти", min_len=2, max_len=180)

    @field_validator("category")
    @classmethod
    def check_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Категория", min_len=2, max_len=80)

    @field_validator("purchase_price")
    @classmethod
    def check_purchase_price(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Закупочная цена")

    @field_validator("retail_price")
    @classmethod
    def check_retail_price(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Отпускная цена")

    @field_validator("stock_qty")
    @classmethod
    def check_stock_qty(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_non_negative_int(value, "Остаток на складе")

    @field_validator("min_stock_qty")
    @classmethod
    def check_min_stock_qty(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_non_negative_int(value, "Минимальный остаток")


class PartRead(BaseModel):
    """Схема чтения запчасти на складе."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category: str
    purchase_price: Decimal
    retail_price: Decimal
    stock_qty: int
    min_stock_qty: int
    is_low_stock: bool = False

    @model_validator(mode="after")
    def populate_low_stock(self) -> "PartRead":
        """Вычисляет флаг низкого остатка на складе."""
        self.is_low_stock = self.stock_qty <= self.min_stock_qty
        return self


class RequestPartCreate(BaseModel):
    """Схема добавления использованной запчасти в заявку."""

    part_id: int
    quantity: int = 1
    unit_price: Decimal | None = None

    @field_validator("part_id")
    @classmethod
    def check_part_id(cls, value: int) -> int:
        return validate_positive_int(value, "Идентификатор запчасти")

    @field_validator("quantity")
    @classmethod
    def check_quantity(cls, value: int) -> int:
        return validate_positive_int(value, "Количество")

    @field_validator("unit_price")
    @classmethod
    def check_unit_price(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Цена за единицу")


class RequestPartUpdate(BaseModel):
    """Схема обновления количества или цены запчасти в заявке."""

    quantity: int | None = None
    unit_price: Decimal | None = None

    @field_validator("quantity")
    @classmethod
    def check_quantity(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_positive_int(value, "Количество")

    @field_validator("unit_price")
    @classmethod
    def check_unit_price(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Цена за единицу")


class RequestPartRead(BaseModel):
    """Схема чтения запчасти, использованной в заявке."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    part_id: int
    quantity: int
    unit_price: Decimal
    added_at: datetime
    part: PartRead | None = None


class StockMovementCreate(BaseModel):
    """Схема регистрации складского движения."""

    part_id: int
    request_id: int | None = None
    movement_type: MovementType
    quantity: int
    reason: str | None = None

    @field_validator("part_id")
    @classmethod
    def check_part_id(cls, value: int) -> int:
        return validate_positive_int(value, "Идентификатор запчасти")

    @field_validator("quantity")
    @classmethod
    def check_quantity(cls, value: int) -> int:
        return validate_positive_int(value, "Количество")

    @field_validator("reason")
    @classmethod
    def check_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Основание операции", min_len=1, max_len=255)


class StockMovementRead(BaseModel):
    """Схема чтения записи движения склада."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    request_id: int | None
    performed_by_id: int
    movement_type: MovementType
    quantity: int
    reason: str | None
    created_at: datetime
