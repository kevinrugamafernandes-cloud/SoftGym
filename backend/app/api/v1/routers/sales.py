import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query, Response
from fastapi import status as http_status

from app.dependencies.auth import AdminUser, FrontDeskUser
from app.dependencies.services import SaleSvc
from app.models.payment import PaymentMethod
from app.repositories.sale_repository import SaleFilters
from app.schemas.sale import SaleCreate, SaleListOut, SaleOut, SaleVoid, WhatsAppLinkOut

router = APIRouter(prefix="/sales", tags=["Punto de venta"])


@router.post(
    "", response_model=SaleOut, status_code=http_status.HTTP_201_CREATED,
    summary="Registrar una venta (descuenta stock y suma a la caja abierta)",
    responses={409: {"description": "Sin caja abierta (cash_session_required) o stock insuficiente (insufficient_stock)"}},
)
def register_sale(data: SaleCreate, user: FrontDeskUser, service: SaleSvc):
    return service.register(data, user)


@router.get("", response_model=SaleListOut, summary="Historial de ventas con totales")
def list_sales(
    _user: FrontDeskUser,
    service: SaleSvc,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    method: Optional[PaymentMethod] = Query(None),
    member_id: Optional[uuid.UUID] = Query(None),
    cash_session_id: Optional[uuid.UUID] = Query(None),
    include_voided: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    f = SaleFilters(date_from, date_to, method, member_id, cash_session_id, include_voided)
    return service.list(f, page=page, size=size)


@router.get("/{sale_id}", response_model=SaleOut, summary="Detalle de una venta")
def get_sale(sale_id: uuid.UUID, _user: FrontDeskUser, service: SaleSvc):
    return service.get(sale_id)


@router.get("/{sale_id}/ticket.pdf", summary="Ticket de venta en PDF (80 mm)", responses={200: {"content": {"application/pdf": {}}}})
def get_ticket_pdf(sale_id: uuid.UUID, _user: FrontDeskUser, service: SaleSvc):
    code, pdf = service.ticket_pdf(sale_id)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="venta-{code}.pdf"'})


@router.get("/{sale_id}/whatsapp", response_model=WhatsAppLinkOut, summary="Enlace wa.me con el comprobante de la venta")
def sale_whatsapp(
    sale_id: uuid.UUID, _user: FrontDeskUser, service: SaleSvc,
    phone: Optional[str] = Query(None, max_length=25, description="Por defecto, el teléfono del cliente"),
):
    return service.whatsapp(sale_id, phone)


@router.post("/{sale_id}/void", response_model=SaleOut, summary="Anular una venta (administrador; devuelve el stock)")
def void_sale(sale_id: uuid.UUID, body: SaleVoid, admin: AdminUser, service: SaleSvc):
    return service.void(sale_id, body.reason, admin)
