"""Cobranza: socios con membresía vencida o por vencer y recordatorios por WhatsApp."""
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

CollectionState = Literal["vencida", "por_vencer"]


class CollectionItemOut(BaseModel):
    member_id: uuid.UUID
    full_name: str
    identification: str
    phone: Optional[str]
    plan_name: str
    end_date: date
    days: int                      # días de atraso (vencida) o días restantes (por vencer)
    state: CollectionState
    label: str                     # "Venció hace 5 días", "Vence mañana"…
    last_reminder_at: Optional[datetime]
    whatsapp_url: Optional[str]    # None si el socio no tiene un teléfono válido
    message: str


class CollectionListOut(BaseModel):
    items: List[CollectionItemOut]
    total: int
    page: int
    size: int
    pages: int
    overdue_count: int
    expiring_count: int


class ReminderCreate(BaseModel):
    kind: CollectionState


class ReminderOut(BaseModel):
    member_id: uuid.UUID
    kind: CollectionState
    created_at: datetime
