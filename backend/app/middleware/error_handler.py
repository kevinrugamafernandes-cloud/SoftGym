"""
Manejo global de errores. TODOS los mensajes que llegan al usuario salen en español:
  - errores de validación de Pydantic (tipo de error -> mensaje en español)
  - errores HTTP por defecto de FastAPI/Starlette ("Not authenticated", "Not Found"...)
  - excepciones de dominio (SoftGymException)
  - errores no controlados (sin filtrar detalles internos)

Formato de respuesta: {"detail": "<mensaje legible>", "code": "<código>", "errors": [...]}
`detail` siempre es un texto listo para mostrarse en un Toast.
"""
import logging
from typing import Any, Dict, List

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import SoftGymException

logger = logging.getLogger(__name__)

# ── Etiquetas legibles de campos ──────────────────────────────────────────────
FIELD_LABELS: Dict[str, str] = {
    # socios
    "identification": "Identificación", "first_name": "Nombre", "last_name": "Apellidos",
    "birth_date": "Fecha de nacimiento", "gender": "Género", "phone": "Teléfono",
    "email": "Correo electrónico", "notes": "Notas", "status": "Estado",
    "joined_at": "Fecha de ingreso",
    # planes
    "name": "Nombre", "description": "Descripción", "duration_days": "Duración (días)",
    "price": "Precio", "is_active": "Activo",
    # ficha física
    "weight_kg": "Peso (kg)", "height_cm": "Estatura (cm)", "body_fat_pct": "% de grasa",
    "muscle_pct": "% de músculo", "chest_cm": "Pecho (cm)", "waist_cm": "Cintura (cm)",
    "hips_cm": "Cadera (cm)", "arms_cm": "Brazo (cm)", "thighs_cm": "Muslo (cm)",
    "calves_cm": "Pantorrilla (cm)", "recorded_at": "Fecha de medición", "bmi": "IMC",
    # usuarios / auth
    "password": "Contraseña", "full_name": "Nombre completo", "role": "Rol",
    # paginación y filtros
    "page": "Página", "size": "Tamaño de página", "search": "Búsqueda",
    "limit": "Límite", "offset": "Desplazamiento",
    # caja y punto de venta
    "opening_float": "Fondo inicial", "counted_cash": "Efectivo contado", "items": "Productos",
    "quantity": "Cantidad", "product_id": "Producto", "method": "Método de pago", "reference": "Referencia",
    "customer_name": "Nombre del cliente", "customer_phone": "Teléfono del cliente", "reason": "Motivo",
    "sku": "Código", "category": "Categoría", "cost": "Costo", "tax_rate": "Tarifa de IVA",
    "cabys_code": "Código CABYS", "min_stock": "Stock mínimo", "initial_stock": "Stock inicial",
    "counted_stock": "Stock contado", "unit_cost": "Costo unitario", "amount": "Monto",
    "payment_date": "Fecha del pago",
    # configuración, inscripción y reportes
    "legal_name": "Razón social", "tax_id": "Cédula", "whatsapp_phone": "WhatsApp comercial", "address": "Dirección",
    "receipt_message": "Mensaje de comprobantes", "overdue_message": "Mensaje de membresía vencida",
    "expiring_message": "Mensaje de membresía por vencer", "year": "Año", "month": "Mes",
    "date_from": "Desde", "date_to": "Hasta", "kind": "Tipo", "state": "Estado",
    # ids de ruta
    "member_id": "Identificador del socio", "plan_id": "Identificador del plan",
    "measurement_id": "Identificador de la medición",
}

_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}

_DATE_TYPES = {
    "date_parsing", "date_type", "date_from_datetime_parsing", "datetime_parsing",
    "datetime_type", "datetime_from_date_parsing",
}


def translate_validation_error(error: Dict[str, Any]) -> str:
    """Convierte un error de Pydantic v2 en un mensaje en español."""
    etype = error.get("type", "")
    ctx = error.get("ctx") or {}
    msg = error.get("msg", "")

    if etype == "missing":
        return "Este campo es obligatorio"
    if etype == "string_too_short":
        return f"Debe tener al menos {ctx.get('min_length')} caracteres"
    if etype == "string_too_long":
        return f"No puede superar {ctx.get('max_length')} caracteres"
    if etype == "too_short":
        return f"Debe tener al menos {ctx.get('min_length')} elementos"
    if etype == "too_long":
        return f"No puede tener más de {ctx.get('max_length')} elementos"
    if etype == "greater_than":
        return f"Debe ser mayor que {ctx.get('gt')}"
    if etype == "greater_than_equal":
        return f"Debe ser mayor o igual que {ctx.get('ge')}"
    if etype == "less_than":
        return f"Debe ser menor que {ctx.get('lt')}"
    if etype == "less_than_equal":
        return f"Debe ser menor o igual que {ctx.get('le')}"
    if etype in {"int_parsing", "int_type", "int_from_float"}:
        return "Debe ser un número entero"
    if etype in {"float_parsing", "float_type", "decimal_parsing", "decimal_type"}:
        return "Debe ser un número válido"
    if etype == "decimal_max_digits":
        return f"No puede tener más de {ctx.get('max_digits')} dígitos en total"
    if etype == "decimal_max_places":
        return f"No puede tener más de {ctx.get('decimal_places')} decimales"
    if etype == "decimal_whole_digits":
        return f"No puede tener más de {ctx.get('whole_digits')} dígitos enteros"
    if etype in {"bool_parsing", "bool_type"}:
        return "Debe ser verdadero o falso"
    if etype == "string_type":
        return "Debe ser texto"
    if etype in _DATE_TYPES:
        return "Fecha inválida (use el formato AAAA-MM-DD)"
    if etype in {"enum", "literal_error"}:
        return f"Valor no permitido. Valores válidos: {ctx.get('expected')}"
    if etype in {"uuid_parsing", "uuid_type"}:
        return "Identificador inválido"
    if etype == "json_invalid":
        return "El cuerpo de la solicitud no es un JSON válido"
    if etype in {"model_type", "model_attributes_type", "dict_type"}:
        return "Formato de datos inválido"
    if etype == "extra_forbidden":
        return "Campo no permitido"
    if etype == "value_error":
        # Los ValueError de nuestros validadores ya vienen en español.
        if "valid email address" in msg:
            return "Correo electrónico inválido"
        prefix = "Value error, "
        return msg[len(prefix):] if msg.startswith(prefix) else "Valor inválido"
    return "Valor inválido"


def _field_path(loc: Any) -> str:
    parts = [p for p in loc]
    if parts and parts[0] in _LOCATION_PREFIXES:
        parts = parts[1:]
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out


def _label(field: str) -> str:
    last = field.split(".")[-1].split("[")[0] if field else ""
    return FIELD_LABELS.get(last, last) if last else "Solicitud"


# ── Mensajes HTTP por defecto de FastAPI/Starlette ────────────────────────────
_HTTP_DETAIL_ES = {
    "Not authenticated": "No autenticado. Inicie sesión para continuar",
    "Forbidden": "Acceso denegado",
    "Not Found": "Recurso no encontrado",
    "Method Not Allowed": "Método no permitido",
    "Could not validate credentials": "No se pudieron validar las credenciales",
    "Insufficient permissions": "No tiene permisos para realizar esta acción",
    "Bad Request": "Solicitud inválida",
    "Unauthorized": "No autorizado",
    "Internal Server Error": "Ocurrió un error inesperado. Intente de nuevo",
}


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, str):
        detail = _HTTP_DETAIL_ES.get(detail, detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors: List[Dict[str, str]] = []
    for error in exc.errors():
        field = _field_path(error.get("loc", ()))
        errors.append({"field": field, "message": translate_validation_error(error)})

    first = errors[0]
    detail = f"Datos inválidos. {_label(first['field'])}: {first['message']}"
    if len(errors) > 1:
        detail += f" (y {len(errors) - 1} error{'es' if len(errors) > 2 else ''} más)"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail, "code": "validation_error", "errors": errors},
    )


async def softgym_exception_handler(request: Request, exc: SoftGymException):
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocurrió un error inesperado. Intente de nuevo", "code": "internal_error"},
    )
