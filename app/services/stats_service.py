from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import REQUEST_STATUS_LABELS, RepairRequest, RequestStatus, User
from app.schemas import (
    AdminStatsResponse,
    StatsDailyPoint,
    StatsDeviceTypeItem,
    StatsMasterItem,
    StatsStatusItem,
    StatsSummary,
)

STATUS_ORDER: tuple[RequestStatus, ...] = (
    RequestStatus.ACCEPTED,
    RequestStatus.DIAGNOSTICS,
    RequestStatus.IN_REPAIR,
    RequestStatus.READY,
    RequestStatus.ISSUED,
)


def get_admin_stats(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AdminStatsResponse:
    """Агрегирует статистику заявок, выручки, типов устройств и мастеров за период."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата начала периода не может быть позже даты окончания",
        )

    stmt = select(RepairRequest)
    if date_from is not None:
        start_dt = datetime.combine(date_from, time.min, tzinfo=UTC)
        stmt = stmt.where(RepairRequest.created_at >= start_dt)
    if date_to is not None:
        end_exclusive = datetime.combine(
            date_to + timedelta(days=1), time.min, tzinfo=UTC
        )
        stmt = stmt.where(RepairRequest.created_at < end_exclusive)

    orders = list(db.scalars(stmt.order_by(RepairRequest.created_at.asc())).all())
    users_by_id = {
        user.id: user.full_name for user in db.scalars(select(User)).all()
    }

    total_orders = len(orders)
    total_revenue = sum((order.total_cost for order in orders), Decimal("0.00"))
    avg_order_value = (
        (total_revenue / total_orders).quantize(Decimal("0.01"))
        if total_orders > 0
        else Decimal("0.00")
    )
    completed_orders = sum(
        1 for order in orders if order.status == RequestStatus.ISSUED
    )
    active_orders = total_orders - completed_orders

    daily_counts: dict[str, int] = defaultdict(int)
    daily_revenue: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    status_counts: dict[RequestStatus, int] = {st: 0 for st in STATUS_ORDER}
    device_counts: dict[str, int] = defaultdict(int)
    device_revenue: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    master_counts: dict[int | None, int] = defaultdict(int)
    master_revenue: dict[int | None, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for order in orders:
        day_key = order.created_at.date().isoformat()
        daily_counts[day_key] += 1
        daily_revenue[day_key] += order.total_cost
        status_counts[order.status] = status_counts.get(order.status, 0) + 1

        dev_key = order.device_type.strip() or "Прочее"
        device_counts[dev_key] += 1
        device_revenue[dev_key] += order.total_cost

        master_counts[order.master_id] += 1
        master_revenue[order.master_id] += order.total_cost

    daily = [
        StatsDailyPoint(
            date=day_key,
            orders_count=daily_counts[day_key],
            revenue=daily_revenue[day_key],
        )
        for day_key in sorted(daily_counts.keys())
    ]

    by_status = [
        StatsStatusItem(
            status=st,
            label=REQUEST_STATUS_LABELS[st],
            count=status_counts[st],
        )
        for st in STATUS_ORDER
    ]

    by_device_type = sorted(
        [
            StatsDeviceTypeItem(
                device_type=dev_key,
                orders_count=device_counts[dev_key],
                revenue=device_revenue[dev_key],
            )
            for dev_key in device_counts
        ],
        key=lambda item: (-item.revenue, -item.orders_count, item.device_type),
    )

    by_master = sorted(
        [
            StatsMasterItem(
                master_id=m_id,
                master_name=(
                    users_by_id.get(m_id, f"Мастер #{m_id}")
                    if m_id is not None
                    else "Не назначен"
                ),
                orders_count=master_counts[m_id],
                revenue=master_revenue[m_id],
            )
            for m_id in master_counts
        ],
        key=lambda item: (-item.orders_count, -item.revenue, item.master_name),
    )

    return AdminStatsResponse(
        date_from=date_from.isoformat() if date_from is not None else None,
        date_to=date_to.isoformat() if date_to is not None else None,
        summary=StatsSummary(
            total_orders=total_orders,
            total_revenue=total_revenue,
            avg_order_value=avg_order_value,
            completed_orders=completed_orders,
            active_orders=active_orders,
        ),
        daily=daily,
        by_status=by_status,
        by_device_type=by_device_type,
        by_master=by_master,
    )
