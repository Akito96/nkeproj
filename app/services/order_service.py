import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import (
    RepairRequest,
    RequestPart,
    RequestPhoto,
    RequestStatus,
    Service,
    StatusHistory,
    User,
    UserRole,
)
from app.schemas import RepairRequestCreate

MAX_PHOTOS_PER_ORDER = 5
MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PHOTO_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
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
    """Изменяет статус заявки и записывает переход в таблицу истории статусов."""
    old_status = order.status
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


def get_order_detail(
    db: Session,
    order_id: int,
    current_user: User,
) -> RepairRequest:
    """Возвращает детальную заявку с историей статусов при проверке прав владельца."""
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
