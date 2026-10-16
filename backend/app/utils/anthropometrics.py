"""
Utilidades antropométricas.

Función pura (sin dependencias de DB ni de FastAPI) para poder
usarla tanto en los schemas Pydantic como en los servicios.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional


def calculate_bmi(
    weight_kg: Optional[Decimal],
    height_cm: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Calcula el IMC: peso_kg / (altura_m ** 2), redondeado a 2 decimales.

    Retorna None si falta algún dato o si la estatura es <= 0,
    para no persistir valores inválidos.
    """
    if weight_kg is None or height_cm is None:
        return None
    if height_cm <= 0 or weight_kg <= 0:
        return None

    height_m = height_cm / Decimal("100")
    bmi = weight_kg / (height_m * height_m)
    return bmi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def classify_bmi(bmi: Optional[Decimal]) -> Optional[str]:
    """Clasificación de la OMS para adultos."""
    if bmi is None:
        return None
    value = float(bmi)
    if value < 18.5:
        return "Bajo peso"
    if value < 25.0:
        return "Peso normal"
    if value < 30.0:
        return "Sobrepeso"
    if value < 35.0:
        return "Obesidad grado I"
    if value < 40.0:
        return "Obesidad grado II"
    return "Obesidad grado III"
