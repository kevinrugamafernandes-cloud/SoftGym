"""
Cliente resiliente para autocompletar datos a partir de la cédula.

Fuente: API pública del Ministerio de Hacienda (https://api.hacienda.go.cr/fe/ae),
el padrón de CONTRIBUYENTES. Importante:
  * No es el Registro Civil: devuelve un único campo "nombre" y NO la fecha de nacimiento.
  * Solo conoce personas inscritas como contribuyentes; para el resto responde 404.
  * Política oficial: 100 solicitudes/5 s o 1200/2 min; al excederlas bloquea la IP 10 min.
    Cita como causas de bloqueo las consultas repetidas al mismo registro y las
    búsquedas constantes de identificaciones inexistentes.

Por eso el cliente implementa:
  * Caché en memoria: positiva (24 h) y NEGATIVA (10 min, para no repetir cédulas inexistentes).
  * Reintentos con backoff SOLO ante fallos transitorios (timeout, red, 5xx).
  * 429: NO se reintenta; se abre el cortacircuitos durante Retry-After (o el enfriamiento).
  * Cortacircuitos: tras N fallos seguidos deja de llamar al servicio durante un enfriamiento.
  * Nunca propaga excepciones de httpx: solo errores de dominio con mensaje en español.
"""
import logging
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceException, SoftGymException
from app.utils.names import split_full_name

logger = logging.getLogger(__name__)

# httpx registra a nivel INFO la URL COMPLETA de cada petición, y la cédula viaja en
# la query (?identificacion=...). Se silencia por debajo de WARNING para que ninguna
# cédula se escriba en claro en los logs (nuestros propios logs usan mask_identification).
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_TYPE_LABELS = {"01": "fisica", "02": "juridica", "03": "dimex", "04": "nite"}
_NOT_FOUND = object()  # marca de "cédula inexistente" en la caché
_EMPTY = object()      # respuesta 200 sin nombre (equivale a inexistente)


class CedulaNotFound(SoftGymException):
    status_code = 404
    default_code = "cedula_not_found"


class LookupUnavailable(ExternalServiceException):
    default_code = "lookup_unavailable"


@dataclass(frozen=True)
class LookupResult:
    identification: str
    full_name: str
    first_name: str
    last_name: str
    identification_type: Optional[str]  # fisica | juridica | dimex | nite | None


def mask_identification(identification: str) -> str:
    """Para logs: 112345678 -> 112***678 (no se escriben cédulas completas)."""
    return f"{identification[:3]}***{identification[-3:]}" if len(identification) >= 7 else "***"


class CedulaLookupService:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
        enabled: bool = True,
        max_retries: int = 2,
        backoff_seconds: float = 0.3,
        cache_ttl_seconds: int = 86400,
        negative_cache_ttl_seconds: int = 600,
        breaker_threshold: int = 5,
        breaker_cooldown_seconds: int = 60,
        name_order: str = "nombre_primero",
        cache_max_entries: int = 2000,
        client: Optional[httpx.Client] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url = base_url
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(3.0, timeout_seconds))
        self._enabled = enabled
        self._max_retries = max(0, max_retries)
        self._backoff = backoff_seconds
        self._ttl = cache_ttl_seconds
        self._neg_ttl = negative_cache_ttl_seconds
        self._threshold = breaker_threshold
        self._cooldown = breaker_cooldown_seconds
        self._name_order = name_order
        self._cache_max = cache_max_entries
        self._clock = clock
        self._sleep = sleep

        self._owns_client = client is None
        self._client = client or httpx.Client(
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "SoftGym/1.0 (Lion Fitness Center)"},
        )

        self._lock = threading.Lock()
        self._cache: Dict[str, Tuple[float, object]] = {}
        self._consecutive_failures = 0
        self._open_until = 0.0

    # ── API pública ───────────────────────────────────────────────────────────
    def lookup(self, identification: str) -> LookupResult:
        """Devuelve los datos o lanza CedulaNotFound / LookupUnavailable. Nunca httpx."""
        if not self._enabled:
            raise LookupUnavailable(
                "La consulta automática de cédulas está deshabilitada. Ingrese los datos manualmente",
                code="lookup_disabled",
            )

        cached = self._cache_get(identification)
        if cached is _NOT_FOUND:
            raise self._not_found()
        if cached is not None:
            return cached  # type: ignore[return-value]

        self._check_breaker()
        return self._fetch(identification)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ── Caché ─────────────────────────────────────────────────────────────────
    def _cache_get(self, key: str) -> Optional[object]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if self._clock() >= expires_at:
                del self._cache[key]
                return None
            return value

    def _cache_put(self, key: str, value: object, ttl: int) -> None:
        if ttl <= 0:
            return
        with self._lock:
            if len(self._cache) >= self._cache_max:
                now = self._clock()
                for k in [k for k, (exp, _) in self._cache.items() if exp <= now]:
                    del self._cache[k]
                if len(self._cache) >= self._cache_max:  # sigue lleno: descarta la más antigua
                    del self._cache[next(iter(self._cache))]
            self._cache[key] = (self._clock() + ttl, value)

    # ── Cortacircuitos ────────────────────────────────────────────────────────
    def _check_breaker(self) -> None:
        with self._lock:
            remaining = self._open_until - self._clock()
        if remaining > 0:
            logger.debug("Cortacircuitos abierto (%.0fs restantes): no se consulta Hacienda", remaining)
            raise self._unavailable()

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._open_until = 0.0

    def _record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold:
                self._open_until = self._clock() + self._cooldown
                logger.warning(
                    "Consulta de cédula: %d fallos seguidos; se pausa %ds",
                    self._consecutive_failures, self._cooldown,
                )

    def _open_breaker(self, seconds: float) -> None:
        with self._lock:
            self._open_until = self._clock() + seconds

    # ── Llamada HTTP ──────────────────────────────────────────────────────────
    def _fetch(self, identification: str) -> LookupResult:
        masked = mask_identification(identification)
        attempts = 1 + self._max_retries
        reason = "desconocido"

        for attempt in range(attempts):
            try:
                response = self._client.get(
                    self._url, params={"identificacion": identification}, timeout=self._timeout
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                reason = type(exc).__name__
            else:
                code = response.status_code
                if code == 200:
                    parsed = self._parse(identification, response)
                    if isinstance(parsed, LookupResult):
                        self._record_success()
                        self._cache_put(identification, parsed, self._ttl)
                        return parsed
                    if parsed is _EMPTY:
                        self._record_success()
                        self._cache_put(identification, _NOT_FOUND, self._neg_ttl)
                        raise self._not_found()
                    reason = "respuesta inválida"
                elif code in (400, 404):
                    # El servicio respondió con normalidad: la cédula no existe / no es válida.
                    self._record_success()
                    self._cache_put(identification, _NOT_FOUND, self._neg_ttl)
                    raise self._not_found()
                elif code == 429:
                    wait = self._retry_after(response)
                    self._open_breaker(max(wait, self._cooldown))
                    logger.warning("Hacienda respondió 429 para %s; se pausa la consulta", masked)
                    raise LookupUnavailable(
                        "Se alcanzó el límite de consultas del servicio. "
                        "Intente de nuevo en unos minutos o ingrese los datos manualmente",
                        code="lookup_rate_limited",
                    )
                elif code >= 500:
                    reason = f"HTTP {code}"
                else:  # otros 4xx (403, etc.): no tiene sentido reintentar
                    reason = f"HTTP {code}"
                    break

            if attempt < attempts - 1:
                self._sleep(self._backoff * (2 ** attempt))

        self._record_failure()
        logger.warning("Consulta de cédula %s falló (%s)", masked, reason)
        raise self._unavailable()

    def _parse(self, identification: str, response: httpx.Response):
        """LookupResult | _EMPTY (200 sin nombre: inexistente) | None (respuesta inválida)."""
        try:
            data = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None

        nombre = data.get("nombre")
        if not isinstance(nombre, str) or not nombre.strip():
            return _EMPTY

        full_name = " ".join(nombre.split())
        id_type = _TYPE_LABELS.get(str(data.get("tipoIdentificacion", "")))
        if id_type == "juridica":  # las empresas no se separan en nombre/apellidos
            first, last = full_name.title(), ""
        else:
            parsed = split_full_name(full_name, self._name_order)
            first, last = parsed.first_name, parsed.last_name
        return LookupResult(identification, full_name, first, last, id_type)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        try:
            return max(0.0, float(response.headers.get("Retry-After", "0")))
        except ValueError:
            return 0.0

    @staticmethod
    def _not_found() -> CedulaNotFound:
        return CedulaNotFound(
            "No se encontró la cédula en el registro de consulta. "
            "Puede ingresar los datos manualmente",
            code="cedula_not_found",
        )

    @staticmethod
    def _unavailable() -> LookupUnavailable:
        return LookupUnavailable(
            "El servicio de consulta de cédulas no está disponible en este momento. "
            "Ingrese los datos manualmente",
            code="lookup_unavailable",
        )


# ── Instancia compartida (caché y cortacircuitos deben vivir entre peticiones) ──
@lru_cache(maxsize=1)
def get_cedula_lookup_service() -> CedulaLookupService:
    return CedulaLookupService(
        base_url=settings.CEDULA_LOOKUP_URL,
        timeout_seconds=settings.CEDULA_LOOKUP_TIMEOUT_SECONDS,
        enabled=settings.CEDULA_LOOKUP_ENABLED,
        max_retries=settings.CEDULA_LOOKUP_MAX_RETRIES,
        cache_ttl_seconds=settings.CEDULA_LOOKUP_CACHE_TTL_SECONDS,
        negative_cache_ttl_seconds=settings.CEDULA_LOOKUP_NEGATIVE_CACHE_TTL_SECONDS,
        breaker_threshold=settings.CEDULA_LOOKUP_BREAKER_THRESHOLD,
        breaker_cooldown_seconds=settings.CEDULA_LOOKUP_BREAKER_COOLDOWN_SECONDS,
        name_order=settings.CEDULA_LOOKUP_NAME_ORDER,
    )


def shutdown_cedula_lookup_service() -> None:
    if get_cedula_lookup_service.cache_info().currsize:
        get_cedula_lookup_service().close()
        get_cedula_lookup_service.cache_clear()
