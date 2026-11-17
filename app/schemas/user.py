import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.base import UserRole
from app.schemas.common import validate_text_length

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[\d\s\-()]{7,20}$")


def _validate_email(value: str) -> str:
    cleaned = value.strip().lower()
    if not EMAIL_PATTERN.match(cleaned) or len(cleaned) > 255:
        raise ValueError("Укажите корректный адрес электронной почты")
    return cleaned


def _validate_phone(value: str) -> str:
    cleaned = value.strip()
    digits = re.sub(r"\D", "", cleaned)
    if not PHONE_PATTERN.match(cleaned) or len(digits) < 7 or len(cleaned) > 20:
        raise ValueError("Укажите корректный номер телефона (от 7 до 20 символов)")
    return cleaned


def _validate_password(value: str) -> str:
    if len(value) < 6:
        raise ValueError("Пароль должен содержать минимум 6 символов")
    if len(value) > 128:
        raise ValueError("Пароль должен содержать не более 128 символов")
    return value


class UserCreate(BaseModel):
    """Схема создания пользователя."""

    full_name: str
    email: str
    phone: str
    password: str
    role: UserRole = UserRole.CLIENT

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, value: str) -> str:
        return validate_text_length(value, "ФИО", min_len=2, max_len=120)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _validate_email(value)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return _validate_phone(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class UserUpdate(BaseModel):
    """Схема обновления данных пользователя."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_text_length(value, "ФИО", min_len=2, max_len=120)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_email(value)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_phone(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_password(value)


class UserRead(BaseModel):
    """Схема чтения профиля пользователя без хеша пароля."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    """Схема входа по e-mail и паролю."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _validate_email(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if not value:
            raise ValueError("Введите пароль")
        return value


class TokenResponse(BaseModel):
    """Ответ аутентификации с JWT-токеном."""

    access_token: str
    token_type: str = "bearer"
