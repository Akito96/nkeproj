from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserRole
from app.schemas import UserCreate, UserUpdate


def _ensure_unique_contacts(
    db: Session,
    email: str | None = None,
    phone: str | None = None,
    exclude_user_id: int | None = None,
) -> None:
    if email is not None:
        stmt = select(User).where(User.email == email)
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        if db.scalar(stmt) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким e-mail уже зарегистрирован",
            )

    if phone is not None:
        stmt = select(User).where(User.phone == phone)
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        if db.scalar(stmt) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким номером телефона уже зарегистрирован",
            )


def list_users(
    db: Session,
    role: UserRole | None = None,
    employees_only: bool = False,
) -> list[User]:
    """Возвращает список пользователей или сотрудников с фильтром по роли."""
    stmt = select(User)
    if employees_only:
        stmt = stmt.where(User.role.in_([UserRole.MASTER, UserRole.ADMIN]))
    if role is not None:
        stmt = stmt.where(User.role == role)
    return list(db.scalars(stmt.order_by(User.id.asc())).all())


def get_user(db: Session, user_id: int) -> User:
    """Возвращает пользователя по ID или выбрасывает 404."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    return user


def create_user(
    db: Session,
    payload: UserCreate,
    employees_only: bool = False,
) -> User:
    """Создаёт пользователя или сотрудника (master/admin) с проверкой уникальности."""
    if employees_only and payload.role == UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сотрудник должен иметь роль master или admin",
        )

    _ensure_unique_contacts(db, email=payload.email, phone=payload.phone)

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user_id: int,
    payload: UserUpdate,
    employees_only: bool = False,
) -> User:
    """Обновляет профиль, роль или статус активности пользователя."""
    user = get_user(db, user_id)
    if employees_only and user.role == UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сотрудник не найден",
        )

    updates = payload.model_dump(exclude_unset=True)
    if employees_only and updates.get("role") == UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сотрудник должен иметь роль master или admin",
        )

    _ensure_unique_contacts(
        db,
        email=updates.get("email"),
        phone=updates.get("phone"),
        exclude_user_id=user.id,
    )

    password = updates.pop("password", None)
    if password is not None:
        user.password_hash = hash_password(password)

    for field, value in updates.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(
    db: Session,
    user_id: int,
    current_admin: User,
    employees_only: bool = False,
) -> None:
    """Удаляет пользователя при отсутствии связанных записей."""
    user = get_user(db, user_id)
    if employees_only and user.role == UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сотрудник не найден",
        )

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить собственную учётную запись",
        )

    try:
        db.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Невозможно удалить пользователя со связанными данными; деактивируйте учётную запись",
        ) from exc
