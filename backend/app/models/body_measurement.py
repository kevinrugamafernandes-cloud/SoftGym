"""
Modelo de Medición Corporal (Ficha Física).

Cada registro representa un snapshot antropométrico de un socio
en una fecha dada. Se almacenan múltiples registros por socio
para construir el historial de evolución.

El IMC se calcula y persiste en DB para:
  - Evitar recalcular en cada consulta.
  - Mantener consistencia histórica (el cálculo no cambia si
    cambia la fórmula en el futuro; los datos pasados conservan
    el valor del momento en que fueron registrados).

Fórmula IMC: peso_kg / (altura_m ** 2)
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.user import User


class BodyMeasurement(Base, GymScopedMixin):
    __tablename__ = "body_measurements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Claves foráneas ───────────────────────────────────────────────────────
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Fecha del registro ────────────────────────────────────────────────────
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )

    # ── Métricas primarias ────────────────────────────────────────────────────
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    height_cm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    bmi: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # ── Composición corporal ──────────────────────────────────────────────────
    body_fat_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    muscle_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # ── Medidas corporales (cm) ───────────────────────────────────────────────
    chest_cm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    waist_cm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    hips_cm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    arms_cm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    thighs_cm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    calves_cm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # ── Notas ─────────────────────────────────────────────────────────────────
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Auditoría ─────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relaciones ────────────────────────────────────────────────────────────
    member: Mapped["Member"] = relationship(
        "Member", back_populates="body_measurements"
    )
    recorded_by: Mapped[Optional["User"]] = relationship("User")

    # ── Helpers de clasificación IMC ──────────────────────────────────────────
    @property
    def bmi_category(self) -> Optional[str]:
        """Clasificación de la OMS según el IMC calculado."""
        if self.bmi is None:
            return None
        bmi_val = float(self.bmi)
        if bmi_val < 18.5:
            return "Bajo peso"
        elif bmi_val < 25.0:
            return "Peso normal"
        elif bmi_val < 30.0:
            return "Sobrepeso"
        elif bmi_val < 35.0:
            return "Obesidad grado I"
        elif bmi_val < 40.0:
            return "Obesidad grado II"
        else:
            return "Obesidad grado III"

    def __repr__(self) -> str:
        return (
            f"<BodyMeasurement id={self.id} member={self.member_id} "
            f"date={self.recorded_at.date()} bmi={self.bmi}>"
        )
