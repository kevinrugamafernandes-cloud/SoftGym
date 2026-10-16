import uuid
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.product import InventoryMovement, Product


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass
class ProductFilters:
    search: Optional[str] = None
    category: Optional[str] = None
    active_only: bool = False
    low_stock: bool = False


class ProductRepository:
    """Acceso a datos de Product e InventoryMovement. No hace commit: lo hace el servicio."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def get(self, product_id: uuid.UUID, *, for_update: bool = False) -> Optional[Product]:
        stmt = select(Product).where(Product.gym_id == self._gym_id, Product.id == product_id)
        if for_update:
            stmt = stmt.with_for_update()
        return self._db.scalars(stmt).first()

    def lock_many(self, product_ids: Sequence[uuid.UUID]) -> List[Product]:
        """
        Bloquea los productos de una venta en ORDEN de id: dos ventas simultáneas con los mismos
        productos esperan en el mismo orden y nunca se bloquean mutuamente (sin deadlocks).
        """
        return list(self._db.scalars(
            select(Product)
            .where(Product.gym_id == self._gym_id, Product.id.in_(list(product_ids)))
            .order_by(Product.id)
            .with_for_update()
        ).all())

    def get_by_name(self, name: str, *, exclude_id: Optional[uuid.UUID] = None) -> Optional[Product]:
        stmt = select(Product).where(Product.gym_id == self._gym_id, func.lower(Product.name) == name.strip().lower())
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        return self._db.scalars(stmt).first()

    def get_by_sku(self, sku: str, *, exclude_id: Optional[uuid.UUID] = None) -> Optional[Product]:
        stmt = select(Product).where(Product.gym_id == self._gym_id, func.lower(Product.sku) == sku.strip().lower())
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        return self._db.scalars(stmt).first()

    def add(self, product: Product) -> Product:
        self._db.add(product)
        self._db.flush()
        return product

    def add_movement(self, movement: InventoryMovement) -> InventoryMovement:
        self._db.add(movement)
        self._db.flush()
        return movement

    def search(self, f: ProductFilters, *, page: int, size: int) -> Tuple[List[Product], int]:
        stmt = select(Product).where(Product.gym_id == self._gym_id)
        if f.search:
            for word in f.search.split():
                pattern = f"%{_escape_like(word)}%"
                stmt = stmt.where(or_(
                    func.unaccent(Product.name).ilike(func.unaccent(pattern), escape="\\"),
                    Product.sku.ilike(pattern, escape="\\"),
                    func.unaccent(Product.category).ilike(func.unaccent(pattern), escape="\\"),
                ))
        if f.category:
            stmt = stmt.where(func.lower(Product.category) == f.category.strip().lower())
        if f.active_only:
            stmt = stmt.where(Product.is_active.is_(True))
        if f.low_stock:
            stmt = stmt.where(Product.stock <= Product.min_stock, Product.is_active.is_(True))
        total = self._db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self._db.scalars(
            stmt.order_by(Product.is_active.desc(), Product.category.nulls_last(), Product.name)
            .offset((page - 1) * size).limit(size)
        ).all()
        return list(items), total

    def low_stock_count(self) -> int:
        return self._db.scalar(
            select(func.count()).select_from(Product).where(
                Product.gym_id == self._gym_id, Product.is_active.is_(True), Product.stock <= Product.min_stock
            )
        ) or 0

    def categories(self) -> List[str]:
        rows = self._db.scalars(
            select(Product.category).where(Product.gym_id == self._gym_id, Product.category.is_not(None))
            .distinct().order_by(Product.category)
        ).all()
        return [r for r in rows if r]

    def movements(self, product_id: uuid.UUID, *, page: int, size: int) -> Tuple[List[InventoryMovement], int]:
        base = select(InventoryMovement).where(
            InventoryMovement.gym_id == self._gym_id, InventoryMovement.product_id == product_id
        )
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = self._db.scalars(
            base.options(selectinload(InventoryMovement.user))
            .order_by(InventoryMovement.created_at.desc(), InventoryMovement.stock_after)
            .offset((page - 1) * size).limit(size)
        ).all()
        return list(items), total
