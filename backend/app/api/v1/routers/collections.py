import uuid
from typing import Optional

from fastapi import APIRouter, Query
from fastapi import status as http_status

from app.dependencies.auth import FrontDeskUser
from app.dependencies.services import CollectionsSvc
from app.schemas.collections import CollectionListOut, CollectionState, ReminderCreate, ReminderOut

router = APIRouter(prefix="/collections", tags=["Cobranza (morosos)"])


@router.get("", response_model=CollectionListOut, summary="Socios con membresía vencida o por vencer, con enlace wa.me")
def list_collections(
    _user: FrontDeskUser,
    service: CollectionsSvc,
    state: CollectionState = Query("vencida"),
    search: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
):
    return service.list(state, search=search, page=page, size=size)


@router.post(
    "/{member_id}/reminders", response_model=ReminderOut, status_code=http_status.HTTP_201_CREATED,
    summary="Registrar que se envió un recordatorio por WhatsApp",
)
def log_reminder(member_id: uuid.UUID, data: ReminderCreate, user: FrontDeskUser, service: CollectionsSvc):
    return service.log_reminder(member_id, data.kind, user)
