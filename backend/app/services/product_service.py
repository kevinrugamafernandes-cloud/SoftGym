"""Catálogo de productos e inventario: alta, edición y movimientos de stock auditados."""
import math
import uuid
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleException, ConflictException, NotFoundException
from app.models.product import InventoryMovement, MovementKind, Product
from app.models.user import User
from app.repositories.product_repository import ProductFilters, ProductRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.product import (
    MovementListOut, MovementOut, ProductCreate, ProductListOut, ProductOut, ProductUpdate, StockChange,
)
from app.schemas.sale import sale_code


def product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id, name=p.name, sku=p.sku, category=p.category, description=p.description, price=p.price,
        cost=p.cost, tax_rate=p.tax_rate, cabys_code=p.cabys_code, stock=p.stock, min_stock=p.min_stock,
        is_active=p.is_active, low_stock=p.is_active and p.stock <= p.min_stock,
        created_at=p.created_at, updated_at=p.updated_at,
    )


class ProductService:
    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id
        self._repo = ProductRepository(db, gym_id)

    # ── Consultas ─────────────────────────────────────────────────────────────
    def list(self, f: ProductFilters, *, page: int, size: int) -> ProductListOut:
        items, total = self._repo.search(f, page=page, size=size)
        return ProductListOut(
            items=[product_out(p) for p in items], total=total, page=page, size=size,
            pages=math.ceil(total / size) if total else 0, low_stock_count=self._repo.low_stock_count(),
        )

    def get(self, product_id: uuid.UUID) -> ProductOut:
        return product_out(self._get(product_id))

    def categories(self) -> List[str]:
        return self._repo.categories()

    def movements(self, product_id: uuid.UUID, *, page: int, size: int) -> MovementListOut:
        self._get(product_id)
        items, total = self._repo.movements(product_id, page=page, size=size)
        numbers = SaleRepository(self._db, self._gym_id).codes_for([m.sale_id for m in items if m.sale_id])
        return MovementListOut(
            items=[
                MovementOut(
                    id=m.id, kind=m.kind, quantity=m.quantity, stock_after=m.stock_after, unit_cost=m.unit_cost,
                    sale_id=m.sale_id, sale_code=sale_code(numbers[m.sale_id]) if m.sale_id in numbers else None,
                    notes=m.notes, user_name=m.user.full_name if m.user else None, created_at=m.created_at,
                )
                for m in items
            ],
            total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0,
        )

    # ── Alta y edición ────────────────────────────────────────────────────────
    def create(self, data: ProductCreate, user: User) -> ProductOut:
        self._ensure_unique(data.name, data.sku)
        fields = data.model_dump(exclude={"initial_stock"})
        product = Product(gym_id=self._gym_id, stock=data.initial_stock, **fields)
        try:
            self._repo.add(product)
            if data.initial_stock > 0:
                self._repo.add_movement(InventoryMovement(
                    gym_id=self._gym_id, product_id=product.id, kind=MovementKind.INITIAL,
                    quantity=data.initial_stock, stock_after=data.initial_stock, unit_cost=data.cost,
                    notes="Inventario inicial", user_id=user.id,
                ))
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ConflictException("Ya existe un producto con ese nombre o código", code="product_exists")
        self._db.refresh(product)
        return product_out(product)

    def update(self, product_id: uuid.UUID, data: ProductUpdate) -> ProductOut:
        product = self._get(product_id)
        changes = data.model_dump(exclude_unset=True)
        self._ensure_unique(changes.get("name"), changes.get("sku"), exclude_id=product.id)
        for field, value in changes.items():
            setattr(product, field, value)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ConflictException("Ya existe un producto con ese nombre o código", code="product_exists")
        self._db.refresh(product)
        return product_out(product)

    # ── Movimientos de stock ──────────────────────────────────────────────────
    def change_stock(self, product_id: uuid.UUID, data: StockChange, user: User) -> ProductOut:
        try:
            product = self._repo.get(product_id, for_update=True)  # serializa con las ventas en curso
            if product is None:
                raise NotFoundException("Producto", code="product_not_found")
            if data.kind == "entrada":
                delta = int(data.quantity or 0)
                kind = MovementKind.PURCHASE
            else:
                delta = int(data.counted_stock or 0) - product.stock
                kind = MovementKind.ADJUSTMENT
                if delta == 0:
                    raise BusinessRuleException("El stock contado es igual al actual: no hay nada que ajustar", code="no_stock_change")
            product.stock += delta
            if data.kind == "entrada" and data.unit_cost is not None:
                product.cost = data.unit_cost  # último costo de compra
            self._repo.add_movement(InventoryMovement(
                gym_id=self._gym_id, product_id=product.id, kind=kind, quantity=delta, stock_after=product.stock,
                unit_cost=data.unit_cost, notes=data.notes, user_id=user.id,
            ))
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(product)
        return product_out(product)

    # ── Internos ──────────────────────────────────────────────────────────────
    def _get(self, product_id: uuid.UUID) -> Product:
        product = self._repo.get(product_id)
        if product is None:
            raise NotFoundException("Producto", code="product_not_found")
        return product

    def _ensure_unique(self, name: Optional[str], sku: Optional[str], *, exclude_id: Optional[uuid.UUID] = None) -> None:
        if name and self._repo.get_by_name(name, exclude_id=exclude_id):
            raise ConflictException(f"Ya existe un producto llamado '{name}'", code="product_name_taken")
        if sku and self._repo.get_by_sku(sku, exclude_id=exclude_id):
            raise ConflictException(f"El código '{sku}' ya está asignado a otro producto", code="product_sku_taken")
