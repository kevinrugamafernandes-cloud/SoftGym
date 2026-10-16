"""
Reglas de vencimiento de membresías. Funciones PURAS (sin BD) para poder probarlas a fondo.

Convención (una sola, aplicada en todo el sistema):
  * `end_date` es el ÚLTIMO día con acceso (inclusive). Un plan de 30 días pagado el 1 de
    octubre cubre del 1 al 30; el 31 ya es el primer día de atraso.
  * `days_remaining = end_date - hoy`: 0 = vence hoy (último día); negativo = vencida.
  * hoy se calcula en la zona horaria del GIMNASIO.
"""
from datetime import date
from typing import Literal, Optional

from app.models.enums import MemberStatus
from app.models.member import Member
from app.models.membership import Membership

ExpiryState = Literal["vigente", "por_vencer", "vencida"]


def days_remaining(end_date: date, today: date) -> int:
    return (end_date - today).days


def expiry_state(end_date: date, today: date, warn_days: int) -> ExpiryState:
    d = days_remaining(end_date, today)
    if d < 0:
        return "vencida"
    if d <= warn_days:
        return "por_vencer"
    return "vigente"


def member_status_for(end_date: date, today: date, warn_days: int, grace_days: int) -> MemberStatus:
    """Estado calculado del socio a partir del vencimiento de su última membresía."""
    d = days_remaining(end_date, today)
    if d < -grace_days:
        return MemberStatus.EXPIRED          # moroso
    if d <= warn_days:
        return MemberStatus.EXPIRING_SOON    # por vencer (incluye el periodo de gracia)
    return MemberStatus.ACTIVE


def describe_days(d: int) -> str:
    """Texto para mostrar en la interfaz."""
    if d > 1:
        return f"Vence en {d} días"
    if d == 1:
        return "Vence mañana"
    if d == 0:
        return "Vence hoy"
    if d == -1:
        return "Venció ayer"
    return f"Venció hace {-d} días"


def sync_member_status(
    member: Member,
    latest: Optional[Membership],
    today: date,
    *,
    warn_days: int,
    grace_days: int,
    reactivate: bool,
) -> None:
    """
    Actualiza `member.status` según su última membresía vigente (no cancelada).

      * Sin membresías: el socio queda INACTIVO (nunca activo sin membresía ni pago).
      * Un socio marcado `inactivo` a mano NO se toca, salvo `reactivate=True` (p. ej. al
        registrarle un pago: pagar implica que vuelve a estar activo).
    """
    if latest is None:
        # Sin membresía (p. ej. se anuló su único pago) el socio no puede quedar activo.
        member.status = MemberStatus.INACTIVE
        return
    if member.status == MemberStatus.INACTIVE and not reactivate:
        return
    member.status = member_status_for(latest.end_date, today, warn_days, grace_days)
