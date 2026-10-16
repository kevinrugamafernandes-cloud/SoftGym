import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from fastapi import status as http_status

from app.dependencies.auth import FrontDeskUser
from app.dependencies.services import CashSessionSvc
from app.models.cash_session import CashSessionStatus
from app.repositories.cash_session_repository import CashSessionFilters
from app.schemas.cash_session import (
    CashSessionClose, CashSessionListOut, CashSessionOpen, CashSessionOut, CurrentCashSessionOut,
)

router = APIRouter(prefix="/cash-sessions", tags=["Sesiones de caja"])


@router.get("/current", response_model=CurrentCashSessionOut, summary="Mi caja abierta (o null)")
def current_session(user: FrontDeskUser, service: CashSessionSvc):
    return service.current(user)


@router.post(
    "/open", response_model=CashSessionOut, status_code=http_status.HTTP_201_CREATED,
    summary="Abrir caja con fondo inicial",
    responses={409: {"description": "Ya tiene una caja abierta (cash_session_already_open)"}},
)
def open_session(data: CashSessionOpen, user: FrontDeskUser, service: CashSessionSvc):
    return service.open(data, user)


@router.post(
    "/{session_id}/close", response_model=CashSessionOut,
    summary="Cerrar caja con el conteo físico (calcula sobrante/faltante)",
)
def close_session(session_id: uuid.UUID, data: CashSessionClose, user: FrontDeskUser, service: CashSessionSvc):
    return service.close(session_id, data, user)


@router.get("", response_model=CashSessionListOut, summary="Historial de sesiones (la recepcionista ve solo las suyas)")
def list_sessions(
    user: FrontDeskUser,
    service: CashSessionSvc,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    cashier_id: Optional[uuid.UUID] = Query(None),
    status: Optional[CashSessionStatus] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    return service.list(CashSessionFilters(date_from, date_to, cashier_id, status), user, page=page, size=size)


@router.get("/{session_id}", response_model=CashSessionOut, summary="Detalle y resumen de una sesión")
def get_session(session_id: uuid.UUID, user: FrontDeskUser, service: CashSessionSvc):
    return service.get(session_id, user)
