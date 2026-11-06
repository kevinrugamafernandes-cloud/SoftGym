"""
Freno a los ataques de fuerza bruta contra el login (en memoria, por proceso).

  * Por correo: tras LOGIN_MAX_ATTEMPTS fallos dentro de la ventana, esa cuenta queda
    bloqueada LOGIN_LOCKOUT_MINUTES (aunque el atacante cambie de IP).
  * Por IP: un tope más alto, para quien prueba muchos correos distintos.
Un inicio de sesión correcto limpia el contador del correo.

Con varias instancias del backend cada una lleva su propia cuenta; para un gimnasio con
una instancia es suficiente y no requiere Redis.
"""
import math
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from app.core.config import settings
from app.core.exceptions import TooManyRequestsException

_lock = threading.Lock()
_fails: Dict[str, Deque[float]] = defaultdict(deque)
_blocked_until: Dict[str, float] = {}


def _window() -> float:
    return settings.LOGIN_LOCKOUT_MINUTES * 60


def _prune(key: str, now: float) -> None:
    q = _fails[key]
    while q and now - q[0] > _window():
        q.popleft()


def _limit_for(key: str) -> int:
    return settings.LOGIN_MAX_ATTEMPTS_PER_IP if key.startswith("ip:") else settings.LOGIN_MAX_ATTEMPTS


def check(email: str, ip: str) -> None:
    """Lanza 429 si el correo o la IP están bloqueados."""
    now = time.monotonic()
    with _lock:
        for key in (f"email:{email.strip().lower()}", f"ip:{ip}"):
            until = _blocked_until.get(key)
            if until and until > now:
                minutes = max(1, math.ceil((until - now) / 60))
                raise TooManyRequestsException(
                    f"Demasiados intentos fallidos. Intente de nuevo en {minutes} minuto{'s' if minutes > 1 else ''}",
                    retry_after=int(until - now) + 1, code="too_many_attempts",
                )
            if until:
                _blocked_until.pop(key, None)


def register_failure(email: str, ip: str) -> None:
    now = time.monotonic()
    with _lock:
        for key in (f"email:{email.strip().lower()}", f"ip:{ip}"):
            _prune(key, now)
            _fails[key].append(now)
            if len(_fails[key]) >= _limit_for(key):
                _blocked_until[key] = now + _window()
                _fails[key].clear()


def register_success(email: str) -> None:
    with _lock:
        key = f"email:{email.strip().lower()}"
        _fails.pop(key, None)
        _blocked_until.pop(key, None)


def reset() -> None:
    """Solo para pruebas."""
    with _lock:
        _fails.clear()
        _blocked_until.clear()
