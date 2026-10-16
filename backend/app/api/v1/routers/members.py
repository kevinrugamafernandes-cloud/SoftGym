import uuid
from typing import Optional

from fastapi import APIRouter, Query, Response
from fastapi import status as http_status

from app.dependencies.auth import AdminUser, FrontDeskUser, StaffUser
from app.dependencies.services import CedulaLookupSvc, EnrollmentSvc, MemberSvc, MembershipSvc
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut
from app.models.enums import MemberStatus
from typing import List

from app.schemas.membership import MembershipOut
from app.schemas.member import (
    CedulaLookupOut,
    MemberCreate,
    MemberListOut,
    MemberOut,
    MemberUpdate,
)

router = APIRouter(prefix="/members", tags=["Socios"])


# IMPORTANTE: esta ruta va ANTES de "/{member_id}" para que "cedula-lookup" no se
# interprete como un identificador de socio.
@router.get(
    "/cedula-lookup/{cedula}",
    response_model=CedulaLookupOut,
    summary="Autocompletar nombre a partir de la cédula (Fácil Inscripción)",
    responses={
        404: {"description": "Cédula no encontrada en el registro (code: cedula_not_found)"},
        422: {"description": "Formato inválido o persona jurídica"},
        503: {"description": "Servicio externo no disponible (code: lookup_unavailable)"},
    },
)
def cedula_lookup(
    cedula: str, _user: FrontDeskUser, service: MemberSvc, lookup: CedulaLookupSvc
):
    return service.lookup_by_identification(cedula, lookup)


@router.get("", response_model=MemberListOut, summary="Listar socios (paginado, con filtros)")
def list_members(
    _user: StaffUser,
    service: MemberSvc,
    search: Optional[str] = Query(None, max_length=100, description="Nombre, apellidos o cédula"),
    status: Optional[MemberStatus] = Query(None, description="Filtrar por estado"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    return service.list(search=search, status=status, page=page, size=size)


@router.post(
    "", response_model=MemberOut, status_code=http_status.HTTP_201_CREATED,
    summary="Registrar un socio SIN cobro (queda inactivo hasta su primer pago)",
)
def create_member(data: MemberCreate, _user: FrontDeskUser, service: MemberSvc):
    return service.create(data)


@router.post(
    "/enroll", response_model=EnrollmentOut, status_code=http_status.HTTP_201_CREATED,
    summary="Inscribir: registra al socio y cobra su primer plan en una sola operación",
    responses={409: {"description": "Cédula registrada o sin caja abierta (cash_session_required)"}},
)
def enroll_member(data: EnrollmentCreate, user: FrontDeskUser, service: EnrollmentSvc):
    return service.enroll(data, user)


@router.get("/{member_id}", response_model=MemberOut, summary="Detalle de un socio")
def get_member(member_id: uuid.UUID, _user: StaffUser, service: MemberSvc):
    return service.get(member_id)


@router.patch("/{member_id}", response_model=MemberOut, summary="Actualizar datos de un socio")
def update_member(member_id: uuid.UUID, data: MemberUpdate, _user: FrontDeskUser, service: MemberSvc):
    return service.update(member_id, data)


@router.delete(
    "/{member_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Dar de baja a un socio (baja lógica, solo administradores)",
)
def delete_member(member_id: uuid.UUID, _admin: AdminUser, service: MemberSvc):
    service.delete(member_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post(
    "/{member_id}/restore",
    response_model=MemberOut,
    summary="Restaurar un socio dado de baja (solo administradores)",
)
def restore_member(member_id: uuid.UUID, _admin: AdminUser, service: MemberSvc):
    return service.restore(member_id)


@router.get(
    "/{member_id}/memberships",
    response_model=List[MembershipOut],
    summary="Historial de membresías del socio (más reciente primero)",
)
def list_member_memberships(member_id: uuid.UUID, _user: FrontDeskUser, service: MembershipSvc):
    return service.history(member_id)
