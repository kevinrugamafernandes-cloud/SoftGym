from fastapi import APIRouter

from app.dependencies.auth import AdminUser, StaffUser
from app.dependencies.services import SettingsSvc
from app.schemas.settings import GymSettingsOut, GymSettingsUpdate

router = APIRouter(prefix="/settings", tags=["Configuración"])


@router.get("", response_model=GymSettingsOut, summary="Datos del negocio y mensajes personalizados")
def get_settings(_user: StaffUser, service: SettingsSvc):
    return service.get()


@router.patch("", response_model=GymSettingsOut, summary="Editar datos del negocio (administrador)")
def update_settings(data: GymSettingsUpdate, _admin: AdminUser, service: SettingsSvc):
    return service.update(data)
