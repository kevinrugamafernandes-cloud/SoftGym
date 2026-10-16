"""Gimnasio (inquilino). Hoy hay uno (Lion Fitness Center); la estructura admite varios."""
import uuid

from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Gym(Base, TimestampMixin):
    __tablename__ = "gyms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    # Zona horaria del gimnasio: define qué es "hoy" para vencimientos y cierres de caja.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Costa_Rica")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CRC")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Datos del negocio (Configuración) ─────────────────────────────────────
    legal_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)      # razón social
    tax_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)           # cédula física/jurídica
    whatsapp_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)   # teléfono comercial
    email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Mensajes personalizables. Admiten {nombre}, {gimnasio}, {plan}, {fecha_vencimiento}, {dias}, {telefono}.
    receipt_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # pie de comprobantes
    overdue_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # recordatorio: vencida
    expiring_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)       # recordatorio: por vencer

    def __repr__(self) -> str:
        return f"<Gym {self.slug}>"
