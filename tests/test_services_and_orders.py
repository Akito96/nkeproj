from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, RepairRequest, RequestStatus, Service, User, UserRole
from app.services import order_service


@pytest.fixture
def api_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Session, None, None]:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

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


def _create_user(
    db: Session,
    email: str,
    phone: str,
    role: UserRole = UserRole.CLIENT,
) -> tuple[User, str]:
    user = User(
        full_name=f"Тест {role.value}",
        email=email,
        phone=phone,
        password_hash=hash_password("Secret123!"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, create_access_token(user.id, user.role)


def test_get_services_search_category_pagination(
    client: TestClient, api_db: Session
) -> None:
    api_db.add_all(
        [
            Service(
                title="Замена экрана iPhone",
                category="Смартфоны",
                description="Установка нового OLED дисплея",
                base_price=Decimal("2500.00"),
                warranty_days=90,
            ),
            Service(
                title="Замена матрицы ноутбука",
                category="Ноутбуки",
                description="Подбор и замена IPS матрицы",
                base_price=Decimal("3000.00"),
                warranty_days=90,
            ),
            Service(
                title="Чистка ноутбука от пыли",
                category="Ноутбуки",
                description="Замена термопасты и чистка кулера",
                base_price=Decimal("2000.00"),
                warranty_days=30,
            ),
            Service(
                title="Архивная услуга",
                category="Ноутбуки",
                description="Скрыта из каталога",
                base_price=Decimal("500.00"),
                is_active=False,
            ),
        ]
    )
    api_db.commit()

    page1 = client.get("/api/services", params={"page": 1, "size": 2})
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 3
    assert body1["pages"] == 2
    assert body1["page"] == 1
    assert len(body1["items"]) == 2

    by_category = client.get("/services", params={"category": "ноутбуки"})
    assert by_category.status_code == 200
    assert by_category.json()["total"] == 2

    by_search = client.get("/services", params={"search": "Матриц"})
    assert by_search.status_code == 200
    assert by_search.json()["total"] == 1
    assert by_search.json()["items"][0]["title"] == "Замена матрицы ноутбука"


def test_create_order_with_photos_and_status_history(
    client: TestClient, api_db: Session, tmp_path: Path
) -> None:
    _, client_token = _create_user(api_db, "c1@test.ru", "+7-900-111-00-01")
    service = Service(
        title="Замена разъёма",
        category="Смартфоны",
        description="Ремонт USB-C",
        base_price=Decimal("1800.00"),
    )
    api_db.add(service)
    api_db.commit()
    api_db.refresh(service)

    response = client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        data={
            "device_type": "Смартфон",
            "device_brand": "Samsung",
            "device_model": "Galaxy S23",
            "problem_description": "Не заряжается при подключении кабеля",
            "service_id": str(service.id),
        },
        files=[
            ("photos", ("front.jpg", b"fake-jpg-bytes", "image/jpeg")),
            ("photos", ("port.png", b"fake-png-bytes", "image/png")),
        ],
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "accepted"
    assert data["status_label"] == "принята"
    assert data["labor_cost"] == "1800.00"
    assert len(data["status_history"]) == 1
    assert data["status_history"][0]["old_status"] is None
    assert data["status_history"][0]["new_status"] == "accepted"
    assert len(data["photos"]) == 2

    urls = [p["file_url"] for p in data["photos"]]
    assert urls[0] != urls[1]
    for url in urls:
        assert url.startswith("/uploads/")
        saved_file = tmp_path / Path(url).name
        assert saved_file.exists()


def test_create_order_photo_validation_and_auth(
    client: TestClient, api_db: Session
) -> None:
    _, client_token = _create_user(api_db, "c2@test.ru", "+7-900-111-00-02")
    _, master_token = _create_user(
        api_db, "m1@test.ru", "+7-900-111-00-03", role=UserRole.MASTER
    )

    base_data = {
        "device_type": "Ноутбук",
        "problem_description": "Перегревается и выключается через 10 минут",
    }

    assert client.post("/orders", data=base_data).status_code == 401
    assert (
        client.post(
            "/orders",
            headers={"Authorization": f"Bearer {master_token}"},
            data=base_data,
        ).status_code
        == 403
    )

    too_many = [
        ("photos", (f"img{i}.webp", b"webp-data", "image/webp")) for i in range(6)
    ]
    resp_many = client.post(
        "/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        data=base_data,
        files=too_many,
    )
    assert resp_many.status_code == 400
    assert "5 фотографий" in resp_many.json()["detail"]

    resp_bad_type = client.post(
        "/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        data=base_data,
        files=[("photos", ("doc.pdf", b"%PDF-1.4", "application/pdf"))],
    )
    assert resp_bad_type.status_code == 400
    assert "JPG, PNG или WEBP" in resp_bad_type.json()["detail"]

    oversized = b"x" * (5 * 1024 * 1024 + 1)
    resp_too_big = client.post(
        "/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        data=base_data,
        files=[("photos", ("huge.jpg", oversized, "image/jpeg"))],
    )
    assert resp_too_big.status_code == 400
    assert "5 МБ" in resp_too_big.json()["detail"]

    resp_bad_text = client.post(
        "/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        data={"device_type": "ПК", "problem_description": "Нет"},
    )
    assert resp_bad_text.status_code == 422
    assert "минимум 5 символов" in resp_bad_text.json()["detail"][0]["msg"]


def test_get_my_orders_and_order_detail_ownership_and_status_history(
    client: TestClient, api_db: Session
) -> None:
    _, c1_token = _create_user(api_db, "owner@test.ru", "+7-900-222-00-01")
    _, c2_token = _create_user(api_db, "other@test.ru", "+7-900-222-00-02")
    master_user, _ = _create_user(
        api_db, "master@test.ru", "+7-900-222-00-03", role=UserRole.MASTER
    )

    r1 = client.post(
        "/orders",
        headers={"Authorization": f"Bearer {c1_token}"},
        data={
            "device_type": "Ноутбук",
            "problem_description": "Не включается после скачка напряжения",
        },
    )
    assert r1.status_code == 201
    order1_id = r1.json()["id"]

    r2 = client.post(
        "/orders",
        headers={"Authorization": f"Bearer {c2_token}"},
        data={
            "device_type": "Планшет",
            "problem_description": "Треснул экран после падения",
        },
    )
    assert r2.status_code == 201

    my_resp = client.get("/orders/my", headers={"Authorization": f"Bearer {c1_token}"})
    assert my_resp.status_code == 200
    my_items = my_resp.json()
    assert len(my_items) == 1
    assert my_items[0]["id"] == order1_id

    order_obj = api_db.get(RepairRequest, order1_id)
    assert order_obj is not None
    order_service.change_order_status(
        api_db,
        order_obj,
        RequestStatus.DIAGNOSTICS,
        master_user,
        note="Начата аппаратная диагностика",
    )

    detail_ok = client.get(
        f"/orders/{order1_id}", headers={"Authorization": f"Bearer {c1_token}"}
    )
    assert detail_ok.status_code == 200
    detail = detail_ok.json()
    assert detail["status"] == "diagnostics"
    assert detail["status_label"] == "в диагностике"
    assert len(detail["status_history"]) == 2
    assert detail["status_history"][1]["old_status"] == "accepted"
    assert detail["status_history"][1]["new_status"] == "diagnostics"

    forbidden = client.get(
        f"/orders/{order1_id}", headers={"Authorization": f"Bearer {c2_token}"}
    )
    assert forbidden.status_code == 403

    not_found = client.get(
        "/orders/999999", headers={"Authorization": f"Bearer {c1_token}"}
    )
    assert not_found.status_code == 404
