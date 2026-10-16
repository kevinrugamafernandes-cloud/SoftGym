# SoftGym · Fase 3 · Turno 4 (sesiones de caja + tienda POS + WhatsApp)

Los archivos ya están escritos en esta carpeta. No hay dependencias nuevas (backend ni frontend).

## Aplicar  (¡en este orden!)
    # 1) RESPALDAR LA BASE DE DATOS
    docker compose up -d --build backend frontend
    docker compose exec backend alembic upgrade head          # aplica 0006
    docker compose exec backend pytest app/tests -q           # 378 pruebas (+58)

## IMPORTANTE para la puesta en marcha
Desde esta versión **cobrar exige caja abierta** (`CASH_SESSION_REQUIRED=true`). Cada recepcionista debe
pulsar «Caja cerrada · Abrir» en el encabezado al iniciar su turno y cerrarla al terminar.
Para desactivar la regla temporalmente: `CASH_SESSION_REQUIRED=false` en el .env del backend.

## Qué probar
1. Encabezado → «Caja cerrada · Abrir» → fondo inicial. El indicador muestra el efectivo esperado en vivo.
2. Tienda → Vender: tocar productos (o escanear el código y Enter), método, vuelto, cliente opcional → Cobrar.
   Comprobante con Ticket PDF (80 mm) y «Enviar por WhatsApp».
3. Pagos → Registrar cobro: sin caja abierta aparece el aviso con «Abrir caja». El comprobante tiene WhatsApp.
4. Encabezado → «Caja abierta» → Cerrar caja: contar por total o por billetes y monedas; con diferencia
   pide observaciones; muestra sobrante/faltante.
5. Pagos → Caja del día: totales de membresías + tienda y la tabla de turnos con su arqueo.
6. Tienda → Inventario (admin): crear producto, entrada de mercadería, ajuste por conteo, bitácora.
7. Tienda → Ventas: historial con IVA, reimpresión, WhatsApp y anulación (admin; devuelve el stock).

Verificado: pytest 378/378 en PostgreSQL 16 · tsc · ESLint (sin avisos nuevos) · vite build ·
recorrido completo en navegador (recepcionista y administrador, escritorio y móvil).

## Cambios en código existente (y por qué)
- payments: columna `cash_session_id`; el cobro se liga a la caja del cajero (migración 0006).
- payment_service: exige caja abierta (configurable) y `cash_summary` suma las ventas de la tienda.
- PaymentOut incluye `cash_session_id`; CashSummaryOut agrega `payments_*`/`sales_*` (campos nuevos, compatibles).
- tests/conftest.py: las pruebas anteriores corren sin la regla de caja; las nuevas usan `@pytest.mark.cash_required`.
- Frontend: la Caja del día reemplaza el arqueo local (no se guardaba) por los turnos persistidos;
  el comprobante de pago suma el botón de WhatsApp; nuevo indicador de caja en el encabezado.

## Pendiente (siguiente turno)
- Libros internos para el contador: libro de ventas con IVA por tarifa, cierre mensual, exportación.
- Definir si las membresías llevan IVA (servicio gravado al 13 %): hoy solo la tienda desglosa IVA.
- Recordatorios de cobro vencido por WhatsApp (lista de morosos con enlace wa.me por socio).
