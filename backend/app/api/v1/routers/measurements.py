import uuid

from fastapi import APIRouter, Query, Response
from fastapi import status as http_status

from app.dependencies.auth import AdminUser, StaffUser
from app.dependencies.services import MeasurementSvc
from app.schemas.body_measurement import (
    BodyMeasurementCreate,
    BodyMeasurementHistoryOut,
    BodyMeasurementOut,
    BodyMeasurementUpdate,
)

router = APIRouter(prefix="/members/{member_id}/measurements", tags=["Ficha física"])


@router.get("", response_model=BodyMeasurementHistoryOut, summary="Historial evolutivo del socio")
def list_measurements(
    member_id: uuid.UUID,
    _user: StaffUser,
    service: MeasurementSvc,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    items, total = service.list(member_id, limit=limit, offset=offset)
    return BodyMeasurementHistoryOut(
        member_id=member_id,
        items=[BodyMeasurementOut.model_validate(m) for m in items],
        total=total,
    )


@router.post(
    "",
    response_model=BodyMeasurementOut,
    status_code=http_status.HTTP_201_CREATED,
    summary="Registrar una medición (el IMC se calcula automáticamente)",
)
def create_measurement(
    member_id: uuid.UUID, data: BodyMeasurementCreate, user: StaffUser, service: MeasurementSvc
):
    return service.create(member_id, data, user)


@router.get("/{measurement_id}", response_model=BodyMeasurementOut, summary="Detalle de una medición")
def get_measurement(member_id: uuid.UUID, measurement_id: uuid.UUID, _user: StaffUser, service: MeasurementSvc):
    return service.get(member_id, measurement_id)


@router.patch("/{measurement_id}", response_model=BodyMeasurementOut, summary="Corregir una medición")
def update_measurement(
    member_id: uuid.UUID,
    measurement_id: uuid.UUID,
    data: BodyMeasurementUpdate,
    _user: StaffUser,
    service: MeasurementSvc,
):
    return service.update(member_id, measurement_id, data)


@router.delete(
    "/{measurement_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Eliminar una medición (solo administradores)",
)
def delete_measurement(member_id: uuid.UUID, measurement_id: uuid.UUID, _admin: AdminUser, service: MeasurementSvc):
    service.delete(member_id, measurement_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
