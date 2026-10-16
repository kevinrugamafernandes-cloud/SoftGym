from fastapi import APIRouter
from app.api.v1.routers import (
    auth, cash_sessions, collections, health, measurements, members, payments, plans, products, reports, sales,
    settings, system,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(members.router)
api_router.include_router(measurements.router)
api_router.include_router(plans.router)
api_router.include_router(payments.router)
api_router.include_router(cash_sessions.router)
api_router.include_router(products.router)
api_router.include_router(sales.router)
api_router.include_router(collections.router)
api_router.include_router(reports.router)
api_router.include_router(settings.router)
api_router.include_router(system.router)
