"""
Valores por defecto del negocio, compartidos por la migración 0007 (semilla) y el código.
Se copian a la BD al migrar: el administrador los cambia luego desde Configuración.
"""
from decimal import Decimal

# Planes oficiales de Lion Fitness Center (precio FINAL con IVA 13 % incluido).
# `aliases`: nombres equivalentes que ya pudieran existir; se actualiza ese plan en vez de duplicarlo.
OFFICIAL_PLANS = [
    {"name": "Pase de Día", "duration_days": 1, "price": Decimal("2000.00"),
     "description": "Acceso por un día", "aliases": ["pase de día", "pase de dia", "pase diario", "día", "dia"]},
    {"name": "Quincena", "duration_days": 15, "price": Decimal("13000.00"),
     "description": "Acceso por 15 días", "aliases": ["quincena", "quincenal"]},
    {"name": "Mensualidad", "duration_days": 30, "price": Decimal("20000.00"),
     "description": "Acceso por 30 días", "aliases": ["mensualidad", "mensual", "mes"]},
]

DEFAULT_OVERDUE_MESSAGE = (
    "Hola {nombre}, te saludamos de {gimnasio}. Te recordamos que tu membresía {plan} venció el "
    "{fecha_vencimiento}. Te esperamos para renovarla y seguir entrenando juntos. 💪"
)
DEFAULT_EXPIRING_MESSAGE = (
    "Hola {nombre}, te saludamos de {gimnasio}. Tu membresía {plan} vence el {fecha_vencimiento} "
    "({dias}). Renuévala en recepción para no perder tu continuidad. 💪"
)
DEFAULT_RECEIPT_MESSAGE = "¡Gracias por entrenar con nosotros!"

# Variables disponibles en los mensajes personalizados.
MESSAGE_PLACEHOLDERS = ["nombre", "gimnasio", "plan", "fecha_vencimiento", "dias", "telefono"]
