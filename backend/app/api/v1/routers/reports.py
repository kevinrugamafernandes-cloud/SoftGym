from datetime import date
from typing import List

from fastapi import APIRouter, Query, Response
from fastapi import status as http_status

from app.dependencies.auth import AdminUser, FrontDeskUser
from app.dependencies.services import DashboardSvc, ReportSvc
from app.schemas.dashboard import DashboardOut
from app.schemas.reports import MonthlyCloseCreate, MonthlyCloseItemOut, MonthlyReportOut, SalesBookOut

router = APIRouter(tags=["Reportes y contabilidad"])


@router.get("/dashboard", response_model=DashboardOut, summary="Métricas del día para el panel principal")
def dashboard(user: FrontDeskUser, service: DashboardSvc):
    return service.summary(user)


@router.get("/reports/sales-book", response_model=SalesBookOut, summary="Libro de ventas con IVA por tarifa (administrador)")
def sales_book(_admin: AdminUser, service: ReportSvc, date_from: date = Query(...), date_to: date = Query(...)):
    return service.sales_book(date_from, date_to)


@router.get("/reports/sales-book.csv", summary="Libro de ventas en CSV para Excel (administrador)",
            responses={200: {"content": {"text/csv": {}}}})
def sales_book_csv(_admin: AdminUser, service: ReportSvc, date_from: date = Query(...), date_to: date = Query(...)):
    data = service.sales_book_csv(date_from, date_to)
    name = f"libro-ventas_{date_from:%Y-%m-%d}_{date_to:%Y-%m-%d}.csv"
    return Response(content=data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/reports/monthly", response_model=MonthlyReportOut, summary="Resumen mensual y estado del cierre (administrador)")
def monthly(_admin: AdminUser, service: ReportSvc, year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12)):
    return service.monthly(year, month)


@router.get("/reports/monthly.pdf", summary="Cierre mensual en PDF para el contador (administrador)",
            responses={200: {"content": {"application/pdf": {}}}})
def monthly_pdf(_admin: AdminUser, service: ReportSvc, year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12)):
    pdf = service.monthly_pdf(year, month)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="cierre-{year}-{month:02d}.pdf"'})


@router.get("/reports/monthly-closes", response_model=List[MonthlyCloseItemOut], summary="Meses cerrados (administrador)")
def list_closes(_admin: AdminUser, service: ReportSvc):
    return service.closes()


@router.post("/reports/monthly-closes", response_model=MonthlyReportOut, status_code=http_status.HTTP_201_CREATED,
             summary="Cerrar un mes: congela sus totales y bloquea cambios en ese periodo (administrador)")
def close_month(data: MonthlyCloseCreate, admin: AdminUser, service: ReportSvc):
    return service.close_month(data.year, data.month, data.notes, admin)
