import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import SoftGymException
from app.middleware.log_filters import install_log_filters
from app.middleware.error_handler import (
    http_exception_handler,
    softgym_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.services.cedula_lookup_service import shutdown_cedula_lookup_service

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
install_log_filters()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SoftGym API starting — env: %s", settings.ENVIRONMENT)
    yield
    shutdown_cedula_lookup_service()
    logger.info("SoftGym API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="SoftGym — Lion Fitness Center Management System",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(SoftGymException, softgym_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(api_router)
    return app


app = create_app()
