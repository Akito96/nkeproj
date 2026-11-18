from collections.abc import Generator
from datetime import timedelta
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, require_role
from app.main import app
from app.models import Base, User, UserRole
from app.routers import auth as auth_router


@pytest.fixture
def auth_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with session_factory() as db:
        yield db
    app.dependency_overrides.clear()


def test_register_success_and_forces_client_role(
    client: TestClient, auth_db: Session
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Анна Иванова",
            "email": "Anna@Example.com",
            "phone": "+7-900-555-01-01",
            "password": "secret123",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "anna@example.com"
    assert data["role"] == "client"
    assert "password" not in data
    assert "password_hash" not in data

    api_response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Пётр Смирнов",
            "email": "petr@example.com",
            "phone": "+7-900-555-01-02",
            "password": "secret123",
        },
    )
    assert api_response.status_code == 201
    assert api_response.json()["role"] == "client"

    saved_user = auth_db.get(User, data["id"])
    assert saved_user is not None
    assert saved_user.password_hash != "secret123"
    assert saved_user.password_hash.startswith("$2")


def test_register_duplicate_email_or_phone_and_validation(
    client: TestClient, auth_db: Session
) -> None:
    payload = {
        "full_name": "Олег Соколов",
        "email": "oleg@example.com",
        "phone": "+7-900-555-01-10",
        "password": "secret123",
    }
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    dup_email = client.post(
        "/auth/register",
        json={**payload, "phone": "+7-900-555-01-11"},
    )
    assert dup_email.status_code == 409
    assert "e-mail" in dup_email.json()["detail"]

    dup_phone = client.post(
        "/auth/register",
        json={**payload, "email": "other@example.com"},
    )
    assert dup_phone.status_code == 409
    assert "телефона" in dup_phone.json()["detail"]

    bad_input = client.post(
        "/auth/register",
        json={
            "full_name": "Олег Соколов",
            "email": "not-an-email",
            "phone": "+7-900-555-01-12",
            "password": "123",
        },
    )
    assert bad_input.status_code == 422
    messages = " | ".join(err["msg"] for err in bad_input.json()["detail"])
    assert "электронной почты" in messages
    assert "минимум 6 символов" in messages


def test_login_and_me_flow(client: TestClient, auth_db: Session) -> None:
    client.post(
        "/auth/register",
        json={
            "full_name": "Иван Орлов",
            "email": "ivan@example.com",
            "phone": "+7-900-555-02-01",
            "password": "mypassword",
        },
    )

    login_ok = client.post(
        "/auth/login",
        json={"email": "ivan@example.com", "password": "mypassword"},
    )
    assert login_ok.status_code == 200
    token = login_ok.json()["access_token"]
    assert login_ok.json()["token_type"] == "bearer"

    me_ok = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_ok.status_code == 200
    assert me_ok.json()["email"] == "ivan@example.com"
    assert me_ok.json()["role"] == "client"

    wrong_pass = client.post(
        "/auth/login",
        json={"email": "ivan@example.com", "password": "wrongpassword"},
    )
    assert wrong_pass.status_code == 401

    no_user = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "mypassword"},
    )
    assert no_user.status_code == 401

    no_token = client.get("/auth/me")
    assert no_token.status_code == 401

    bad_token = client.get("/auth/me", headers={"Authorization": "Bearer broken.jwt.token"})
    assert bad_token.status_code == 401

    user = auth_db.get(User, me_ok.json()["id"])
    assert user is not None
    expired_token = create_access_token(
        user_id=user.id,
        role=user.role,
        expires_delta=timedelta(minutes=-1),
    )
    expired_resp = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert expired_resp.status_code == 401

    user.is_active = False
    auth_db.commit()

    blocked_login = client.post(
        "/auth/login",
        json={"email": "ivan@example.com", "password": "mypassword"},
    )
    assert blocked_login.status_code == 403
    assert "заблокирована" in blocked_login.json()["detail"]

    blocked_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert blocked_me.status_code == 401


def test_require_role_protects_endpoints() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    with session_factory() as db:
        pw_hash = hash_password("Secret123!")
        client_user = User(
            full_name="Клиент Тест",
            email="c@test.ru",
            phone="+7-900-000-00-01",
            password_hash=pw_hash,
            role=UserRole.CLIENT,
        )
        master_user = User(
            full_name="Мастер Тест",
            email="m@test.ru",
            phone="+7-900-000-00-02",
            password_hash=pw_hash,
            role=UserRole.MASTER,
        )
        admin_user = User(
            full_name="Админ Тест",
            email="a@test.ru",
            phone="+7-900-000-00-03",
            password_hash=pw_hash,
            role=UserRole.ADMIN,
        )
        db.add_all([client_user, master_user, admin_user])
        db.commit()
        client_token = create_access_token(client_user.id, UserRole.CLIENT)
        master_token = create_access_token(master_user.id, UserRole.MASTER)
        admin_token = create_access_token(admin_user.id, UserRole.ADMIN)

    role_app = FastAPI()
    role_app.include_router(auth_router.router)

    def override_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    role_app.dependency_overrides[get_db] = override_db

    @role_app.get("/only-admin")
    def only_admin(
        user: Annotated[User, Depends(require_role("admin"))],
    ) -> dict[str, str]:
        return {"role": user.role.value}

    @role_app.get("/staff")
    def staff_only(
        user: Annotated[User, Depends(require_role("master", "admin"))],
    ) -> dict[str, str]:
        return {"role": user.role.value}

    @role_app.get("/only-client")
    def only_client(
        user: Annotated[User, Depends(require_role("client"))],
    ) -> dict[str, str]:
        return {"role": user.role.value}

    with TestClient(role_app) as test_client:
        assert test_client.get("/only-admin").status_code == 401
        assert (
            test_client.get(
                "/only-admin", headers={"Authorization": f"Bearer {client_token}"}
            ).status_code
            == 403
        )
        assert (
            test_client.get(
                "/only-admin", headers={"Authorization": f"Bearer {master_token}"}
            ).status_code
            == 403
        )
        assert (
            test_client.get(
                "/only-admin", headers={"Authorization": f"Bearer {admin_token}"}
            ).status_code
            == 200
        )

        assert (
            test_client.get(
                "/staff", headers={"Authorization": f"Bearer {client_token}"}
            ).status_code
            == 403
        )
        assert (
            test_client.get(
                "/staff", headers={"Authorization": f"Bearer {master_token}"}
            ).status_code
            == 200
        )
        assert (
            test_client.get(
                "/staff", headers={"Authorization": f"Bearer {admin_token}"}
            ).status_code
            == 200
        )

        assert (
            test_client.get(
                "/only-client", headers={"Authorization": f"Bearer {master_token}"}
            ).status_code
            == 403
        )
        assert (
            test_client.get(
                "/only-client", headers={"Authorization": f"Bearer {client_token}"}
            ).status_code
            == 200
        )
