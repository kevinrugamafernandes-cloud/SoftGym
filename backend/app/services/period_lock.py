"""Bloqueo de periodos con cierre mensual: lo entregado al contador no puede cambiar."""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.models.monthly_close import MonthlyClose

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
             "octubre", "noviembre", "diciembre"]


def month_label(year: int, month: int) -> str:
    return f"{MONTHS_ES[month - 1]} {year}"


def is_period_closed(db: Session, gym_id: uuid.UUID, d: date) -> bool:
    return db.scalar(
        select(MonthlyClose.id).where(
            MonthlyClose.gym_id == gym_id, MonthlyClose.year == d.year, MonthlyClose.month == d.month
        )
    ) is not None


def ensure_period_open(db: Session, gym_id: uuid.UUID, d: date, action: str) -> None:
    if is_period_closed(db, gym_id, d):
        raise ConflictException(
            f"El mes de {month_label(d.year, d.month)} ya tiene cierre contable: no se puede {action}",
            code="period_closed",
        )
