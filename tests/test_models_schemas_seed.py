from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    REQUEST_STATUS_LABELS,
    Base,
    Part,
    RepairRequest,
    RequestStatus,
    Service,
    User,
    UserRole,
)
from app.schemas import (
    PartCreate,
    PartRead,
    RepairRequestCreate,
    RepairRequestDetailRead,
    RepairRequestUpdate,
    RequestPartCreate,
    ServiceCreate,
    ServiceRead,
    UserCreate,
    UserRead,
)
from seed import seed_database


def _create_sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    return factory()


def test_seed_database_counts_and_idempotency() -> None:
    with _create_sqlite_session() as db:
        summary = seed_database(db)
        assert summary == {
            "admins": 1,
            "masters": 2,
            "clients": 3,
            "services": 10,
            "parts": 15,
            "requests": 20,
        }

        assert db.scalar(select(func.count(User.id)).where(User.role == UserRole.ADMIN)) == 1
        assert db.scalar(select(func.count(User.id)).where(User.role == UserRole.MASTER)) == 2
        assert db.scalar(select(func.count(User.id)).where(User.role == UserRole.CLIENT)) == 3
        assert db.scalar(select(func.count(Service.id))) == 10
        assert db.scalar(select(func.count(Part.id))) == 15
        assert db.scalar(select(func.count(RepairRequest.id))) == 20

        statuses_in_db = set(db.scalars(select(RepairRequest.status)).all())
        assert statuses_in_db == set(RequestStatus)

        second_run = seed_database(db)
        assert second_run == {
            "admins": 0,
            "masters": 0,
            "clients": 0,
            "services": 0,
            "parts": 0,
            "requests": 0,
        }

        reset_run = seed_database(db, reset=True)
        assert reset_run["requests"] == 20
        assert db.scalar(select(func.count(RepairRequest.id))) == 20


def test_read_schemas_serialize_seeded_models() -> None:
    with _create_sqlite_session() as db:
        seed_database(db)

        user = db.scalar(select(User).limit(1))
        service = db.scalar(select(Service).limit(1))
        part = db.scalar(select(Part).limit(1))
        request = db.scalar(
            select(RepairRequest).where(RepairRequest.status == RequestStatus.IN_REPAIR).limit(1)
        )

        assert user is not None
        assert service is not None
        assert part is not None
        assert request is not None

        user_read = UserRead.model_validate(user)
        service_read = ServiceRead.model_validate(service)
        part_read = PartRead.model_validate(part)
        request_detail = RepairRequestDetailRead.model_validate(request)

        assert user_read.email == user.email
        assert service_read.title == service.title
        assert part_read.sku == part.sku
        assert request_detail.status == RequestStatus.IN_REPAIR
        assert request_detail.status_label == REQUEST_STATUS_LABELS[RequestStatus.IN_REPAIR]
        assert len(request_detail.status_history) >= 1
        assert len(request_detail.used_parts) >= 1


def test_pydantic_validation_errors_in_russian() -> None:
    with pytest.raises(ValidationError) as user_exc:
        UserCreate(
            full_name="А",
            email="bad-email",
            phone="123",
            password="123",
        )
    user_errors = " | ".join(err["msg"] for err in user_exc.value.errors())
    assert "ФИО" in user_errors
    assert "электронной почты" in user_errors
    assert "телефона" in user_errors
    assert "Пароль" in user_errors

    with pytest.raises(ValidationError) as svc_exc:
        ServiceCreate(
            title=" ",
            category="Ноутбуки",
            base_price=Decimal("-100.00"),
            warranty_days=-5,
        )
    svc_errors = " | ".join(err["msg"] for err in svc_exc.value.errors())
    assert "не может быть пустым" in svc_errors
    assert "отрицательным" in svc_errors

    with pytest.raises(ValidationError) as part_exc:
        PartCreate(
            sku="A",
            name="Деталь",
            category="Разное",
            purchase_price=Decimal("-1.00"),
            retail_price=Decimal("10.00"),
            stock_qty=-2,
        )
    part_errors = " | ".join(err["msg"] for err in part_exc.value.errors())
    assert "минимум 2 символов" in part_errors
    assert "отрицательным" in part_errors

    with pytest.raises(ValidationError) as rp_exc:
        RequestPartCreate(part_id=0, quantity=0)
    assert "больше нуля" in rp_exc.value.errors()[0]["msg"]

    with pytest.raises(ValidationError) as req_exc:
        RepairRequestCreate(
            device_type="Смартфон",
            device_brand="Apple",
            device_model="iPhone 13",
            problem_description="Нет",
        )
    assert "минимум 5 символов" in req_exc.value.errors()[0]["msg"]

    with pytest.raises(ValidationError) as upd_exc:
        RepairRequestUpdate(total_cost=Decimal("-50.00"))
    assert "отрицательным" in upd_exc.value.errors()[0]["msg"]
