from decimal import Decimal

from pydantic import BaseModel

from app.models.base import RequestStatus


class StatsSummary(BaseModel):
    """Сводные KPI-показатели мастерской за выбранный период."""

    total_orders: int
    total_revenue: Decimal
    avg_order_value: Decimal
    completed_orders: int
    active_orders: int


class StatsDailyPoint(BaseModel):
    """Точка динамики заявок и выручки за конкретную дату."""

    date: str
    orders_count: int
    revenue: Decimal


class StatsStatusItem(BaseModel):
    """Количество заявок в конкретном статусе."""

    status: RequestStatus
    label: str
    count: int


class StatsDeviceTypeItem(BaseModel):
    """Статистика заявок и выручки по типу устройства."""

    device_type: str
    orders_count: int
    revenue: Decimal


class StatsMasterItem(BaseModel):
    """Статистика загрузки и выручки по мастеру."""

    master_id: int | None
    master_name: str
    orders_count: int
    revenue: Decimal


class AdminStatsResponse(BaseModel):
    """Агрегированная статистика для графиков панели администратора."""

    date_from: str | None
    date_to: str | None
    summary: StatsSummary
    daily: list[StatsDailyPoint]
    by_status: list[StatsStatusItem]
    by_device_type: list[StatsDeviceTypeItem]
    by_master: list[StatsMasterItem]
