import uuid
from typing import List

from fastapi import APIRouter, Query, Response
from fastapi import status as http_status

from app.dependencies.auth import AdminUser, FrontDeskUser
from app.dependencies.services import PlanSvc
from app.schemas.plan import PlanCreate, PlanOut, PlanUpdate

router = APIRouter(prefix="/plans", tags=["Planes"])


@router.get("", response_model=List[PlanOut], summary="Listar planes")
def list_plans(
    _user: FrontDeskUser,
    service: PlanSvc,
    active_only: bool = Query(False, description="Solo planes activos (los que se ofrecen al inscribir)"),
):
    return service.list(active_only=active_only)


@router.post(
    "", response_model=PlanOut, status_code=http_status.HTTP_201_CREATED, summary="Crear un plan (solo administradores)"
)
def create_plan(data: PlanCreate, _admin: AdminUser, service: PlanSvc):
    return service.create(data)


@router.get("/{plan_id}", response_model=PlanOut, summary="Detalle de un plan")
def get_plan(plan_id: uuid.UUID, _user: FrontDeskUser, service: PlanSvc):
    return service.get(plan_id)


@router.patch("/{plan_id}", response_model=PlanOut, summary="Editar un plan (solo administradores)")
def update_plan(plan_id: uuid.UUID, data: PlanUpdate, _admin: AdminUser, service: PlanSvc):
    return service.update(plan_id, data)


@router.delete(
    "/{plan_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Eliminar un plan sin membresías (solo administradores)",
)
def delete_plan(plan_id: uuid.UUID, _admin: AdminUser, service: PlanSvc):
    service.delete(plan_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
