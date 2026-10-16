"""Inscripción: alta del socio + primer cobro en UNA transacción."""
import uuid
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.payment import PaymentMethod
from app.schemas.member import MemberCreate, MemberOut
from app.schemas.payment import Money, PaymentOut


class EnrollmentPayment(BaseModel):
    plan_id: uuid.UUID
    amount: Optional[Money] = None          # omitido → precio del plan
    method: PaymentMethod
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("reference", "notes")
    @classmethod
    def blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class EnrollmentCreate(BaseModel):
    member: MemberCreate
    payment: EnrollmentPayment


class EnrollmentOut(BaseModel):
    member: MemberOut
    payment: PaymentOut
