"""
Punto de venta: venta de productos con descuento ATÓMICO de inventario.

Una venta es todo o nada, en UNA transacción:
  1. Bloquea la caja abierta del cajero (si no tiene, no se vende).
  2. Bloquea los productos en orden de id (sin deadlocks) y verifica stock.
  3. Calcula precios e IVA en el servidor (el cliente solo manda id y cantidad).
  4. Asigna el consecutivo, guarda la venta y sus líneas, descuenta el stock y deja
     un movimiento de inventario por línea.
Si algo falla, no queda nada: ni venta, ni número consumido, ni stock descontado.
La BD respalda la regla con CHECK (stock >= 0).
"""
import math
import uuid
from collections import OrderedDict
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.exceptions import (
    BusinessRuleException, ConflictException, NotFoundException, SoftGymException,
)
from app.models.payment import PaymentMethod
from app.models.product import InventoryMovement, MovementKind, Product
from app.models.sale import Sale, SaleItem
from app.models.user import User
from app.repositories.member_repository import MemberRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.sale_repository import SaleFilters, SaleRepository
from app.repositories.sequence_repository import next_document_number
from app.schemas.sale import (
    SaleCreate, SaleCustomerOut, SaleItemOut, SaleListOut, SaleOut, SaleTotalsOut, TaxBreakdownOut,
    WhatsAppLinkOut, sale_code,
)
from app.services.cash_session_service import CashSessionService, cash_session_required
from app.services.gym_context import GymContext
from app.services.period_lock import ensure_period_open
from app.services.payment_service import METHOD_LABELS
from app.utils.money import q2, split_tax_included
from app.utils.receipt_pdf import business_line
from app.utils.sale_pdf import SaleTicketData, SaleTicketLine, build_sale_pdf
from app.utils.whatsapp import normalize_phone, sale_message, wa_link

_REFERENCE_REQUIRED = {PaymentMethod.SINPE, PaymentMethod.TRANSFER}


class InsufficientStockException(SoftGymException):
    status_code = 409
    default_code = "insufficient_stock"

    def __init__(self, shortages: List[Tuple[Product, int]]) -> None:
        parts = [f"{p.name} (pidió {qty}, hay {p.stock})" for p, qty in shortages]
        super().__init__("Stock insuficiente: " + "; ".join(parts))
        self.shortages = shortages


def tax_breakdown(items) -> List[TaxBreakdownOut]:
    """Base e IVA agrupados por tarifa (lo que pide el libro de ventas y la factura 4.4)."""
    acc: Dict[Decimal, Tuple[Decimal, Decimal]] = {}
    for it in items:
        base, tax = acc.get(it.tax_rate, (Decimal("0"), Decimal("0")))
        acc[it.tax_rate] = (base + it.line_subtotal, tax + it.line_tax)
    return [TaxBreakdownOut(rate=r, base=q2(b), tax=q2(t)) for r, (b, t) in sorted(acc.items(), reverse=True)]


def sale_out(s: Sale) -> SaleOut:
    member = s.member
    return SaleOut(
        id=s.id, sale_number=s.sale_number, sale_code=sale_code(s.sale_number), sale_date=s.sale_date,
        created_at=s.created_at, cash_session_id=s.cash_session_id,
        cashier_name=s.cashier.full_name if s.cashier else None,
        customer=SaleCustomerOut(
            member_id=s.member_id,
            name=s.customer_name or (member.full_name if member else None),
            phone=s.customer_phone or (member.phone if member else None),
        ),
        method=s.method, reference=s.reference,
        items=[
            SaleItemOut(
                product_id=i.product_id, product_name=i.product_name, cabys_code=i.cabys_code, quantity=i.quantity,
                unit_price=i.unit_price, tax_rate=i.tax_rate, line_subtotal=i.line_subtotal, line_tax=i.line_tax,
                line_total=i.line_total,
            )
            for i in s.items
        ],
        taxes=tax_breakdown(s.items), subtotal=s.subtotal, tax_total=s.tax_total, total=s.total, notes=s.notes,
        is_voided=s.voided_at is not None, voided_at=s.voided_at,
        voided_by_name=s.voided_by.full_name if s.voided_by else None, void_reason=s.void_reason,
    )


class SaleService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._clock = clock
        self._ctx = GymContext(db, gym_id, clock)
        self._sales = SaleRepository(db, gym_id)
        self._products = ProductRepository(db, gym_id)
        self._members = MemberRepository(db, gym_id)
        self._sessions = CashSessionService(db, gym_id, clock)

    # ── Vender ────────────────────────────────────────────────────────────────
    def register(self, data: SaleCreate, user: User) -> SaleOut:
        try:
            return self._register(data, user)
        except Exception:
            self._db.rollback()  # todo o nada
            raise

    def _register(self, data: SaleCreate, user: User) -> SaleOut:
        session = self._sessions.lock_open_for(user)
        if session is None:
            raise cash_session_required()
        if data.method in _REFERENCE_REQUIRED and not data.reference:
            raise BusinessRuleException(
                f"Para pagos por {METHOD_LABELS[data.method]} indique el número de referencia o comprobante",
                code="reference_required",
            )
        if data.customer_phone and normalize_phone(data.customer_phone) is None:
            raise BusinessRuleException("El teléfono del cliente no es válido", code="invalid_phone")
        if data.member_id and self._members.get(data.member_id) is None:
            raise NotFoundException("Socio", code="member_not_found")

        # Misma línea repetida en el carrito → se suma (conserva el orden de aparición).
        wanted: "OrderedDict[uuid.UUID, int]" = OrderedDict()
        for line in data.items:
            wanted[line.product_id] = wanted.get(line.product_id, 0) + line.quantity

        products = {p.id: p for p in self._products.lock_many(list(wanted))}
        missing = [pid for pid in wanted if pid not in products]
        if missing:
            raise NotFoundException("Producto", code="product_not_found")
        inactive = [products[pid].name for pid in wanted if not products[pid].is_active]
        if inactive:
            raise BusinessRuleException(
                f"Producto inactivo, no se puede vender: {', '.join(inactive)}", code="product_inactive"
            )
        shortages = [(products[pid], qty) for pid, qty in wanted.items() if products[pid].stock < qty]
        if shortages:
            raise InsufficientStockException(shortages)

        sale = Sale(
            gym_id=self._gym_id, sale_number=next_document_number(self._db, self._gym_id, "venta"),
            sale_date=self._ctx.today, cash_session_id=session.id, cashier_id=user.id,
            member_id=data.member_id, customer_name=data.customer_name, customer_phone=data.customer_phone,
            method=data.method, reference=data.reference, notes=data.notes,
            subtotal=Decimal("0"), tax_total=Decimal("0"), total=Decimal("0"),
        )
        subtotal = tax_total = total = Decimal("0.00")
        for position, (pid, qty) in enumerate(wanted.items(), start=1):
            p = products[pid]
            line_total = q2(p.price * qty)
            base, tax = split_tax_included(line_total, p.tax_rate)
            sale.items.append(SaleItem(
                position=position, product_id=p.id, product_name=p.name, cabys_code=p.cabys_code, quantity=qty,
                unit_price=p.price, unit_cost=p.cost, tax_rate=p.tax_rate,
                line_subtotal=base, line_tax=tax, line_total=line_total,
            ))
            subtotal, tax_total, total = subtotal + base, tax_total + tax, total + line_total
        sale.subtotal, sale.tax_total, sale.total = subtotal, tax_total, total
        self._sales.add(sale)

        for item in sale.items:
            p = products[item.product_id]
            p.stock -= item.quantity
            self._products.add_movement(InventoryMovement(
                gym_id=self._gym_id, product_id=p.id, kind=MovementKind.SALE, quantity=-item.quantity,
                stock_after=p.stock, unit_cost=p.cost, sale_id=sale.id, user_id=user.id,
            ))
        self._db.commit()
        return self.get(sale.id)

    # ── Anular ────────────────────────────────────────────────────────────────
    def void(self, sale_id: uuid.UUID, reason: str, user: User) -> SaleOut:
        try:
            sale = self._sales.get(sale_id, for_update=True)
            if sale is None:
                raise NotFoundException("Venta", feminine=True, code="sale_not_found")
            if sale.voided_at is not None:
                raise ConflictException("La venta ya está anulada", code="already_voided")
            ensure_period_open(self._db, self._gym_id, sale.sale_date, "anular ventas de ese mes")
            products = {p.id: p for p in self._products.lock_many([i.product_id for i in sale.items])}
            for item in sale.items:
                p = products[item.product_id]
                p.stock += item.quantity            # la mercadería vuelve al inventario
                self._products.add_movement(InventoryMovement(
                    gym_id=self._gym_id, product_id=p.id, kind=MovementKind.SALE_VOID, quantity=item.quantity,
                    stock_after=p.stock, sale_id=sale.id, notes=reason, user_id=user.id,
                ))
            sale.voided_at = self._clock.now()
            sale.voided_by_id = user.id
            sale.void_reason = reason
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return self.get(sale_id)

    # ── Consultas ─────────────────────────────────────────────────────────────
    def _load(self, sale_id: uuid.UUID) -> Sale:
        sale = self._sales.get(sale_id)
        if sale is None:
            raise NotFoundException("Venta", feminine=True, code="sale_not_found")
        return sale

    def get(self, sale_id: uuid.UUID) -> SaleOut:
        sale = self._load(sale_id)
        self._db.refresh(sale)
        return sale_out(sale)

    def list(self, f: SaleFilters, *, page: int, size: int) -> SaleListOut:
        items, total = self._sales.search(f, page=page, size=size)
        t = self._sales.totals(f)
        return SaleListOut(
            items=[sale_out(s) for s in items], total=total, page=page, size=size,
            pages=math.ceil(total / size) if total else 0,
            totals=SaleTotalsOut(active_count=t.active_count, active_total=t.active_total, active_tax=t.active_tax,
                                 voided_count=t.voided_count, voided_total=t.voided_total),
        )

    def ticket_pdf(self, sale_id: uuid.UUID) -> Tuple[str, bytes]:
        s = sale_out(self._load(sale_id))
        gym = self._ctx.gym
        pdf = build_sale_pdf(SaleTicketData(
            gym_name=gym.name, currency=gym.currency, code=s.sale_code, sale_date=s.sale_date,
            created_at=s.created_at.astimezone(ZoneInfo(gym.timezone)), cashier=s.cashier_name, customer=s.customer.name,
            lines=[SaleTicketLine(i.quantity, i.product_name, i.unit_price, i.line_total, i.tax_rate) for i in s.items],
            subtotal=s.subtotal, taxes=[(t.rate, t.base, t.tax) for t in s.taxes], total=s.total,
            method_label=METHOD_LABELS[s.method], reference=s.reference, voided=s.is_voided, void_reason=s.void_reason,
            footer=gym.receipt_message,
            business=business_line(gym.legal_name, gym.tax_id, gym.whatsapp_phone, gym.address),
        ))
        return s.sale_code, pdf

    def whatsapp(self, sale_id: uuid.UUID, phone: Optional[str]) -> WhatsAppLinkOut:
        s = sale_out(self._load(sale_id))
        number = normalize_phone(phone or s.customer.phone)
        if number is None:
            raise BusinessRuleException(
                "Indique un número de WhatsApp válido (8 dígitos en Costa Rica)" if (phone or s.customer.phone)
                else "La venta no tiene teléfono del cliente: indique un número de WhatsApp",
                code="phone_required",
            )
        gym = self._ctx.gym
        message = sale_message(
            gym_name=gym.name, currency=gym.currency, code=s.sale_code, sale_date=s.sale_date, customer=s.customer.name,
            lines=[(i.quantity, i.product_name, i.line_total) for i in s.items], subtotal=s.subtotal,
            taxes=[(t.rate, t.tax) for t in s.taxes if t.tax > 0], total=s.total,
            method_label=METHOD_LABELS[s.method], reference=s.reference, voided=s.is_voided,
            footer=gym.receipt_message,
        )
        return WhatsAppLinkOut(phone=number, url=wa_link(number, message), message=message)
