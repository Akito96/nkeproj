import argparse
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import bcrypt
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    MasterComment,
    MovementType,
    Part,
    RepairRequest,
    RequestPart,
    RequestPhoto,
    RequestStatus,
    Service,
    StatusHistory,
    StockMovement,
    User,
    UserRole,
)

DEFAULT_PASSWORD = "Password123!"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def _clear_database(db: Session) -> None:
    db.execute(delete(StockMovement))
    db.execute(delete(RequestPart))
    db.execute(delete(RequestPhoto))
    db.execute(delete(MasterComment))
    db.execute(delete(StatusHistory))
    db.execute(delete(RepairRequest))
    db.execute(delete(Part))
    db.execute(delete(Service))
    db.execute(delete(User))
    db.flush()


def seed_database(db: Session, reset: bool = False) -> dict[str, int]:
    """Заполняет БД тестовыми данными: 1 админ, 2 мастера, 3 клиента, 10 услуг, 15 запчастей, 20 заявок."""
    if reset:
        _clear_database(db)
    elif (db.scalar(select(func.count(User.id))) or 0) > 0:
        return {
            "admins": 0,
            "masters": 0,
            "clients": 0,
            "services": 0,
            "parts": 0,
            "requests": 0,
        }

    password_hash = _hash_password(DEFAULT_PASSWORD)

    admin = User(
        full_name="Алексей Соколов",
        email="admin@repair.ru",
        phone="+7-900-100-00-01",
        password_hash=password_hash,
        role=UserRole.ADMIN,
    )
    masters = [
        User(
            full_name="Дмитрий Волков",
            email="master1@repair.ru",
            phone="+7-900-200-00-01",
            password_hash=password_hash,
            role=UserRole.MASTER,
        ),
        User(
            full_name="Игорь Морозов",
            email="master2@repair.ru",
            phone="+7-900-200-00-02",
            password_hash=password_hash,
            role=UserRole.MASTER,
        ),
    ]
    clients = [
        User(
            full_name="Мария Кузнецова",
            email="client1@repair.ru",
            phone="+7-900-300-00-01",
            password_hash=password_hash,
            role=UserRole.CLIENT,
        ),
        User(
            full_name="Сергей Петров",
            email="client2@repair.ru",
            phone="+7-900-300-00-02",
            password_hash=password_hash,
            role=UserRole.CLIENT,
        ),
        User(
            full_name="Елена Смирнова",
            email="client3@repair.ru",
            phone="+7-900-300-00-03",
            password_hash=password_hash,
            role=UserRole.CLIENT,
        ),
    ]
    db.add_all([admin, *masters, *clients])
    db.flush()

    services_data = [
        ("Замена дисплейного модуля смартфона", "Смартфоны", "Демонтаж битого экрана, установка нового модуля с проверкой TrueTone", Decimal("2500.00"), 90),
        ("Замена аккумулятора смартфона", "Смартфоны", "Замена АКБ с проклейкой влагозащиты и калибровкой", Decimal("1400.00"), 180),
        ("Ремонт разъёма зарядки USB-C / Lightning", "Смартфоны", "Пайка или замена нижнего шлейфа зарядки", Decimal("1800.00"), 60),
        ("Чистка ноутбука от пыли и замена термопасты", "Ноутбуки", "Полная разборка системы охлаждения, замена термопасты и термопрокладок", Decimal("2200.00"), 30),
        ("Замена матрицы ноутбука", "Ноутбуки", "Подбор и установка LCD/IPS матрицы, проверка шлейфа eDP", Decimal("3000.00"), 90),
        ("Замена клавиатуры ноутбука", "Ноутбуки", "Демонтаж топкейса, установка новой клавиатуры с перепайкой заклёпок", Decimal("2700.00"), 90),
        ("Восстановление после залития жидкостью", "Пайка BGA", "Ультразвуковая ванна, устранение коррозии, восстановление цепей питания", Decimal("4500.00"), 30),
        ("Реболлинг и замена контроллера питания", "Пайка BGA", "Микропайка BGA-микросхемы под микроскопом с диагностикой линии питания", Decimal("3800.00"), 60),
        ("Замена тачскрина / стекла планшета", "Планшеты", "Снятие разбитого сенсора, очистка и вклейка нового стекла", Decimal("2600.00"), 60),
        ("Комплексная диагностика и сборка ПК", "ПК", "Тестирование блока питания, материнской платы, ОЗУ и накопителей", Decimal("1500.00"), 30),
    ]
    services = [
        Service(
            title=title,
            category=category,
            description=description,
            base_price=base_price,
            warranty_days=warranty_days,
        )
        for title, category, description, base_price, warranty_days in services_data
    ]
    db.add_all(services)
    db.flush()

    parts_data = [
        ("DISP-IPH13-OLED", "Дисплей OLED для iPhone 13", "Дисплеи", Decimal("5200.00"), Decimal("7800.00"), 8, 2),
        ("DISP-SAM-A54", "Дисплей SuperAMOLED Samsung A54", "Дисплеи", Decimal("4100.00"), Decimal("6400.00"), 6, 2),
        ("BAT-IPH12", "Аккумулятор iPhone 12 (2815 mAh)", "Аккумуляторы", Decimal("1100.00"), Decimal("2100.00"), 14, 3),
        ("BAT-XIA-RN11", "Аккумулятор Xiaomi Redmi Note 11", "Аккумуляторы", Decimal("850.00"), Decimal("1650.00"), 12, 3),
        ("BAT-LEN-TP480", "Аккумулятор Lenovo ThinkPad T480", "Аккумуляторы", Decimal("2400.00"), Decimal("3900.00"), 5, 2),
        ("CHG-USBC-STD", "Разъём USB Type-C универсальный SMD", "Разъёмы и шлейфы", Decimal("180.00"), Decimal("550.00"), 30, 5),
        ("CHG-IPH-FLEX", "Нижний шлейф зарядки iPhone 13", "Разъёмы и шлейфы", Decimal("750.00"), Decimal("1450.00"), 10, 2),
        ("MAT-156-IPS", "Матрица ноутбука 15.6 FullHD IPS 30pin", "Матрицы", Decimal("4800.00"), Decimal("7200.00"), 6, 2),
        ("KBD-ASUS-X515", "Клавиатура ноутбука ASUS VivoBook X515", "Клавиатуры", Decimal("1350.00"), Decimal("2400.00"), 7, 2),
        ("COOL-MX4-4G", "Термопаста Arctic MX-4 (порция на обслуживание)", "Охлаждение", Decimal("200.00"), Decimal("600.00"), 25, 5),
        ("FAN-HP-15S", "Кулер системы охлаждения HP 15s", "Охлаждение", Decimal("900.00"), Decimal("1750.00"), 9, 2),
        ("IC-PMIC-TI", "Контроллер питания TPS65987DDH BGA", "Микросхемы", Decimal("650.00"), Decimal("1500.00"), 11, 3),
        ("IC-TRISTAR-U2", "Контроллер заряда Hydra U2", "Микросхемы", Decimal("420.00"), Decimal("1100.00"), 15, 3),
        ("SSD-NVME-512", "Накопитель SSD M.2 NVMe 512 GB", "Накопители", Decimal("2600.00"), Decimal("3900.00"), 8, 2),
        ("TOUCH-IPAD9", "Сенсорное стекло iPad 9 (10.2)", "Тачскрины", Decimal("1450.00"), Decimal("2700.00"), 6, 2),
    ]
    parts = [
        Part(
            sku=sku,
            name=name,
            category=category,
            purchase_price=purchase_price,
            retail_price=retail_price,
            stock_qty=stock_qty,
            min_stock_qty=min_stock_qty,
        )
        for sku, name, category, purchase_price, retail_price, stock_qty, min_stock_qty in parts_data
    ]
    db.add_all(parts)
    db.flush()

    now = datetime.now(UTC)
    for part in parts:
        db.add(
            StockMovement(
                part_id=part.id,
                request_id=None,
                performed_by_id=admin.id,
                movement_type=MovementType.IN,
                quantity=part.stock_qty,
                reason="Начальный приход при постановке склада на учёт",
                created_at=now - timedelta(days=30),
            )
        )

    devices = [
        ("Смартфон", "Apple", "iPhone 13", "Разбит экран после падения, сенсор не реагирует", 0, 0),
        ("Смартфон", "Samsung", "Galaxy A54", "Полосы на дисплее и нет изображения в нижней части", 0, 1),
        ("Смартфон", "Apple", "iPhone 12", "Быстро разряжается, выключается на 25% заряда", 1, 2),
        ("Смартфон", "Xiaomi", "Redmi Note 11", "Вздулась батарея, отходит задняя крышка", 1, 3),
        ("Ноутбук", "Lenovo", "ThinkPad T480", "Не держит заряд без сети, ошибка батареи", 1, 4),
        ("Смартфон", "Xiaomi", "Poco X5", "Расшатан разъём Type-C, заряжается только под углом", 2, 5),
        ("Смартфон", "Apple", "iPhone 13", "Не видит кабель зарядки и компьютер", 2, 6),
        ("Ноутбук", "HP", "15s-eq2000", "Сильно шумит кулер и перегревается под нагрузкой", 3, 9),
        ("Ноутбук", "Acer", "Aspire 5", "Треснула матрица после закрытия крышки с ручкой внутри", 4, 7),
        ("Ноутбук", "ASUS", "VivoBook X515", "Не работают клавиши верхнего ряда после пролития чая", 5, 8),
        ("Ноутбук", "Dell", "Inspiron 15", "Пролита вода на клавиатуру, не включается", 6, 9),
        ("Смартфон", "Apple", "iPhone 12 Pro", "Потребление тока по шине питания, не стартует", 7, 12),
        ("Планшет", "Apple", "iPad 9", "Паутина трещин на тачскрине, матрица целая", 8, 14),
        ("ПК", "Custom", "Workstation Ryzen 5", "Не определяется системный SSD и зависает BIOS", 9, 13),
        ("Ноутбук", "HP", "Pavilion 15", "Троттлинг процессора и треск вентилятора", 3, 10),
        ("Ноутбук", "ASUS", "ROG Strix G15", "Выгорела цепь питания Type-C после неоригинального БП", 7, 11),
        ("Смартфон", "Samsung", "Galaxy S22", "Нет быстрой зарядки, ошибка влаги в порту", 2, 5),
        ("Ноутбук", "Lenovo", "IdeaPad 3", "Полосы на экране при открытии крышки ноутбука", 4, 7),
        ("Планшет", "Samsung", "Galaxy Tab A8", "Разбито защитное стекло сенсора, нужен ремонт", 8, 14),
        ("ПК", "HP", "ProDesk 400", "Периодические перезагрузки и синий экран при работе", 9, 13),
    ]

    status_cycle = [
        RequestStatus.ACCEPTED,
        RequestStatus.DIAGNOSTICS,
        RequestStatus.IN_REPAIR,
        RequestStatus.READY,
        RequestStatus.ISSUED,
    ]
    progression = [
        RequestStatus.ACCEPTED,
        RequestStatus.DIAGNOSTICS,
        RequestStatus.IN_REPAIR,
        RequestStatus.READY,
        RequestStatus.ISSUED,
    ]

    requests: list[RepairRequest] = []
    for idx, (dev_type, brand, model, problem, svc_idx, part_idx) in enumerate(devices):
        target_status = status_cycle[idx % len(status_cycle)]
        client_user = clients[idx % len(clients)]
        service = services[svc_idx]
        part = parts[part_idx]
        assigned_master = None if target_status == RequestStatus.ACCEPTED else masters[idx % len(masters)]

        created_at = now - timedelta(days=20 - idx, hours=idx % 6)
        completed_at = (
            created_at + timedelta(days=2, hours=4)
            if target_status == RequestStatus.ISSUED
            else None
        )

        needs_estimate = target_status in {
            RequestStatus.IN_REPAIR,
            RequestStatus.READY,
            RequestStatus.ISSUED,
        }
        labor_cost = service.base_price if needs_estimate else Decimal("0.00")
        parts_cost = part.retail_price if needs_estimate and part.stock_qty > 0 else Decimal("0.00")
        total_cost = labor_cost + parts_cost

        diagnostic_result = (
            None
            if target_status == RequestStatus.ACCEPTED
            else f"Первичная диагностика устройства {brand} {model} подтвердила неисправность узла."
        )

        req = RepairRequest(
            client_id=client_user.id,
            master_id=assigned_master.id if assigned_master else None,
            service_id=service.id,
            device_type=dev_type,
            device_brand=brand,
            device_model=model,
            serial_number=f"SN-{2026000 + idx + 1}",
            appearance="Потёртости корпуса, следы повседневной эксплуатации",
            problem_description=problem,
            diagnostic_result=diagnostic_result,
            status=target_status,
            labor_cost=labor_cost,
            parts_cost=parts_cost,
            total_cost=total_cost,
            created_at=created_at,
            updated_at=completed_at or (created_at + timedelta(hours=3)),
            completed_at=completed_at,
        )
        db.add(req)
        db.flush()
        requests.append(req)

        target_pos = progression.index(target_status)
        prev_status: RequestStatus | None = None
        for step_idx in range(target_pos + 1):
            step_status = progression[step_idx]
            actor = admin if step_status in {RequestStatus.ACCEPTED, RequestStatus.ISSUED} else (assigned_master or admin)
            db.add(
                StatusHistory(
                    request_id=req.id,
                    changed_by_id=actor.id,
                    old_status=prev_status,
                    new_status=step_status,
                    note=f"Перевод заявки в статус «{step_status.value}»",
                    changed_at=created_at + timedelta(hours=step_idx * 4),
                )
            )
            prev_status = step_status

        if assigned_master is not None:
            db.add(
                MasterComment(
                    request_id=req.id,
                    author_id=assigned_master.id,
                    comment_text=f"Устройство {brand} {model} принято в работу инженером.",
                    is_internal=False,
                    created_at=created_at + timedelta(hours=2),
                )
            )
            db.add(
                RequestPhoto(
                    request_id=req.id,
                    uploaded_by_id=assigned_master.id,
                    file_url=f"/uploads/demo_req_{req.id}_intake.jpg",
                    caption="Состояние устройства при приёме",
                    uploaded_at=created_at + timedelta(minutes=30),
                )
            )

        if needs_estimate and part.stock_qty > 0:
            part.stock_qty -= 1
            db.add(
                RequestPart(
                    request_id=req.id,
                    part_id=part.id,
                    quantity=1,
                    unit_price=part.retail_price,
                    added_at=created_at + timedelta(hours=6),
                )
            )
            db.add(
                StockMovement(
                    part_id=part.id,
                    request_id=req.id,
                    performed_by_id=assigned_master.id if assigned_master else admin.id,
                    movement_type=MovementType.OUT,
                    quantity=1,
                    reason=f"Списание в заказ #{req.id}",
                    created_at=created_at + timedelta(hours=6),
                )
            )

    db.commit()

    return {
        "admins": 1,
        "masters": len(masters),
        "clients": len(clients),
        "services": len(services),
        "parts": len(parts),
        "requests": len(requests),
    }


def main() -> None:
    """Точка входа CLI для заполнения базы тестовыми данными."""
    parser = argparse.ArgumentParser(description="Заполнение БД тестовыми данными")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Очистить таблицы перед повторным заполнением",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        summary = seed_database(db, reset=args.reset)
    print("Результат заполнения БД:", summary)


if __name__ == "__main__":
    main()
