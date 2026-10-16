from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, model_validator, validator
from typing import List, Literal, Union
import secrets

DEFAULT_JWT_SECRET = "your-super-secret-jwt-key-change-this-in-production"
_DEV_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}
_PLACEHOLDER_PREFIX = "cambie-esto"


class Settings(BaseSettings):
    APP_NAME: str = "SoftGym"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: Union[List[AnyHttpUrl], List[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # ── Membresías ────────────────────────────────────────────────────────────
    # Días previos al vencimiento en que el socio pasa a "por vencer".
    MEMBERSHIP_EXPIRING_DAYS: int = 5
    # Días de gracia tras el vencimiento antes de marcarlo "moroso" (0 = moroso desde el día siguiente).
    MEMBERSHIP_GRACE_DAYS: int = 0

    # ── Caja y punto de venta ─────────────────────────────────────────────────
    # Si es True, para cobrar una membresía el usuario debe tener una caja ABIERTA (el cobro
    # queda ligado a su turno y entra en su arqueo). Las ventas de la tienda la exigen siempre.
    CASH_SESSION_REQUIRED: bool = True
    # Prefijo telefónico por defecto para los enlaces de WhatsApp (números locales de 8 dígitos).
    WHATSAPP_DEFAULT_COUNTRY_CODE: str = "506"

    # ── Consulta de cédula (Fácil Inscripción) ────────────────────────────────
    # Padrón de contribuyentes del Ministerio de Hacienda. Límites oficiales:
    # 100 solicitudes/5 s o 1200/2 min -> bloqueo de IP por 10 min.
    CEDULA_LOOKUP_ENABLED: bool = True
    CEDULA_LOOKUP_URL: str = "https://api.hacienda.go.cr/fe/ae"
    CEDULA_LOOKUP_TIMEOUT_SECONDS: float = 5.0
    CEDULA_LOOKUP_MAX_RETRIES: int = 2
    CEDULA_LOOKUP_CACHE_TTL_SECONDS: int = 86400          # resultados encontrados
    CEDULA_LOOKUP_NEGATIVE_CACHE_TTL_SECONDS: int = 600   # cédulas inexistentes
    CEDULA_LOOKUP_BREAKER_THRESHOLD: int = 5
    CEDULA_LOOKUP_BREAKER_COOLDOWN_SECONDS: int = 60
    # Orden en que Hacienda devuelve el campo "nombre" (no está documentado
    # oficialmente; verificar con una cédula propia y ajustar si hace falta).
    CEDULA_LOOKUP_NAME_ORDER: Literal["nombre_primero", "apellidos_primero"] = "nombre_primero"

    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @model_validator(mode="after")
    def _require_real_jwt_secret_outside_dev(self):
        """Fuera de desarrollo, la app NO arranca con una clave JWT pública o débil."""
        if self.ENVIRONMENT.lower() not in _DEV_ENVIRONMENTS:
            if (
                self.JWT_SECRET == DEFAULT_JWT_SECRET
                or self.JWT_SECRET.startswith(_PLACEHOLDER_PREFIX)
                or len(self.JWT_SECRET) < 32
            ):
                raise ValueError(
                    "JWT_SECRET debe definirse con un valor propio de al menos 32 "
                    "caracteres cuando ENVIRONMENT no es de desarrollo. "
                    "Genere uno con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
