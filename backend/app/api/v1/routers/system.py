from fastapi import APIRouter
from pydantic import BaseModel

from app.core.exceptions import NotFoundException
from app.dependencies.auth import AdminUser
from app.dependencies.services import StatusRefreshSvc
from app.repositories.gym_repository import GymRepository

router = APIRouter(prefix="/system", tags=["Sistema"])


class RefreshStatusesOut(BaseModel):
    memberships_expired: int
    members_updated: int


@router.post(
    "/refresh-statuses", response_model=RefreshStatusesOut,
    summary="Recalcular el estado (activo / por vencer / moroso) de los socios del gimnasio",
)
def refresh_statuses(admin: AdminUser, service: StatusRefreshSvc):
    gym = GymRepository(service._db).get(admin.gym_id)
    if gym is None:
        raise NotFoundException("Gimnasio", code="gym_not_found")
    result = service.refresh_gym(gym)
    return RefreshStatusesOut(memberships_expired=result.memberships_expired, members_updated=result.members_updated)
