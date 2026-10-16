"""
Cierre mensual contable. Al cerrar un mes se guarda una instantánea de sus totales (lo que se
entrega al contador) y el periodo queda BLOQUEADO: no se registran cobros con fecha de ese mes
ni se anulan cobros o ventas de ese mes. Así lo entregado al contador no cambia después.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin

if TYPE_CHECKING:
    from app.models.user import User


class MonthlyClose(Base, GymScopedMixin):
    __tablename__ = "monthly_closes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    closed_by: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        UniqueConstraint("gym_id", "year", "month", name="uq_monthly_closes_period"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_monthly_closes_month"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="ck_monthly_closes_year"),
    )
