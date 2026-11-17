from decimal import Decimal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Ответ служебного эндпоинта проверки работоспособности."""

    status: str
    detail: str


def validate_text_length(
    value: str,
    field_name: str,
    min_len: int = 1,
    max_len: int | None = None,
) -> str:
    """Проверяет строковое поле после обрезки пробелов и возвращает ошибку на русском."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Поле «{field_name}» не может быть пустым")
    if len(cleaned) < min_len:
        raise ValueError(
            f"Поле «{field_name}» должно содержать минимум {min_len} символов"
        )
    if max_len is not None and len(cleaned) > max_len:
        raise ValueError(
            f"Поле «{field_name}» должно содержать не более {max_len} символов"
        )
    return cleaned


def validate_non_negative_decimal(value: Decimal, field_name: str) -> Decimal:
    """Проверяет, что денежная величина не отрицательна."""
    if value < Decimal(0):
        raise ValueError(f"Поле «{field_name}» не может быть отрицательным")
    return value


def validate_non_negative_int(value: int, field_name: str) -> int:
    """Проверяет, что целочисленное поле не отрицательно."""
    if value < 0:
        raise ValueError(f"Поле «{field_name}» не может быть отрицательным")
    return value


def validate_positive_int(value: int, field_name: str) -> int:
    """Проверяет, что целочисленное поле строго больше нуля."""
    if value <= 0:
        raise ValueError(f"Поле «{field_name}» должно быть больше нуля")
    return value
