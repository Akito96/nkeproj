from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.base import REQUEST_STATUS_LABELS, RequestStatus
from app.schemas.common import (
    validate_non_negative_decimal,
    validate_positive_int,
    validate_text_length,
)
from app.schemas.part import RequestPartCreate, RequestPartRead


class StatusHistoryRead(BaseModel):
    """Схема чтения записи истории смены статуса заявки."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    changed_by_id: int
    old_status: RequestStatus | None
    new_status: RequestStatus
    note: str | None
    changed_at: datetime


class MasterCommentCreate(BaseModel):
    """Схема добавления комментария к заявке."""

    comment_text: str
    is_internal: bool = False

    @field_validator("comment_text")
    @classmethod
    def check_comment_text(cls, value: str) -> str:
        return validate_text_length(value, "Текст комментария", min_len=1)


class MasterCommentUpdate(BaseModel):
    """Схема редактирования комментария к заявке."""

    comment_text: str | None = None
    is_internal: bool | None = None

    @field_validator("comment_text")
    @classmethod
    def check_comment_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Текст комментария", min_len=1)


class MasterCommentRead(BaseModel):
    """Схема чтения комментария к заявке."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    author_id: int
    comment_text: str
    is_internal: bool
    created_at: datetime


class RequestPhotoCreate(BaseModel):
    """Схема прикрепления фотографии к заявке."""

    file_url: str
    caption: str | None = None

    @field_validator("file_url")
    @classmethod
    def check_file_url(cls, value: str) -> str:
        return validate_text_length(value, "Путь к файлу", min_len=1, max_len=500)

    @field_validator("caption")
    @classmethod
    def check_caption(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Подпись к фото", min_len=1, max_len=200)


class RequestPhotoRead(BaseModel):
    """Схема чтения фотографии заявки."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    uploaded_by_id: int
    file_url: str
    caption: str | None
    uploaded_at: datetime


class RepairRequestCreate(BaseModel):
    """Схема создания новой заявки на ремонт."""

    service_id: int | None = None
    device_type: str
    device_brand: str
    device_model: str
    serial_number: str | None = None
    appearance: str | None = None
    problem_description: str

    @field_validator("service_id")
    @classmethod
    def check_service_id(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_positive_int(value, "Идентификатор услуги")

    @field_validator("device_type")
    @classmethod
    def check_device_type(cls, value: str) -> str:
        return validate_text_length(value, "Тип устройства", min_len=2, max_len=80)

    @field_validator("device_brand")
    @classmethod
    def check_device_brand(cls, value: str) -> str:
        return validate_text_length(value, "Бренд", min_len=1, max_len=80)

    @field_validator("device_model")
    @classmethod
    def check_device_model(cls, value: str) -> str:
        return validate_text_length(value, "Модель", min_len=1, max_len=120)

    @field_validator("serial_number")
    @classmethod
    def check_serial_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Серийный номер / IMEI", min_len=1, max_len=100)

    @field_validator("problem_description")
    @classmethod
    def check_problem_description(cls, value: str) -> str:
        return validate_text_length(value, "Описание неисправности", min_len=5)


class RepairRequestUpdate(BaseModel):
    """Схема частичного обновления данных заявки."""

    master_id: int | None = None
    service_id: int | None = None
    device_type: str | None = None
    device_brand: str | None = None
    device_model: str | None = None
    serial_number: str | None = None
    appearance: str | None = None
    problem_description: str | None = None
    diagnostic_result: str | None = None
    labor_cost: Decimal | None = None
    parts_cost: Decimal | None = None
    total_cost: Decimal | None = None

    @field_validator("master_id")
    @classmethod
    def check_master_id(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_positive_int(value, "Идентификатор мастера")

    @field_validator("service_id")
    @classmethod
    def check_service_id(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_positive_int(value, "Идентификатор услуги")

    @field_validator("device_type")
    @classmethod
    def check_device_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Тип устройства", min_len=2, max_len=80)

    @field_validator("device_brand")
    @classmethod
    def check_device_brand(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Бренд", min_len=1, max_len=80)

    @field_validator("device_model")
    @classmethod
    def check_device_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Модель", min_len=1, max_len=120)

    @field_validator("serial_number")
    @classmethod
    def check_serial_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Серийный номер / IMEI", min_len=1, max_len=100)

    @field_validator("problem_description")
    @classmethod
    def check_problem_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Описание неисправности", min_len=5)

    @field_validator("labor_cost")
    @classmethod
    def check_labor_cost(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Стоимость работ")

    @field_validator("parts_cost")
    @classmethod
    def check_parts_cost(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Стоимость запчастей")

    @field_validator("total_cost")
    @classmethod
    def check_total_cost(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Итоговая стоимость")


class RepairRequestStatusUpdate(BaseModel):
    """Схема смены статуса заявки."""

    status: RequestStatus
    note: str | None = None

    @field_validator("note")
    @classmethod
    def check_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Комментарий к смене статуса", min_len=1, max_len=255)


class RepairRequestRead(BaseModel):
    """Краткая схема чтения заявки на ремонт."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    master_id: int | None
    service_id: int | None
    device_type: str
    device_brand: str
    device_model: str
    serial_number: str | None
    appearance: str | None
    problem_description: str
    diagnostic_result: str | None
    status: RequestStatus
    labor_cost: Decimal
    parts_cost: Decimal
    total_cost: Decimal
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    status_label: str = ""

    @model_validator(mode="after")
    def populate_status_label(self) -> "RepairRequestRead":
        """Заполняет русскоязычное название статуса заявки."""
        self.status_label = REQUEST_STATUS_LABELS[self.status]
        return self


class RepairRequestDetailRead(RepairRequestRead):
    """Детальная схема чтения заявки с историей, комментариями, фото и запчастями."""

    status_history: list[StatusHistoryRead] = []
    comments: list[MasterCommentRead] = []
    photos: list[RequestPhotoRead] = []
    used_parts: list[RequestPartRead] = []


class OrderAssignMasterRequest(BaseModel):
    """Схема назначения мастера на заявку."""

    master_id: int

    @field_validator("master_id")
    @classmethod
    def check_master_id(cls, value: int) -> int:
        return validate_positive_int(value, "Идентификатор мастера")


class OrderPartsAndLaborRequest(BaseModel):
    """Схема фиксации использованных запчастей, диагностики и стоимости работ."""

    labor_cost: Decimal | None = None
    diagnostic_result: str | None = None
    parts: list[RequestPartCreate] = []
    part_id: int | None = None
    quantity: int = 1
    unit_price: Decimal | None = None

    @field_validator("labor_cost")
    @classmethod
    def check_labor_cost(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return validate_non_negative_decimal(value, "Стоимость работ")

    @field_validator("diagnostic_result")
    @classmethod
    def check_diagnostic_result(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "Результат диагностики", min_len=1)

    @field_validator("part_id")
    @classmethod
    def check_part_id(cls, value: int | None) -> int | None:
        if value is None:
            return None
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

    @model_validator(mode="after")
    def check_not_empty(self) -> "OrderPartsAndLaborRequest":
        """Проверяет, что передано хотя бы одно поле для обновления."""
        if (
            self.labor_cost is None
            and self.diagnostic_result is None
            and not self.parts
            and self.part_id is None
        ):
            raise ValueError(
                "Укажите стоимость работ, результат диагностики или список запчастей"
            )
        return self
