from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового клиента",
)
def register(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Создаёт учётную запись клиента."""
    return auth_service.register_user(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход в систему",
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Аутентифицирует пользователя и возвращает JWT access-токен."""
    return auth_service.authenticate_user(db, payload)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Профиль текущего пользователя",
)
def read_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Возвращает профиль авторизованного пользователя."""
    return current_user
