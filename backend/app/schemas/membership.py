import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.membership import MembershipStatus


class MembershipSummary(BaseModel):
    """Membresía vigente (o la última) de un socio, con el tiempo restante ya calculado."""
    id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: str
    start_date: date
    end_date: date
    days_remaining: int          # 0 = vence hoy; negativo = ya venció
    days_overdue: int            # días de atraso (0 si no está vencida)
    state: Literal["vigente", "por_vencer", "vencida"]
    label: str                   # "Vence en 3 días", "Venció hace 5 días"…


class MembershipOut(BaseModel):
    """Una fila del historial de membresías de un socio."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: str
    start_date: date
    end_date: date
    status: MembershipStatus
    created_at: datetime
