from typing import Any, Optional

from fastapi import HTTPException, status


class SoftGymException(Exception):
    """
    Base de las excepciones de dominio. Cada subclase declara su status HTTP y un
    `code` legible por máquina; el manejador global las convierte en respuestas
    JSON {"detail": ..., "code": ...} sin que los routers hagan try/except.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_code: str = "internal_error"

    def __init__(self, detail: str, code: Optional[str] = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.default_code


class NotFoundException(SoftGymException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "not_found"

    def __init__(
        self,
        resource: str,
        identifier: Any = None,
        *,
        feminine: bool = False,
        code: Optional[str] = None,
    ) -> None:
        suffix = "no encontrada" if feminine else "no encontrado"
        detail = f"{resource} {suffix}"
        if identifier:
            detail = f"{resource} con id '{identifier}' {suffix}"
        super().__init__(detail, code)


class UnauthorizedException(SoftGymException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "unauthorized"

    def __init__(self, detail: str = "No autenticado", code: Optional[str] = None) -> None:
        super().__init__(detail, code)


class ForbiddenException(SoftGymException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "forbidden"

    def __init__(
        self,
        detail: str = "No tiene permisos para realizar esta acción",
        code: Optional[str] = None,
    ) -> None:
        super().__init__(detail, code)


class ConflictException(SoftGymException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"


class BusinessRuleException(SoftGymException):
    """Petición bien formada pero que viola una regla de negocio."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "business_rule_violation"


class ExternalServiceException(SoftGymException):
    """Un servicio externo no está disponible; la app sigue funcionando."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "external_service_unavailable"


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No se pudieron validar las credenciales",
    headers={"WWW-Authenticate": "Bearer"},
)

forbidden_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="No tiene permisos para realizar esta acción",
)
