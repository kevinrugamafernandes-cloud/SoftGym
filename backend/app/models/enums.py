"""
Enums de dominio compartidos entre modelos y schemas.
Centralizados aquí para evitar importaciones circulares.
"""
from enum import Enum


class MemberStatus(str, Enum):
    """Estado actual de la membresía de un socio."""
    ACTIVE = "activo"
    EXPIRING_SOON = "por_vencer"   # vence en los próximos 5 días
    EXPIRED = "moroso"
    INACTIVE = "inactivo"          # dado de baja manualmente


class Gender(str, Enum):
    MALE = "masculino"
    FEMALE = "femenino"
    OTHER = "otro"
    PREFER_NOT_TO_SAY = "prefiero_no_decir"
