from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserRole
from app.schemas import LoginRequest, TokenResponse, UserCreate


def register_user(db: Session, payload: UserCreate) -> User:
    """Регистрирует нового клиента с проверкой уникальности e-mail и телефона."""
    existing_email = db.scalar(select(User).where(User.email == payload.email))
    if existing_email is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким e-mail уже зарегистрирован",
        )

    existing_phone = db.scalar(select(User).where(User.phone == payload.phone))
    if existing_phone is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким номером телефона уже зарегистрирован",
        )

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=UserRole.CLIENT,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, payload: LoginRequest) -> TokenResponse:
    """Проверяет учётные данные пользователя и выдаёт JWT access-токен."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный e-mail или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись пользователя заблокирована",
        )

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token)
