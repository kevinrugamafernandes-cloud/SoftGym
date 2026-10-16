"""Configuración del negocio (datos del gimnasio y mensajes personalizados)."""
import re
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.templates import validate_template
from app.utils.whatsapp import normalize_phone


def _clean(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v or None


class GymSettingsOut(BaseModel):
    name: str
    legal_name: Optional[str]
    tax_id: Optional[str]
    whatsapp_phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    receipt_message: Optional[str]
    overdue_message: str
    expiring_message: str
    currency: str
    timezone: str
    placeholders: List[str]


class GymSettingsUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    legal_name: Optional[str] = Field(None, max_length=160)
    tax_id: Optional[str] = Field(None, max_length=20)
    whatsapp_phone: Optional[str] = Field(None, max_length=25)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(None, max_length=500)
    receipt_message: Optional[str] = Field(None, max_length=300)
    overdue_message: Optional[str] = Field(None, max_length=1000)
    expiring_message: Optional[str] = Field(None, max_length=1000)

    _c = field_validator("legal_name", "address", "receipt_message")(_clean)

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v

    @field_validator("tax_id")
    @classmethod
    def tax_id_ok(cls, v: Optional[str]) -> Optional[str]:
        v = _clean(v)
        if v is None:
            return None
        digits = re.sub(r"[\s-]", "", v)
        if not re.fullmatch(r"\d{9,12}", digits):
            raise ValueError("La cédula física o jurídica tiene de 9 a 12 dígitos")
        return digits

    @field_validator("whatsapp_phone")
    @classmethod
    def phone_ok(cls, v: Optional[str]) -> Optional[str]:
        v = _clean(v)
        if v is None:
            return None
        if normalize_phone(v) is None:
            raise ValueError("Teléfono de WhatsApp inválido (8 dígitos en Costa Rica)")
        return re.sub(r"[\s\-()]", "", v)

    @field_validator("overdue_message", "expiring_message")
    @classmethod
    def template_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("El mensaje no puede quedar vacío")
        return validate_template(v)
