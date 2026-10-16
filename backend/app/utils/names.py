"""
Separación aproximada de un nombre completo en nombre(s) y apellidos.

Hacienda entrega un solo campo "nombre" en MAYÚSCULAS. En Costa Rica lo habitual
es "NOMBRE(S) APELLIDO1 APELLIDO2", con apellidos que pueden llevar partículas
("DE LOS SANTOS", "DEL VALLE"). Esta separación es una HEURÍSTICA: por eso el
resultado siempre se marca `needs_review` y el formulario lo deja editable.
"""
from dataclasses import dataclass
from typing import List

_PARTICLES = {"de", "del", "la", "las", "los", "y", "san", "santa", "da", "di"}


@dataclass(frozen=True)
class ParsedName:
    first_name: str
    last_name: str


def _group_units(tokens: List[str]) -> List[List[str]]:
    """Agrupa tokens en 'unidades': cada palabra con las partículas que la preceden."""
    units: List[List[str]] = []
    current: List[str] = []
    for token in tokens:
        current.append(token)
        if token.lower() not in _PARTICLES:
            units.append(current)
            current = []
    if current:  # partículas sueltas al final: se pegan a la última unidad
        if units:
            units[-1].extend(current)
        else:
            units.append(current)
    return units


def _titlecase(tokens: List[str]) -> str:
    out = []
    for i, token in enumerate(tokens):
        low = token.lower()
        out.append(low if (low in _PARTICLES and i > 0) else low.capitalize())
    return " ".join(out)


def _join(units: List[List[str]]) -> str:
    return _titlecase([t for unit in units for t in unit])


def split_full_name(full_name: str, order: str = "nombre_primero") -> ParsedName:
    tokens = full_name.split()
    if not tokens:
        return ParsedName("", "")
    units = _group_units(tokens)

    if len(units) == 1:
        return ParsedName(_join(units), "")
    if len(units) == 2:
        first, last = (units[0], units[1]) if order == "nombre_primero" else (units[1], units[0])
        return ParsedName(_join([first]), _join([last]))

    if order == "nombre_primero":  # NOMBRES  AP1 AP2
        return ParsedName(_join(units[:-2]), _join(units[-2:]))
    return ParsedName(_join(units[2:]), _join(units[:2]))  # AP1 AP2  NOMBRES
