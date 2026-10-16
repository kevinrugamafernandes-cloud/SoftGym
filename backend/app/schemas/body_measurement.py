"""
Schemas de la Ficha Física (mediciones antropométricas).

El IMC NUNCA se recibe del cliente: se calcula aquí a partir de peso y
estatura (computed_field), de modo que el servicio lo persista siempre
consistente.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from app.utils.anthropometrics import calculate_bmi, classify_bmi

# Restricciones dentro de Annotated: Pydantic 2.7 no admite max_digits sobre
# Optional[Decimal] declarado con Field(...) directamente.
Weight = Annotated[Decimal, Field(gt=0, le=500, max_digits=5, decimal_places=2)]
Height = Annotated[Decimal, Field(ge=50, le=260, max_digits=5, decimal_places=2)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Girth300 = Annotated[Decimal, Field(gt=0, le=300, max_digits=5, decimal_places=2)]
Girth200 = Annotated[Decimal, Field(gt=0, le=200, max_digits=5, decimal_places=2)]
Girth150 = Annotated[Decimal, Field(gt=0, le=150, max_digits=5, decimal_places=2)]


class BodyMeasurementBase(BaseModel):
    weight_kg: Optional[Weight] = None
    height_cm: Optional[Height] = None
    body_fat_pct: Optional[Percent] = None
    muscle_pct: Optional[Percent] = None
    chest_cm: Optional[Girth300] = None
    waist_cm: Optional[Girth300] = None
    hips_cm: Optional[Girth300] = None
    arms_cm: Optional[Girth150] = None
    thighs_cm: Optional[Girth200] = None
    calves_cm: Optional[Girth150] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_metric(self):
        metrics = [
            self.weight_kg, self.height_cm, self.body_fat_pct, self.muscle_pct,
            self.chest_cm, self.waist_cm, self.hips_cm, self.arms_cm,
            self.thighs_cm, self.calves_cm,
        ]
        if all(m is None for m in metrics):
            raise ValueError("Debe registrar al menos una medida")
        return self

    @model_validator(mode="after")
    def composition_within_100(self):
        if (
            self.body_fat_pct is not None
            and self.muscle_pct is not None
            and self.body_fat_pct + self.muscle_pct > 100
        ):
            raise ValueError("La suma de % grasa y % músculo no puede superar 100")
        return self


class BodyMeasurementCreate(BodyMeasurementBase):
    recorded_at: Optional[datetime] = None  # por defecto: ahora (lo asigna el modelo)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bmi(self) -> Optional[Decimal]:
        return calculate_bmi(self.weight_kg, self.height_cm)


class BodyMeasurementUpdate(BaseModel):
    """
    Corrección de un registro existente. El IMC se recalcula en el servicio
    con los valores finales (peso/estatura nuevos o los ya guardados).
    """
    weight_kg: Optional[Weight] = None
    height_cm: Optional[Height] = None
    body_fat_pct: Optional[Percent] = None
    muscle_pct: Optional[Percent] = None
    chest_cm: Optional[Girth300] = None
    waist_cm: Optional[Girth300] = None
    hips_cm: Optional[Girth300] = None
    arms_cm: Optional[Girth150] = None
    thighs_cm: Optional[Girth200] = None
    calves_cm: Optional[Girth150] = None
    notes: Optional[str] = None


class BodyMeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_id: uuid.UUID
    recorded_at: datetime
    weight_kg: Optional[Decimal]
    height_cm: Optional[Decimal]
    bmi: Optional[Decimal]
    body_fat_pct: Optional[Decimal]
    muscle_pct: Optional[Decimal]
    chest_cm: Optional[Decimal]
    waist_cm: Optional[Decimal]
    hips_cm: Optional[Decimal]
    arms_cm: Optional[Decimal]
    thighs_cm: Optional[Decimal]
    calves_cm: Optional[Decimal]
    notes: Optional[str]
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bmi_category(self) -> Optional[str]:
        return classify_bmi(self.bmi)


class BodyMeasurementHistoryOut(BaseModel):
    """Historial evolutivo de un socio, más reciente primero."""
    member_id: uuid.UUID
    items: List[BodyMeasurementOut]
    total: int
