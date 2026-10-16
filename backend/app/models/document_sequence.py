"""
Consecutivos por gimnasio y tipo de documento (ventas hoy; facturas electrónicas mañana).
Mismo mecanismo que receipt_sequences: UPDATE … RETURNING serializa y no deja huecos.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentSequence(Base):
    __tablename__ = "document_sequences"

    gym_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gyms.id", ondelete="RESTRICT"), primary_key=True
    )
    doc_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
