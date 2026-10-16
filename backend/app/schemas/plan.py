"""Schemas Pydantic del módulo de Planes."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Price = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
TaxRate = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]


class PlanBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    duration_days: int = Field(..., ge=1, le=3650)
    price: Price                                  # precio FINAL, con IVA incluido
    tax_rate: TaxRate = Decimal("13.00")          # IVA del servicio (13 % general en Costa Rica)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v


class PlanCreate(PlanBase):
    is_active: bool = True


class PlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    duration_days: Optional[int] = Field(None, ge=1, le=3650)
    price: Optional[Price] = None
    tax_rate: Optional[TaxRate] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v

    @model_validator(mode="after")
    def required_fields_not_null(self):
        for name in ("name", "duration_days", "price", "tax_rate", "is_active"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"El campo '{name}' no puede ser nulo")
        return self


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    duration_days: int
    price: Decimal
    tax_rate: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
