from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class OpenSessionOut(BaseModel):
    cashier_name: str
    opened_at: str
    expected_cash: Decimal


class DashboardOut(BaseModel):
    date: date
    currency: str
    # Hoy
    today_total: Decimal
    today_memberships: Decimal
    today_store: Decimal
    today_payments_count: int
    today_sales_count: int
    # Mes en curso (sin anulados)
    month_total: Decimal
    month_tax: Decimal
    # Socios
    members_active: int
    members_expiring: int
    members_overdue: int
    members_inactive: int
    members_new_month: int
    # Operación
    low_stock_count: int
    open_sessions: List[OpenSessionOut]
    my_session_open: Optional[bool]
