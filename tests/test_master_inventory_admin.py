from collections.abc import Generator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, Part, RepairRequest, StockMovement, User, UserRole


@pytest.fixture
def full_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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


def _seed_actors(db: Session) -> dict[str, tuple[User, str]]:
    pw = hash_password("Secret123!")
    users = {
        "admin": User(
            full_name="Админ Тест",
            email="admin@test.ru",
            phone="+7-900-000-01-01",
            password_hash=pw,
            role=UserRole.ADMIN,
        ),
        "master1": User(
            full_name="Мастер Первый",
            email="master1@test.ru",
            phone="+7-900-000-01-02",
            password_hash=pw,
            role=UserRole.MASTER,
        ),
        "master2": User(
            full_name="Мастер Второй",
            email="master2@test.ru",
            phone="+7-900-000-01-03",
            password_hash=pw,
            role=UserRole.MASTER,
        ),
        "client": User(
            full_name="Клиент Тест",
            email="client@test.ru",
            phone="+7-900-000-01-04",
            password_hash=pw,
            role=UserRole.CLIENT,
        ),
    }
    db.add_all(users.values())
    db.commit()
    result: dict[str, tuple[User, str]] = {}
    for key, user in users.items():
        db.refresh(user)
        result[key] = (user, create_access_token(user.id, user.role))
    return result


def test_master_workflow_assign_status_transitions_and_comments(
    client: TestClient, full_db: Session
) -> None:
    actors = _seed_actors(full_db)
    admin_token = actors["admin"][1]
    master1_user, master1_token = actors["master1"]
    master2_token = actors["master2"][1]
    client_user, client_token = actors["client"]

    order_resp = client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        data={
            "device_type": "Ноутбук",
            "device_brand": "Lenovo",
            "device_model": "ThinkPad T480",
            "problem_description": "Не заряжается аккумулятор от сети",
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    bad_assign = client.patch(
        f"/api/admin/orders/{order_id}/assign",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"master_id": client_user.id},
    )
    assert bad_assign.status_code == 400
    assert "активным мастером" in bad_assign.json()["detail"]

    assign_resp = client.patch(
        f"/api/admin/orders/{order_id}/assign",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"master_id": master1_user.id},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["master_id"] == master1_user.id

    m1_orders = client.get(
        "/api/master/orders",
        headers={"Authorization": f"Bearer {master1_token}"},
    )
    assert m1_orders.status_code == 200
    assert [item["id"] for item in m1_orders.json()] == [order_id]

    m2_orders = client.get(
        "/api/master/orders",
        headers={"Authorization": f"Bearer {master2_token}"},
    )
    assert m2_orders.status_code == 200
    assert m2_orders.json() == []

    assert (
        client.patch(
            f"/api/master/orders/{order_id}/status",
            headers={"Authorization": f"Bearer {master2_token}"},
            json={"status": "diagnostics"},
        ).status_code
        == 403
    )

    bad_jump = client.patch(
        f"/api/master/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {master1_token}"},
        json={"status": "ready"},
    )
    assert bad_jump.status_code == 400
    assert "Недопустимый переход статуса" in bad_jump.json()["detail"]

    for next_status in ("diagnostics", "in_repair", "ready", "issued"):
        step_resp = client.patch(
            f"/api/master/orders/{order_id}/status",
            headers={"Authorization": f"Bearer {master1_token}"},
            json={"status": next_status, "note": f"Этап {next_status}"},
        )
        assert step_resp.status_code == 200
        assert step_resp.json()["status"] == next_status

    after_issued = client.patch(
        f"/api/master/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {master1_token}"},
        json={"status": "in_repair"},
    )
    assert after_issued.status_code == 400

    comment_resp = client.post(
        f"/api/master/orders/{order_id}/comments",
        headers={"Authorization": f"Bearer {master1_token}"},
        json={"comment_text": "Контроллер питания проверен", "is_internal": False},
    )
    assert comment_resp.status_code == 201
    assert comment_resp.json()["comment_text"] == "Контроллер питания проверен"

    order_detail = client.get(
        f"/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert order_detail.status_code == 200
    assert len(order_detail.json()["status_history"]) == 5
    assert order_detail.json()["completed_at"] is not None


def test_inventory_crud_transactional_write_off_and_low_stock(
    client: TestClient, full_db: Session
) -> None:
    actors = _seed_actors(full_db)
    admin_token = actors["admin"][1]
    master1_user, master1_token = actors["master1"]
    client_token = actors["client"][1]

    part1_resp = client.post(
        "/api/inventory/parts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "sku": "BAT-T480",
            "name": "Аккумулятор ThinkPad T480",
            "category": "Аккумуляторы",
            "purchase_price": "2000.00",
            "retail_price": "3500.00",
            "stock_qty": 3,
            "min_stock_qty": 2,
        },
    )
    assert part1_resp.status_code == 201
    part1 = part1_resp.json()
    assert part1["is_low_stock"] is False

    part2_resp = client.post(
        "/api/inventory/parts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "sku": "TEMP-SKU",
            "name": "Временная деталь",
            "category": "Разное",
            "purchase_price": "100.00",
            "retail_price": "200.00",
            "stock_qty": 0,
            "min_stock_qty": 1,
        },
    )
    assert part2_resp.status_code == 201
    part2_id = part2_resp.json()["id"]
    assert part2_resp.json()["is_low_stock"] is True

    assert (
        client.delete(
            f"/api/inventory/parts/{part2_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code
        == 204
    )

    assert (
        client.delete(
            f"/api/inventory/parts/{part1['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code
        == 409
    )

    order_resp = client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        data={
            "device_type": "Ноутбук",
            "problem_description": "Батарея держит меньше 10 минут",
        },
    )
    order_id = order_resp.json()["id"]
    client.patch(
        f"/api/admin/orders/{order_id}/assign",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"master_id": master1_user.id},
    )

    fail_writeoff = client.post(
        f"/api/master/orders/{order_id}/parts",
        headers={"Authorization": f"Bearer {master1_token}"},
        json={
            "labor_cost": "1500.00",
            "parts": [{"part_id": part1["id"], "quantity": 5}],
        },
    )
    assert fail_writeoff.status_code == 400
    assert "Недостаточно запчасти" in fail_writeoff.json()["detail"]

    full_db.expire_all()
    unchanged_part = full_db.get(Part, part1["id"])
    unchanged_order = full_db.get(RepairRequest, order_id)
    assert unchanged_part is not None and unchanged_part.stock_qty == 3
    assert unchanged_order is not None and unchanged_order.labor_cost == Decimal("0.00")

    ok_writeoff = client.post(
        f"/api/master/orders/{order_id}/parts",
        headers={"Authorization": f"Bearer {master1_token}"},
        json={
            "labor_cost": "1500.00",
            "diagnostic_result": "Требуется замена АКБ",
            "parts": [{"part_id": part1["id"], "quantity": 2}],
        },
    )
    assert ok_writeoff.status_code == 200
    order_data = ok_writeoff.json()
    assert order_data["labor_cost"] == "1500.00"
    assert order_data["parts_cost"] == "7000.00"
    assert order_data["total_cost"] == "8500.00"
    assert order_data["diagnostic_result"] == "Требуется замена АКБ"

    low_parts = client.get(
        "/api/inventory/parts",
        headers={"Authorization": f"Bearer {master1_token}"},
        params={"low_stock_only": "true"},
    )
    assert low_parts.status_code == 200
    assert len(low_parts.json()) == 1
    assert low_parts.json()[0]["stock_qty"] == 1
    assert low_parts.json()[0]["is_low_stock"] is True

    movements = full_db.scalars(
        select(StockMovement).where(StockMovement.part_id == part1["id"])
    ).all()
    assert len(movements) == 2

    bad_movement = client.post(
        "/api/inventory/movements",
        headers={"Authorization": f"Bearer {master1_token}"},
        json={
            "part_id": part1["id"],
            "movement_type": "write_off",
            "quantity": 10,
            "reason": "Тест перерасхода",
        },
    )
    assert bad_movement.status_code == 400


def test_admin_crud_services_employees_users_and_role_guards(
    client: TestClient, full_db: Session
) -> None:
    actors = _seed_actors(full_db)
    admin_user, admin_token = actors["admin"]
    master_token = actors["master1"][1]
    client_token = actors["client"][1]

    for url in (
        "/api/admin/orders",
        "/api/admin/services",
        "/api/admin/employees",
        "/api/admin/users",
    ):
        assert client.get(url, headers={"Authorization": f"Bearer {client_token}"}).status_code == 403
        assert client.get(url, headers={"Authorization": f"Bearer {master_token}"}).status_code == 403

    svc_create = client.post(
        "/api/admin/services",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Прошивка BIOS",
            "category": "Ноутбуки",
            "base_price": "2000.00",
            "warranty_days": 30,
        },
    )
    assert svc_create.status_code == 201
    svc_id = svc_create.json()["id"]

    svc_patch = client.patch(
        f"/api/admin/services/{svc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"base_price": "2500.00"},
    )
    assert svc_patch.status_code == 200
    assert svc_patch.json()["base_price"] == "2500.00"

    assert (
        client.delete(
            f"/api/admin/services/{svc_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code
        == 204
    )

    bad_emp = client.post(
        "/api/admin/employees",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": "Ошибочный Клиент",
            "email": "not-emp@test.ru",
            "phone": "+7-900-777-00-01",
            "password": "Password123!",
            "role": "client",
        },
    )
    assert bad_emp.status_code == 400

    emp_create = client.post(
        "/api/admin/employees",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": "Новый Мастер",
            "email": "newmaster@test.ru",
            "phone": "+7-900-777-00-02",
            "password": "Password123!",
            "role": "master",
        },
    )
    assert emp_create.status_code == 201
    emp_id = emp_create.json()["id"]

    emp_list = client.get(
        "/api/admin/employees",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert emp_list.status_code == 200
    assert all(u["role"] in ("master", "admin") for u in emp_list.json())

    user_patch = client.patch(
        f"/api/admin/users/{emp_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert user_patch.status_code == 200
    assert user_patch.json()["is_active"] is False

    self_delete = client.delete(
        f"/api/admin/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert self_delete.status_code == 400

    assert (
        client.delete(
            f"/api/admin/users/{emp_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code
        == 204
    )
