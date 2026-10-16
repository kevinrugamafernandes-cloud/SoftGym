import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query, Response
from fastapi import status as http_status

from app.dependencies.auth import AdminUser, FrontDeskUser
from app.dependencies.services import PaymentSvc
from app.models.payment import PaymentMethod
from app.repositories.payment_repository import PaymentFilters
from app.schemas.payment import (
    CashSummaryOut, PaymentCreate, PaymentListOut, PaymentOut, ReceiptOut, VoidRequest,
)
from app.schemas.sale import WhatsAppLinkOut

router = APIRouter(prefix="/payments", tags=["Pagos y caja"])


@router.post(
    "", response_model=PaymentOut, status_code=http_status.HTTP_201_CREATED,
    summary="Registrar un cobro (crea la membresía, el comprobante y actualiza el estado del socio)",
    responses={409: {"description": "Posible pago duplicado (possible_duplicate)"}},
)
def register_payment(data: PaymentCreate, user: FrontDeskUser, service: PaymentSvc):
    return service.register(data, user)


@router.get("", response_model=PaymentListOut, summary="Listar pagos con filtros y totales")
def list_payments(
    _user: FrontDeskUser,
    service: PaymentSvc,
    date_from: Optional[date] = Query(None, description="Fecha de pago desde (incluida)"),
    date_to: Optional[date] = Query(None, description="Fecha de pago hasta (incluida)"),
    method: Optional[PaymentMethod] = Query(None),
    member_id: Optional[uuid.UUID] = Query(None),
    include_voided: bool = Query(True, description="Incluir pagos anulados (marcados como tales)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    filters = PaymentFilters(date_from, date_to, method, member_id, include_voided)
    return service.list(filters, page=page, size=size)


# IMPORTANTE: "cash-summary" va ANTES de "/{payment_id}" para no confundirse con un identificador.
@router.get("/cash-summary", response_model=CashSummaryOut, summary="Cierre de caja de un día")
def cash_summary(
    _user: FrontDeskUser,
    service: PaymentSvc,
    day: Optional[date] = Query(None, alias="date", description="Por defecto, hoy en la zona horaria del gimnasio"),
):
    return service.cash_summary(day)


@router.get("/{payment_id}", response_model=PaymentOut, summary="Detalle de un pago")
def get_payment(payment_id: uuid.UUID, _user: FrontDeskUser, service: PaymentSvc):
    return service.get(payment_id)


@router.get("/{payment_id}/receipt", response_model=ReceiptOut, summary="Datos del comprobante")
def get_receipt(payment_id: uuid.UUID, _user: FrontDeskUser, service: PaymentSvc):
    return service.receipt(payment_id)


@router.get(
    "/{payment_id}/receipt.pdf", summary="Comprobante en PDF",
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_receipt_pdf(payment_id: uuid.UUID, _user: FrontDeskUser, service: PaymentSvc):
    code, pdf = service.receipt_pdf(payment_id)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="comprobante-{code}.pdf"'},
    )


@router.get("/{payment_id}/whatsapp", response_model=WhatsAppLinkOut, summary="Enlace wa.me con el comprobante del pago")
def payment_whatsapp(
    payment_id: uuid.UUID, _user: FrontDeskUser, service: PaymentSvc,
    phone: Optional[str] = Query(None, max_length=25, description="Por defecto, el teléfono del socio"),
):
    return service.whatsapp(payment_id, phone)


@router.post(
    "/{payment_id}/void", response_model=PaymentOut,
    summary="Anular un pago (solo administradores; solo el último pago del socio)",
)
def void_payment(payment_id: uuid.UUID, body: VoidRequest, admin: AdminUser, service: PaymentSvc):
    return service.void(payment_id, body.reason, admin)
