"""Schemas de productos e inventario."""
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.product import MovementKind

Price = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
TaxRate = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Stock = Annotated[int, Field(ge=0, le=1_000_000)]


def _clean(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


def _cabys(v: Optional[str]) -> Optional[str]:
    v = _clean(v)
    if v is None:
        return None
    if not re.fullmatch(r"\d{13}", v):
        raise ValueError("El código CABYS tiene 13 dígitos")
    return v


class ProductBase(BaseModel):
    name: str = Field(..., max_length=120)
    sku: Optional[str] = Field(None, max_length=40)
    category: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field(None, max_length=1000)
    price: Price
    cost: Optional[Price] = None
    tax_rate: TaxRate = Decimal("13.00")
    cabys_code: Optional[str] = None
    min_stock: Stock = 0

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v

    _sku = field_validator("sku", "category", "description")(_clean)
    _cab = field_validator("cabys_code")(_cabys)


class ProductCreate(ProductBase):
    initial_stock: Stock = 0
    is_active: bool = True


class ProductUpdate(BaseModel):
    """Edición parcial. El stock NO se edita aquí: se mueve con /stock (entrada o ajuste)."""
    name: Optional[str] = Field(None, max_length=120)
    sku: Optional[str] = Field(None, max_length=40)
    category: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[Price] = None
    cost: Optional[Price] = None
    tax_rate: Optional[TaxRate] = None
    cabys_code: Optional[str] = None
    min_stock: Optional[Stock] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v

    _sku = field_validator("sku", "category", "description")(_clean)
    _cab = field_validator("cabys_code")(_cabys)

    @model_validator(mode="after")
    def required_not_null(self):
        for name in ("name", "price", "tax_rate", "min_stock", "is_active"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"El campo '{name}' no puede ser nulo")
        return self


class StockChange(BaseModel):
    """
    entrada : suma `quantity` unidades (compra o reposición).
    ajuste  : fija el stock en `counted_stock` (conteo físico, merma, vencidos). Exige motivo.
    """
    kind: Literal["entrada", "ajuste"]
    quantity: Optional[int] = Field(None, ge=1, le=100_000)
    counted_stock: Optional[Stock] = None
    unit_cost: Optional[Price] = None
    notes: Optional[str] = Field(None, max_length=500)

    _notes = field_validator("notes")(_clean)

    @model_validator(mode="after")
    def by_kind(self):
        if self.kind == "entrada" and self.quantity is None:
            raise ValueError("Indique cuántas unidades ingresan")
        if self.kind == "ajuste":
            if self.counted_stock is None:
                raise ValueError("Indique el stock contado")
            if not self.notes or len(self.notes) < 3:
                raise ValueError("Indique el motivo del ajuste")
        return self


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sku: Optional[str]
    category: Optional[str]
    description: Optional[str]
    price: Decimal
    cost: Optional[Decimal]
    tax_rate: Decimal
    cabys_code: Optional[str]
    stock: int
    min_stock: int
    is_active: bool
    low_stock: bool
    created_at: datetime
    updated_at: datetime


class ProductListOut(BaseModel):
    items: List[ProductOut]
    total: int
    page: int
    size: int
    pages: int
    low_stock_count: int        # productos activos con stock <= mínimo (de todo el inventario)


class MovementOut(BaseModel):
    id: uuid.UUID
    kind: MovementKind
    quantity: int
    stock_after: int
    unit_cost: Optional[Decimal]
    sale_id: Optional[uuid.UUID]
    sale_code: Optional[str]
    notes: Optional[str]
    user_name: Optional[str]
    created_at: datetime


class MovementListOut(BaseModel):
    items: List[MovementOut]
    total: int
    page: int
    size: int
    pages: int
