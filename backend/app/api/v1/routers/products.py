import uuid
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi import status as http_status

from app.dependencies.auth import AdminUser, FrontDeskUser
from app.dependencies.services import ProductSvc
from app.repositories.product_repository import ProductFilters
from app.schemas.product import (
    MovementListOut, ProductCreate, ProductListOut, ProductOut, ProductUpdate, StockChange,
)

router = APIRouter(prefix="/products", tags=["Productos e inventario"])


@router.get("", response_model=ProductListOut, summary="Catálogo con stock")
def list_products(
    _user: FrontDeskUser,
    service: ProductSvc,
    search: Optional[str] = Query(None, max_length=100, description="Nombre, código o categoría"),
    category: Optional[str] = Query(None, max_length=60),
    active_only: bool = Query(False),
    low_stock: bool = Query(False, description="Solo activos con stock en o bajo el mínimo"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    return service.list(ProductFilters(search, category, active_only, low_stock), page=page, size=size)


@router.get("/categories", response_model=List[str], summary="Categorías en uso")
def list_categories(_user: FrontDeskUser, service: ProductSvc):
    return service.categories()


@router.post("", response_model=ProductOut, status_code=http_status.HTTP_201_CREATED, summary="Crear producto (administrador)")
def create_product(data: ProductCreate, admin: AdminUser, service: ProductSvc):
    return service.create(data, admin)


@router.get("/{product_id}", response_model=ProductOut, summary="Detalle de un producto")
def get_product(product_id: uuid.UUID, _user: FrontDeskUser, service: ProductSvc):
    return service.get(product_id)


@router.patch("/{product_id}", response_model=ProductOut, summary="Editar producto (administrador; no cambia el stock)")
def update_product(product_id: uuid.UUID, data: ProductUpdate, _admin: AdminUser, service: ProductSvc):
    return service.update(product_id, data)


@router.post("/{product_id}/stock", response_model=ProductOut, summary="Entrada de mercadería o ajuste por conteo (administrador)")
def change_stock(product_id: uuid.UUID, data: StockChange, admin: AdminUser, service: ProductSvc):
    return service.change_stock(product_id, data, admin)


@router.get("/{product_id}/movements", response_model=MovementListOut, summary="Bitácora de inventario del producto")
def list_movements(
    product_id: uuid.UUID, _user: FrontDeskUser, service: ProductSvc,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    return service.movements(product_id, page=page, size=size)
