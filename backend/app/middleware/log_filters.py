"""
Filtros de logging.

El endpoint de Fácil Inscripción lleva la cédula en la RUTA
(GET /members/cedula-lookup/{cedula}) y el log de acceso de uvicorn imprime la ruta
completa. Este filtro enmascara la cédula (112345678 -> 112***678) antes de escribirla.
"""
import logging
import re

_PATH = re.compile(r"(/cedula-lookup/)([0-9\-\s%A-Za-z]+)")


def _mask(match: "re.Match[str]") -> str:
    digits = re.sub(r"[^0-9]", "", match.group(2))
    masked = f"{digits[:3]}***{digits[-3:]}" if len(digits) >= 7 else "***"
    return f"{match.group(1)}{masked}"


def mask_cedula_in_text(text: str) -> str:
    return _PATH.sub(_mask, text)


class MaskCedulaInAccessLog(logging.Filter):
    """Reescribe el argumento 'ruta' del log de acceso de uvicorn y el mensaje ya formateado."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                mask_cedula_in_text(a) if isinstance(a, str) else a for a in record.args
            )
        if isinstance(record.msg, str):
            record.msg = mask_cedula_in_text(record.msg)
        return True


def install_log_filters() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, MaskCedulaInAccessLog) for f in access.filters):
        access.addFilter(MaskCedulaInAccessLog())
