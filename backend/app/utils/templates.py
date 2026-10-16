"""Mensajes personalizables con variables entre llaves: "Hola {nombre}, …"."""
import string
from typing import Dict, Iterable

from app.core.defaults import MESSAGE_PLACEHOLDERS


class _Missing(dict):
    def __missing__(self, key: str) -> str:   # una variable sin valor se deja tal cual
        return "{" + key + "}"


def validate_template(template: str, allowed: Iterable[str] = MESSAGE_PLACEHOLDERS) -> str:
    """Verifica llaves balanceadas y que solo se usen variables conocidas. Devuelve el texto limpio."""
    allowed = set(allowed)
    try:
        names = [f for _, f, _, _ in string.Formatter().parse(template) if f is not None]
    except ValueError:
        raise ValueError("El mensaje tiene llaves { } sin cerrar")
    unknown = sorted({n for n in names if n not in allowed})
    if any(n == "" for n in names):
        raise ValueError("Hay llaves vacías {} en el mensaje")
    if unknown:
        raise ValueError(
            f"Variable desconocida: {{{unknown[0]}}}. Use: " + ", ".join("{" + a + "}" for a in sorted(allowed))
        )
    return template.strip()


def render_template(template: str, values: Dict[str, str]) -> str:
    try:
        return template.format_map(_Missing(values))
    except (ValueError, IndexError, KeyError):
        return template   # una plantilla dañada nunca debe tumbar la pantalla de cobros
