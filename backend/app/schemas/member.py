"""Schemas Pydantic del módulo de Miembros."""
import re
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import Gender, MemberStatus
from app.schemas.membership import MembershipSummary


def normalize_identification(value: str) -> str:
    """Quita guiones y espacios y pasa a mayúsculas: '1-1234-5678' -> '112345678'."""
    return re.sub(r"[\s\-]", "", value).upper()


def _clean_phone(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    cleaned = re.sub(r"[\s\-()]", "", v)
    if not cleaned:
        return None
    if not re.fullmatch(r"\+?\d{7,15}", cleaned):
        raise ValueError("Teléfono inválido")
    return cleaned


def _birth_not_future(v: Optional[date]) -> Optional[date]:
    if v is not None and v > date.today():
        raise ValueError("La fecha de nacimiento no puede ser futura")
    return v


class MemberBase(BaseModel):
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    gender: Optional[Gender] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Este campo no puede estar vacío")
        if len(v) > 100:
            raise ValueError("Máximo 100 caracteres")
        return v

    _birth_ok = field_validator("birth_date")(_birth_not_future)
    _phone_ok = field_validator("phone")(_clean_phone)


class MemberCreate(MemberBase):
    identification: str
    joined_at: Optional[date] = None

    @field_validator("joined_at")
    @classmethod
    def joined_not_future(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("La fecha de ingreso no puede ser futura")
        return v

    @field_validator("identification")
    @classmethod
    def validate_identification(cls, v: str) -> str:
        normalized = normalize_identification(v)
        if not re.fullmatch(r"[A-Z0-9]{5,20}", normalized):
            raise ValueError("La identificación solo admite letras y números (5 a 20 caracteres)")
        return normalized


class MemberUpdate(BaseModel):
    """
    Actualización parcial. La cédula NO es editable: es el identificador
    natural del socio y la llave del historial.
    """
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[Gender] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    status: Optional[MemberStatus] = None

    _birth_ok = field_validator("birth_date")(_birth_not_future)
    _phone_ok = field_validator("phone")(_clean_phone)

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Este campo no puede estar vacío")
        if len(v) > 100:
            raise ValueError("Máximo 100 caracteres")
        return v

    @model_validator(mode="after")
    def required_fields_not_null(self):
        # first_name, last_name y status son NOT NULL: enviar null explícito no tiene sentido.
        for name in ("first_name", "last_name", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"El campo '{name}' no puede ser nulo")
        return self


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    identification: str
    first_name: str
    last_name: str
    full_name: str
    birth_date: Optional[date]
    gender: Optional[Gender]
    phone: Optional[str]
    email: Optional[str]
    status: MemberStatus
    joined_at: date
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Membresía vigente (o la última) con días restantes; None si nunca ha pagado.
    membership: Optional[MembershipSummary] = None


class MemberListOut(BaseModel):
    """Respuesta paginada del listado de miembros."""
    items: List[MemberOut]
    total: int
    page: int
    size: int
    pages: int


class MemberFilters(BaseModel):
    search: Optional[str] = None          # nombre, apellidos o cédula
    status: Optional[MemberStatus] = None
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class CedulaLookupOut(BaseModel):
    """
    Resultado de la consulta de cédula para "Fácil Inscripción".

    - `source="hacienda"`: datos del padrón de contribuyentes del Ministerio de Hacienda
      (NO es el Registro Civil: no incluye fecha de nacimiento y solo cubre contribuyentes).
    - `source="local"`: la cédula ya está registrada en SoftGym; no se consultó a Hacienda.
    - `needs_review=True`: Hacienda entrega un solo campo "nombre"; la separación en
      nombre/apellidos es una aproximación y el usuario debe confirmarla antes de guardar.
    """
    identification: str
    full_name: str
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    identification_type: Optional[str] = None
    source: Literal["hacienda", "local"] = "hacienda"
    needs_review: bool = True
    already_registered: bool = False
    existing_member_id: Optional[uuid.UUID] = None
    existing_member_deleted: bool = False
