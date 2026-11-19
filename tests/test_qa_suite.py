from collections.abc import Generator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base, Part, RepairRequest, User, UserRole


@pytest.fixture
def qa_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[TestClient, Session], None, None]:
    """Создаёт изолированную файловую тестовую БД и отдельный каталог uploads."""
    db_file = tmp_path / "qa_isolated.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", str(upload_dir))

    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def _override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with session_factory() as db, TestClient(app) as test_client:
        yield test_client, db

    app.dependency_overrides.clear()
    engine.dispose()


def _create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: str,
    role: UserRole,
    password: str = "Password123!",
    is_active: bool = True,
) -> User:
    user = User(
        full_name=full_name,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login_headers(client: TestClient, email: str, password: str = "Password123!") -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_tc01_tc02_register_login_and_duplicate_checks(
    qa_env: tuple[TestClient, Session],
) -> None:
    """TC-01, TC-02: Регистрация (принудительно client), вход, /me и защита от дубликатов."""
    client, _ = qa_env

    reg_resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Иван Тестовый",
            "email": "ivan.qa@example.ru",
            "phone": "+7-999-111-22-33",
            "password": "Password123!",
            "role": "admin",
        },
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["role"] == "client"
    assert "password_hash" not in user_data

    headers = _login_headers(client, "ivan.qa@example.ru")
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "ivan.qa@example.ru"

    dup_email = client.post(
        "/api/auth/register",
        json={
            "full_name": "Другой Пользователь",
            "email": "ivan.qa@example.ru",
            "phone": "+7-999-111-22-44",
            "password": "Password123!",
        },
    )
    assert dup_email.status_code == 409
    assert "e-mail" in dup_email.json()["detail"].lower()

    dup_phone = client.post(
        "/api/auth/register",
        json={
            "full_name": "Другой Пользователь",
            "email": "other.qa@example.ru",
            "phone": "+7-999-111-22-33",
            "password": "Password123!",
        },
    )
    assert dup_phone.status_code == 409
    assert "телефон" in dup_phone.json()["detail"].lower()


def test_tc03_tc04_login_wrong_credentials_and_blocked_user(
    qa_env: tuple[TestClient, Session],
) -> None:
    """TC-03, TC-04: Ошибка 401 при неверном пароле и 403 для заблокированной учётной записи."""
    client, db = qa_env
    _create_user(
        db,
        full_name="Активный Клиент",
        email="active@qa.ru",
        phone="+7-999-200-00-01",
        role=UserRole.CLIENT,
    )
    _create_user(
        db,
        full_name="Заблокированный Клиент",
        email="blocked@qa.ru",
        phone="+7-999-200-00-02",
        role=UserRole.CLIENT,
        is_active=False,
    )

    bad_pw = client.post(
        "/api/auth/login",
        json={"email": "active@qa.ru", "password": "WrongPassword!"},
    )
    assert bad_pw.status_code == 401
    assert "Неверный e-mail или пароль" in bad_pw.json()["detail"]

    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "nobody@qa.ru", "password": "Password123!"},
    )
    assert unknown_email.status_code == 401

    blocked_resp = client.post(
        "/api/auth/login",
        json={"email": "blocked@qa.ru", "password": "Password123!"},
    )
    assert blocked_resp.status_code == 403
    assert "заблокирована" in blocked_resp.json()["detail"].lower()


def test_tc05_tc06_tc07_tc08_role_access_and_order_isolation(
    qa_env: tuple[TestClient, Session],
) -> None:
    """TC-05..TC-08: Изоляция заявок клиентов, ролевые ограничения и 401 без токена."""
    client, db = qa_env
    admin = _create_user(
        db,
        full_name="Админ QA",
        email="admin@qa.ru",
        phone="+7-999-300-00-01",
        role=UserRole.ADMIN,
    )
    master1 = _create_user(
        db,
        full_name="Мастер 1 QA",
        email="master1@qa.ru",
        phone="+7-999-300-00-02",
        role=UserRole.MASTER,
    )
    master2 = _create_user(
        db,
        full_name="Мастер 2 QA",
        email="master2@qa.ru",
        phone="+7-999-300-00-03",
        role=UserRole.MASTER,
    )
    client_a = _create_user(
        db,
        full_name="Клиент А",
        email="client_a@qa.ru",
        phone="+7-999-300-00-04",
        role=UserRole.CLIENT,
    )
    client_b = _create_user(
        db,
        full_name="Клиент Б",
        email="client_b@qa.ru",
        phone="+7-999-300-00-05",
        role=UserRole.CLIENT,
    )

    assert client.get("/api/orders/my").status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer broken.jwt.token"},
        ).status_code
        == 401
    )

    h_admin = _login_headers(client, admin.email)
    h_master1 = _login_headers(client, master1.email)
    h_master2 = _login_headers(client, master2.email)
    h_client_a = _login_headers(client, client_a.email)
    h_client_b = _login_headers(client, client_b.email)

    order_resp = client.post(
        "/api/orders",
        headers=h_client_a,
        data={
            "device_type": "Смартфон",
            "device_brand": "Apple",
            "device_model": "iPhone 14",
            "problem_description": "Не заряжается после падения в воду",
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    assert client.get(f"/api/orders/{order_id}", headers=h_client_a).status_code == 200
    forbidden_other_client = client.get(f"/api/orders/{order_id}", headers=h_client_b)
    assert forbidden_other_client.status_code == 403
    assert "чужой" in forbidden_other_client.json()["detail"].lower()

    my_b = client.get("/api/orders/my", headers=h_client_b)
    assert my_b.status_code == 200
    assert my_b.json() == []

    for endpoint in (
        "/api/master/orders",
        "/api/inventory/parts",
        "/api/admin/users",
        "/api/admin/stats",
    ):
        assert client.get(endpoint, headers=h_client_a).status_code == 403

    assign_resp = client.patch(
        f"/api/admin/orders/{order_id}/assign",
        headers=h_admin,
        json={"master_id": master1.id},
    )
    assert assign_resp.status_code == 200

    assert (
        client.patch(
            f"/api/master/orders/{order_id}/status",
            headers=h_master2,
            json={"status": "diagnostics"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/master/orders/{order_id}/comments",
            headers=h_master2,
            json={"comment_text": "Попытка чужого мастера", "is_internal": False},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/master/orders/{order_id}/status",
            headers=h_master1,
            json={"status": "diagnostics"},
        ).status_code
        == 200
    )


def test_tc09_tc10_boundary_empty_and_too_long_fields(
    qa_env: tuple[TestClient, Session],
) -> None:
    """TC-09, TC-10: Граничные значения для пустых полей и превышения максимальной длины."""
    client, db = qa_env
    user = _create_user(
        db,
        full_name="Клиент Границы",
        email="bounds@qa.ru",
        phone="+7-999-400-00-01",
        role=UserRole.CLIENT,
    )
    admin = _create_user(
        db,
        full_name="Админ Границы",
        email="admin_bounds@qa.ru",
        phone="+7-999-400-00-02",
        role=UserRole.ADMIN,
    )
    h_client = _login_headers(client, user.email)
    h_admin = _login_headers(client, admin.email)

    empty_reg = client.post(
        "/api/auth/register",
        json={"full_name": "   ", "email": "", "phone": "", "password": ""},
    )
    assert empty_reg.status_code == 422

    too_long_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Я" * 121,
            "email": "long@qa.ru",
            "phone": "+7-999-400-00-03",
            "password": "Password123!",
        },
    )
    assert too_long_reg.status_code == 422

    empty_order = client.post(
        "/api/orders",
        headers=h_client,
        data={"device_type": "   ", "problem_description": "   "},
    )
    assert empty_order.status_code == 422

    too_long_order = client.post(
        "/api/orders",
        headers=h_client,
        data={
            "device_type": "А" * 81,
            "device_brand": "Б" * 81,
            "device_model": "В" * 121,
            "problem_description": "Достаточно длинное описание неисправности",
        },
    )
    assert too_long_order.status_code == 422

    ok_order = client.post(
        "/api/orders",
        headers=h_client,
        data={
            "device_type": "ПК",
            "device_brand": "HP",
            "device_model": "ProDesk",
            "problem_description": "Не включается после скачка напряжения",
        },
    )
    assert ok_order.status_code == 201
    order_id = ok_order.json()["id"]

    too_long_note = client.patch(
        f"/api/master/orders/{order_id}/status",
        headers=h_admin,
        json={"status": "diagnostics", "note": "N" * 256},
    )
    assert too_long_note.status_code == 422


def test_tc11_tc12_tc13_boundary_photo_uploads(
    qa_env: tuple[TestClient, Session],
) -> None:
    """TC-11..TC-13: Граничные проверки фото — 0 байт, > 5 МБ, > 5 файлов и неверный формат."""
    client, db = qa_env
    user = _create_user(
        db,
        full_name="Клиент Фото",
        email="photo@qa.ru",
        phone="+7-999-500-00-01",
        role=UserRole.CLIENT,
    )
    h_client = _login_headers(client, user.email)
    base_data = {
        "device_type": "Ноутбук",
        "device_brand": "Lenovo",
        "device_model": "ThinkPad T14",
        "problem_description": "Разбита матрица, полосы по экрану",
    }

    zero_byte = client.post(
        "/api/orders",
        headers=h_client,
        data=base_data,
        files=[("photos", ("empty.jpg", b"", "image/jpeg"))],
    )
    assert zero_byte.status_code == 400
    assert "пуст" in zero_byte.json()["detail"].lower()

    over_limit = client.post(
        "/api/orders",
        headers=h_client,
        data=base_data,
        files=[("photos", ("huge.jpg", b"\xff\xd8" + b"0" * (5 * 1024 * 1024), "image/jpeg"))],
    )
    assert over_limit.status_code == 400
    assert "5 мб" in over_limit.json()["detail"].lower()

    bad_format = client.post(
        "/api/orders",
        headers=h_client,
        data=base_data,
        files=[("photos", ("script.txt", b"hello", "text/plain"))],
    )
    assert bad_format.status_code == 400
    assert "jpg, png или webp" in bad_format.json()["detail"].lower()

    six_files = [
        ("photos", (f"img_{idx}.png", b"\x89PNG\r\n\x1a\n1234", "image/png"))
        for idx in range(6)
    ]
    too_many = client.post(
        "/api/orders",
        headers=h_client,
        data=base_data,
        files=six_files,
    )
    assert too_many.status_code == 400
    assert "не более 5" in too_many.json()["detail"].lower()


def test_tc14_tc15_boundary_inventory_overdraft_and_rollback(
    qa_env: tuple[TestClient, Session],
) -> None:
    """TC-14, TC-15: Запрет списания больше остатка в заявке и в складском движении."""
    client, db = qa_env
    admin = _create_user(
        db,
        full_name="Админ Склад",
        email="admin_inv@qa.ru",
        phone="+7-999-600-00-01",
        role=UserRole.ADMIN,
    )
    master = _create_user(
        db,
        full_name="Мастер Склад",
        email="master_inv@qa.ru",
        phone="+7-999-600-00-02",
        role=UserRole.MASTER,
    )
    user = _create_user(
        db,
        full_name="Клиент Склад",
        email="client_inv@qa.ru",
        phone="+7-999-600-00-03",
        role=UserRole.CLIENT,
    )
    h_admin = _login_headers(client, admin.email)
    h_master = _login_headers(client, master.email)
    h_client = _login_headers(client, user.email)

    part_resp = client.post(
        "/api/inventory/parts",
        headers=h_admin,
        json={
            "sku": "QA-BAT-01",
            "name": "Аккумулятор тестовый",
            "category": "Аккумуляторы",
            "purchase_price": "1000.00",
            "retail_price": "2000.00",
            "stock_qty": 2,
            "min_stock_qty": 1,
        },
    )
    assert part_resp.status_code == 201
    part_id = part_resp.json()["id"]

    order_resp = client.post(
        "/api/orders",
        headers=h_client,
        data={
            "device_type": "Смартфон",
            "device_brand": "Samsung",
            "device_model": "Galaxy S23",
            "problem_description": "Быстро садится аккумулятор",
        },
    )
    order_id = order_resp.json()["id"]
    client.patch(
        f"/api/admin/orders/{order_id}/assign",
        headers=h_admin,
        json={"master_id": master.id},
    )

    overdraft_order = client.post(
        f"/api/master/orders/{order_id}/parts",
        headers=h_master,
        json={
            "labor_cost": "1800.00",
            "parts": [{"part_id": part_id, "quantity": 3}],
        },
    )
    assert overdraft_order.status_code == 400
    assert "Недостаточно запчасти" in overdraft_order.json()["detail"]

    db.expire_all()
    part_after = db.get(Part, part_id)
    order_after = db.get(RepairRequest, order_id)
    assert part_after is not None and part_after.stock_qty == 2
    assert order_after is not None and order_after.labor_cost == Decimal("0.00")

    overdraft_movement = client.post(
        "/api/inventory/movements",
        headers=h_admin,
        json={
            "part_id": part_id,
            "movement_type": "out",
            "quantity": 10,
            "reason": "Тест ухода в минус",
        },
    )
    assert overdraft_movement.status_code == 400
    db.expire_all()
    part_after_mov = db.get(Part, part_id)
    assert part_after_mov is not None and part_after_mov.stock_qty == 2


def test_tc16_boundary_status_transition_bypass(
    qa_env: tuple[TestClient, Session],
) -> None:
    """TC-16: Запрет перехода статуса в обход цепочки и отката назад."""
    client, db = qa_env
    admin = _create_user(
        db,
        full_name="Админ Статусы",
        email="admin_st@qa.ru",
        phone="+7-999-700-00-01",
        role=UserRole.ADMIN,
    )
    user = _create_user(
        db,
        full_name="Клиент Статусы",
        email="client_st@qa.ru",
        phone="+7-999-700-00-02",
        role=UserRole.CLIENT,
    )
    h_admin = _login_headers(client, admin.email)
    h_client = _login_headers(client, user.email)

    order_resp = client.post(
        "/api/orders",
        headers=h_client,
        data={
            "device_type": "Планшет",
            "device_brand": "Apple",
            "device_model": "iPad Air",
            "problem_description": "Треснуло стекло экрана",
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    skip_to_ready = client.patch(
        f"/api/master/orders/{order_id}/status",
        headers=h_admin,
        json={"status": "ready"},
    )
    assert skip_to_ready.status_code == 400
    assert "Недопустимый переход статуса" in skip_to_ready.json()["detail"]

    ok_step = client.patch(
        f"/api/master/orders/{order_id}/status",
        headers=h_admin,
        json={"status": "diagnostics", "note": "Принято на диагностику"},
    )
    assert ok_step.status_code == 200
    assert ok_step.json()["status"] == "diagnostics"

    rollback_step = client.patch(
        f"/api/master/orders/{order_id}/status",
        headers=h_admin,
        json={"status": "accepted"},
    )
    assert rollback_step.status_code == 400
    assert "Недопустимый переход статуса" in rollback_step.json()["detail"]

    detail = client.get(f"/api/orders/{order_id}", headers=h_admin).json()
    assert detail["status"] == "diagnostics"
    assert len(detail["status_history"]) == 2
