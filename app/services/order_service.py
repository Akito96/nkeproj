import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import (
    REQUEST_STATUS_LABELS,
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
from app.schemas import (
    MasterCommentCreate,
    OrderPartsAndLaborRequest,
    RepairRequestCreate,
    RepairRequestStatusUpdate,
    RequestPartCreate,
)

MAX_PHOTOS_PER_ORDER = 5
MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PHOTO_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

ALLOWED_STATUS_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.ACCEPTED: {RequestStatus.DIAGNOSTICS},
    RequestStatus.DIAGNOSTICS: {RequestStatus.IN_REPAIR},
    RequestStatus.IN_REPAIR: {RequestStatus.READY},
    RequestStatus.READY: {RequestStatus.ISSUED},
    RequestStatus.ISSUED: set(),
}


def _validate_and_save_photos(
    photos: list[UploadFile], upload_dir: Path
) -> list[str]:
    valid_photos = [photo for photo in photos if photo.filename]
    if len(valid_photos) > MAX_PHOTOS_PER_ORDER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Можно загрузить не более 5 фотографий к одной заявке",
        )

    buffered_files: list[tuple[str, bytes]] = []
    for photo in valid_photos:
        ext = Path(photo.filename or "").suffix.lower()
        content_type = (photo.content_type or "").lower()
        if (
            ext not in ALLOWED_PHOTO_EXTENSIONS
            or content_type not in ALLOWED_PHOTO_CONTENT_TYPES
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Допустимы только изображения форматов JPG, PNG или WEBP",
            )

        content = photo.file.read(MAX_PHOTO_SIZE_BYTES + 1)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Загруженный файл пуст",
            )
        if len(content) > MAX_PHOTO_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Размер каждой фотографии не должен превышать 5 МБ",
            )

        unique_name = f"{uuid.uuid4().hex}{ext}"
        buffered_files.append((unique_name, content))

    if not buffered_files:
        return []

    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    saved_urls: list[str] = []
    try:
        for unique_name, content in buffered_files:
            target_path = upload_dir / unique_name
            target_path.write_bytes(content)
            saved_paths.append(target_path)
            saved_urls.append(f"/uploads/{unique_name}")
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise

    return saved_urls


def _ensure_master_access(order: RepairRequest, current_user: User) -> None:
    if current_user.role == UserRole.MASTER and order.master_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешён только назначенному мастеру",
        )


def create_order(
    db: Session,
    current_user: User,
    payload: RepairRequestCreate,
    photos: list[UploadFile] | None = None,
) -> RepairRequest:
    """Создаёт заявку на ремонт, сохраняет фото и фиксирует начальный статус в истории."""
    service: Service | None = None
    if payload.service_id is not None:
        service = db.get(Service, payload.service_id)
        if service is None or not service.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Услуга не найдена",
            )

    upload_dir = Path(settings.upload_dir)
    saved_urls = _validate_and_save_photos(photos or [], upload_dir)

    base_labor = service.base_price if service is not None else Decimal("0.00")
    order = RepairRequest(
        client_id=current_user.id,
        service_id=service.id if service is not None else None,
        device_type=payload.device_type,
        device_brand=payload.device_brand,
        device_model=payload.device_model,
        serial_number=payload.serial_number,
        appearance=payload.appearance,
        problem_description=payload.problem_description,
        status=RequestStatus.ACCEPTED,
        labor_cost=base_labor,
        parts_cost=Decimal("0.00"),
        total_cost=base_labor,
    )

    try:
        db.add(order)
        db.flush()

        db.add(
            StatusHistory(
                request_id=order.id,
                changed_by_id=current_user.id,
                old_status=None,
                new_status=RequestStatus.ACCEPTED,
                note="Заявка создана",
            )
        )

        for url in saved_urls:
            db.add(
                RequestPhoto(
                    request_id=order.id,
                    uploaded_by_id=current_user.id,
                    file_url=url,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        for url in saved_urls:
            filename = Path(url).name
            (upload_dir / filename).unlink(missing_ok=True)
        raise

    return get_order_detail(db, order.id, current_user)


def change_order_status(
    db: Session,
    order: RepairRequest,
    new_status: RequestStatus,
    changed_by: User,
    note: str | None = None,
) -> RepairRequest:
    """Изменяет статус заявки с проверкой допустимого перехода и записью в историю."""
    old_status = order.status
    allowed_next = ALLOWED_STATUS_TRANSITIONS.get(old_status, set())
    if new_status not in allowed_next:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Недопустимый переход статуса из «{REQUEST_STATUS_LABELS[old_status]}» "
                f"в «{REQUEST_STATUS_LABELS[new_status]}»"
            ),
        )

    order.status = new_status
    if new_status == RequestStatus.ISSUED and order.completed_at is None:
        order.completed_at = datetime.now(UTC)

    db.add(
        StatusHistory(
            request_id=order.id,
            changed_by_id=changed_by.id,
            old_status=old_status,
            new_status=new_status,
            note=note,
        )
    )
    db.commit()
    db.refresh(order)
    return order


def list_my_orders(
    db: Session,
    current_user: User,
    status_filter: RequestStatus | None = None,
) -> list[RepairRequest]:
    """Возвращает историю заявок текущего авторизованного клиента."""
    stmt = select(RepairRequest).where(RepairRequest.client_id == current_user.id)
    if status_filter is not None:
        stmt = stmt.where(RepairRequest.status == status_filter)

    rows = db.scalars(
        stmt.order_by(RepairRequest.created_at.desc(), RepairRequest.id.desc())
    ).all()
    return list(rows)


def list_master_orders(
    db: Session,
    master_user: User,
    status_filter: RequestStatus | None = None,
) -> list[RepairRequest]:
    """Возвращает только заявки, назначенные конкретному мастеру."""
    stmt = select(RepairRequest).where(RepairRequest.master_id == master_user.id)
    if status_filter is not None:
        stmt = stmt.where(RepairRequest.status == status_filter)

    rows = db.scalars(
        stmt.order_by(RepairRequest.created_at.desc(), RepairRequest.id.desc())
    ).all()
    return list(rows)


def list_all_orders(
    db: Session,
    status_filter: RequestStatus | None = None,
    master_id: int | None = None,
    client_id: int | None = None,
) -> list[RepairRequest]:
    """Возвращает список всех заявок для панели администратора."""
    stmt = select(RepairRequest)
    if status_filter is not None:
        stmt = stmt.where(RepairRequest.status == status_filter)
    if master_id is not None:
        stmt = stmt.where(RepairRequest.master_id == master_id)
    if client_id is not None:
        stmt = stmt.where(RepairRequest.client_id == client_id)

    rows = db.scalars(
        stmt.order_by(RepairRequest.created_at.desc(), RepairRequest.id.desc())
    ).all()
    return list(rows)


def get_order_detail(
    db: Session,
    order_id: int,
    current_user: User,
) -> RepairRequest:
    """Возвращает детальную заявку с историей статусов при проверке прав доступа."""
    stmt = (
        select(RepairRequest)
        .options(
            selectinload(RepairRequest.status_history),
            selectinload(RepairRequest.comments),
            selectinload(RepairRequest.photos),
            selectinload(RepairRequest.used_parts).selectinload(RequestPart.part),
        )
        .where(RepairRequest.id == order_id)
    )
    order = db.scalar(stmt)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена",
        )

    if current_user.role == UserRole.CLIENT and order.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к чужой заявке запрещён",
        )

    return order


def assign_master_to_order(
    db: Session,
    order_id: int,
    master_id: int,
    admin_user: User,
) -> RepairRequest:
    """Назначает активного мастера ответственным исполнителем по заявке."""
    order = db.get(RepairRequest, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена",
        )

    master = db.get(User, master_id)
    if master is None or not master.is_active or master.role != UserRole.MASTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Указанный пользователь не является активным мастером",
        )

    order.master_id = master.id
    db.commit()
    return get_order_detail(db, order.id, admin_user)


def update_master_order_status(
    db: Session,
    order_id: int,
    payload: RepairRequestStatusUpdate,
    current_user: User,
) -> RepairRequest:
    """Обновляет статус заявки от имени назначенного мастера или администратора."""
    order = db.get(RepairRequest, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена",
        )

    _ensure_master_access(order, current_user)
    change_order_status(db, order, payload.status, current_user, note=payload.note)
    return get_order_detail(db, order.id, current_user)


def add_master_comment(
    db: Session,
    order_id: int,
    payload: MasterCommentCreate,
    current_user: User,
) -> MasterComment:
    """Добавляет комментарий мастера или администратора к заявке."""
    order = db.get(RepairRequest, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена",
        )

    _ensure_master_access(order, current_user)

    comment = MasterComment(
        request_id=order.id,
        author_id=current_user.id,
        comment_text=payload.comment_text,
        is_internal=payload.is_internal,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def apply_parts_and_labor(
    db: Session,
    order_id: int,
    payload: OrderPartsAndLaborRequest,
    current_user: User,
) -> RepairRequest:
    """Списывает запчасти со склада (SELECT FOR UPDATE), фиксирует работы и пересчитывает сумму в одной транзакции."""
    try:
        order = db.scalar(
            select(RepairRequest)
            .where(RepairRequest.id == order_id)
            .with_for_update()
        )
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заявка не найдена",
            )

        _ensure_master_access(order, current_user)

        if order.status == RequestStatus.ISSUED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя изменять выданную заявку",
            )

        requested_items: list[RequestPartCreate] = list(payload.parts)
        if payload.part_id is not None:
            requested_items.append(
                RequestPartCreate(
                    part_id=payload.part_id,
                    quantity=payload.quantity,
                    unit_price=payload.unit_price,
                )
            )

        existing_rp_map: dict[int, RequestPart] = {
            rp.part_id: rp
            for rp in db.scalars(
                select(RequestPart).where(RequestPart.request_id == order.id)
            ).all()
        }
        locked_parts: dict[int, Part] = {}

        for item in sorted(requested_items, key=lambda entry: entry.part_id):
            part = locked_parts.get(item.part_id)
            if part is None:
                part = db.scalar(
                    select(Part)
                    .where(Part.id == item.part_id)
                    .with_for_update()
                )
                if part is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Запчасть с ID {item.part_id} не найдена",
                    )
                locked_parts[item.part_id] = part

            if part.stock_qty < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Недостаточно запчасти «{part.name}» на складе "
                        f"(доступно: {part.stock_qty}, требуется: {item.quantity})"
                    ),
                )

            part.stock_qty -= item.quantity
            unit_price = (
                item.unit_price if item.unit_price is not None else part.retail_price
            )

            existing_rp = existing_rp_map.get(part.id)
            if existing_rp is not None:
                existing_rp.quantity += item.quantity
                existing_rp.unit_price = unit_price
            else:
                new_rp = RequestPart(
                    request_id=order.id,
                    part_id=part.id,
                    quantity=item.quantity,
                    unit_price=unit_price,
                )
                db.add(new_rp)
                existing_rp_map[part.id] = new_rp

            db.add(
                StockMovement(
                    part_id=part.id,
                    request_id=order.id,
                    performed_by_id=current_user.id,
                    movement_type=MovementType.OUT,
                    quantity=item.quantity,
                    reason=f"Списание в заявку №{order.id}",
                )
            )

        if payload.labor_cost is not None:
            order.labor_cost = payload.labor_cost
        if payload.diagnostic_result is not None:
            order.diagnostic_result = payload.diagnostic_result

        order.parts_cost = sum(
            (rp.unit_price * rp.quantity for rp in existing_rp_map.values()),
            Decimal(0),
        )
        order.total_cost = order.labor_cost + order.parts_cost

        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_order_detail(db, order.id, current_user)
