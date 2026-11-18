from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    MovementType,
    Part,
    RepairRequest,
    RequestPart,
    StockMovement,
    User,
)
from app.schemas import PartCreate, PartUpdate, StockMovementCreate


def list_parts(
    db: Session,
    category: str | None = None,
    search: str | None = None,
    low_stock_only: bool = False,
) -> list[Part]:
    """Возвращает список запчастей на складе с фильтрацией и флагом низкого остатка."""
    if db.get_bind().dialect.name == "sqlite":
        rows = list(db.scalars(select(Part).order_by(Part.id.asc())).all())
        if category is not None and category.strip():
            cat_fold = category.strip().casefold()
            rows = [p for p in rows if p.category.strip().casefold() == cat_fold]
        if search is not None and search.strip():
            q_fold = search.strip().casefold()
            rows = [
                p
                for p in rows
                if q_fold in p.name.casefold() or q_fold in p.sku.casefold()
            ]
        if low_stock_only:
            rows = [p for p in rows if p.stock_qty <= p.min_stock_qty]
        return rows

    stmt = select(Part)
    if category is not None and category.strip():
        stmt = stmt.where(func.lower(Part.category) == category.strip().lower())
    if search is not None and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Part.name.ilike(pattern), Part.sku.ilike(pattern)))
    if low_stock_only:
        stmt = stmt.where(Part.stock_qty <= Part.min_stock_qty)

    return list(db.scalars(stmt.order_by(Part.id.asc())).all())


def get_part(db: Session, part_id: int) -> Part:
    """Возвращает запчасть по ID или выбрасывает 404."""
    part = db.get(Part, part_id)
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запчасть не найдена",
        )
    return part


def create_part(db: Session, payload: PartCreate, current_user: User) -> Part:
    """Создаёт позицию запчасти и фиксирует начальный приход в журнале склада."""
    existing = db.scalar(select(Part).where(Part.sku == payload.sku))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Запчасть с таким артикулом (SKU) уже существует",
        )

    part = Part(
        sku=payload.sku,
        name=payload.name,
        category=payload.category,
        purchase_price=payload.purchase_price,
        retail_price=payload.retail_price,
        stock_qty=payload.stock_qty,
        min_stock_qty=payload.min_stock_qty,
    )
    db.add(part)
    db.flush()

    if payload.stock_qty > 0:
        db.add(
            StockMovement(
                part_id=part.id,
                request_id=None,
                performed_by_id=current_user.id,
                movement_type=MovementType.IN,
                quantity=payload.stock_qty,
                reason="Начальный приход при добавлении позиции",
            )
        )

    db.commit()
    db.refresh(part)
    return part


def update_part(
    db: Session, part_id: int, payload: PartUpdate, current_user: User
) -> Part:
    """Обновляет запчасть с блокировкой строки и записью корректировки остатка."""
    try:
        part = db.scalar(
            select(Part).where(Part.id == part_id).with_for_update()
        )
        if part is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запчасть не найдена",
            )

        updates = payload.model_dump(exclude_unset=True)
        if "sku" in updates and updates["sku"] != part.sku:
            duplicate = db.scalar(
                select(Part).where(
                    Part.sku == updates["sku"],
                    Part.id != part.id,
                )
            )
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Запчасть с таким артикулом (SKU) уже существует",
                )

        old_stock = part.stock_qty
        for field, value in updates.items():
            setattr(part, field, value)

        if part.stock_qty < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Остаток на складе не может быть отрицательным",
            )

        delta = part.stock_qty - old_stock
        if delta != 0:
            db.add(
                StockMovement(
                    part_id=part.id,
                    request_id=None,
                    performed_by_id=current_user.id,
                    movement_type=MovementType.IN if delta > 0 else MovementType.WRITE_OFF,
                    quantity=abs(delta),
                    reason="Корректировка остатка администратором",
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(part)
    return part


def delete_part(db: Session, part_id: int) -> None:
    """Удаляет запчасть, если по ней не было движений и использований в заявках."""
    part = get_part(db, part_id)

    has_usage = db.scalar(
        select(RequestPart.id).where(RequestPart.part_id == part.id).limit(1)
    )
    has_movement = db.scalar(
        select(StockMovement.id).where(StockMovement.part_id == part.id).limit(1)
    )
    if has_usage is not None or has_movement is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Невозможно удалить запчасть, по которой есть история движения или использования в заявках",
        )

    db.delete(part)
    db.commit()


def create_stock_movement(
    db: Session, payload: StockMovementCreate, current_user: User
) -> StockMovement:
    """Проводит складскую операцию (приход/расход/возврат/списание) с блокировкой строки."""
    try:
        part = db.scalar(
            select(Part).where(Part.id == payload.part_id).with_for_update()
        )
        if part is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запчасть не найдена",
            )

        if payload.request_id is not None:
            order = db.get(RepairRequest, payload.request_id)
            if order is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Заявка не найдена",
                )

        if payload.movement_type in {MovementType.IN, MovementType.RETURN}:
            part.stock_qty += payload.quantity
        else:
            if part.stock_qty < payload.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Недостаточно запчасти «{part.name}» на складе "
                        f"(доступно: {part.stock_qty}, требуется: {payload.quantity})"
                    ),
                )
            part.stock_qty -= payload.quantity

        movement = StockMovement(
            part_id=part.id,
            request_id=payload.request_id,
            performed_by_id=current_user.id,
            movement_type=payload.movement_type,
            quantity=payload.quantity,
            reason=payload.reason,
        )
        db.add(movement)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(movement)
    return movement


def list_stock_movements(
    db: Session, part_id: int | None = None
) -> list[StockMovement]:
    """Возвращает журнал движений склада."""
    stmt = select(StockMovement)
    if part_id is not None:
        stmt = stmt.where(StockMovement.part_id == part_id)
    return list(
        db.scalars(
            stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        ).all()
    )
