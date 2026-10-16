from typing import Annotated

from fastapi import Depends

from app.core.clock import Clock, get_clock
from app.dependencies.auth import CurrentUser, DbSession
from app.services.cash_session_service import CashSessionService
from app.services.collections_service import CollectionsService
from app.services.dashboard_service import DashboardService
from app.services.enrollment_service import EnrollmentService
from app.services.report_service import ReportService
from app.services.settings_service import SettingsService
from app.services.cedula_lookup_service import CedulaLookupService, get_cedula_lookup_service
from app.services.measurement_service import MeasurementService
from app.services.member_service import MemberService
from app.services.membership_service import MembershipService
from app.services.payment_service import PaymentService
from app.services.plan_service import PlanService
from app.services.product_service import ProductService
from app.services.sale_service import SaleService
from app.services.status_refresh_service import StatusRefreshService

# Cada servicio nace ligado al gimnasio del usuario autenticado (leído de la BD, no del token):
# así es imposible, por construcción, consultar o modificar datos de otro gimnasio.
ClockDep = Annotated[Clock, Depends(get_clock)]


def get_member_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> MemberService:
    return MemberService(db, user.gym_id, clock)


def get_plan_service(db: DbSession, user: CurrentUser) -> PlanService:
    return PlanService(db, user.gym_id)


def get_measurement_service(db: DbSession, user: CurrentUser) -> MeasurementService:
    return MeasurementService(db, user.gym_id)


def get_payment_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> PaymentService:
    return PaymentService(db, user.gym_id, clock)


def get_membership_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> MembershipService:
    return MembershipService(db, user.gym_id, clock)


def get_cash_session_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> CashSessionService:
    return CashSessionService(db, user.gym_id, clock)


def get_product_service(db: DbSession, user: CurrentUser) -> ProductService:
    return ProductService(db, user.gym_id)


def get_sale_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> SaleService:
    return SaleService(db, user.gym_id, clock)


def get_settings_service(db: DbSession, user: CurrentUser) -> SettingsService:
    return SettingsService(db, user.gym_id)


def get_enrollment_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> EnrollmentService:
    return EnrollmentService(db, user.gym_id, clock)


def get_collections_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> CollectionsService:
    return CollectionsService(db, user.gym_id, clock)


def get_report_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> ReportService:
    return ReportService(db, user.gym_id, clock)


def get_dashboard_service(db: DbSession, user: CurrentUser, clock: ClockDep) -> DashboardService:
    return DashboardService(db, user.gym_id, clock)


def get_status_refresh_service(db: DbSession, clock: ClockDep) -> StatusRefreshService:
    return StatusRefreshService(db, clock)


MemberSvc = Annotated[MemberService, Depends(get_member_service)]
PlanSvc = Annotated[PlanService, Depends(get_plan_service)]
MeasurementSvc = Annotated[MeasurementService, Depends(get_measurement_service)]
PaymentSvc = Annotated[PaymentService, Depends(get_payment_service)]
MembershipSvc = Annotated[MembershipService, Depends(get_membership_service)]
StatusRefreshSvc = Annotated[StatusRefreshService, Depends(get_status_refresh_service)]
CedulaLookupSvc = Annotated[CedulaLookupService, Depends(get_cedula_lookup_service)]
CashSessionSvc = Annotated[CashSessionService, Depends(get_cash_session_service)]
ProductSvc = Annotated[ProductService, Depends(get_product_service)]
SaleSvc = Annotated[SaleService, Depends(get_sale_service)]
SettingsSvc = Annotated[SettingsService, Depends(get_settings_service)]
EnrollmentSvc = Annotated[EnrollmentService, Depends(get_enrollment_service)]
CollectionsSvc = Annotated[CollectionsService, Depends(get_collections_service)]
ReportSvc = Annotated[ReportService, Depends(get_report_service)]
DashboardSvc = Annotated[DashboardService, Depends(get_dashboard_service)]
