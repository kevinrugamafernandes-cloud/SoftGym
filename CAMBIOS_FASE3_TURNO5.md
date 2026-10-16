# SoftGym · Fase 3 · Turno 5 (versión de producción)

Todo está escrito en esta carpeta. No hay dependencias nuevas.

## Aplicar  (¡en este orden!)
    # 1) RESPALDAR LA BASE DE DATOS
    docker compose up -d --build backend frontend
    docker compose exec backend alembic upgrade head          # aplica 0007 (planes oficiales incluidos)
    docker compose exec backend pytest app/tests -q           # 405 pruebas
    # 2) Entrar como administrador → Configuración: completar WhatsApp comercial, cédula jurídica,
    #    dirección y revisar los mensajes de recordatorio.

Verificado: pytest 405/405 (PostgreSQL 16) · tsc sin errores · ESLint con --max-warnings 0 · vite build
sin advertencias (páginas cargadas bajo demanda) · recorrido en navegador como recepcionista y administrador.

## Qué cambió para el personal
- **Dashboard:** sin el aviso de "Fase 1". Ingresos de hoy y del mes, socios activos, morosos, pendientes
  (stock bajo, por vencer, inactivos, cajas abiertas) y accesos directos.
- **Asistencia:** oculta del menú y del panel.
- **Inscribir socio:** ahora son 2 pasos: datos → plan y cobro. El socio y su primer pago se guardan juntos
  (comprobante + WhatsApp al terminar). Solo el administrador ve "Registrar sin cobro" (queda inactivo).
- **Morosos** (menú): vencidas / por vencer, botón WhatsApp con el mensaje listo, copiar mensaje,
  último recordatorio y botón Cobrar.
- **Configuración** (admin): datos del negocio (salen en comprobantes, tickets y mensajes), mensajes con
  vista previa y gestión de planes (precio, duración, IVA, activar/desactivar).
- **Reportes** (admin): libro de ventas del mes (membresías + tienda) con IVA por tarifa, totales por
  tipo y método, arqueos, exportación CSV (Excel en español) y PDF, y **Cerrar mes**.
- Comprobantes de membresía muestran el IVA incluido.

## Cambios de comportamiento (importante)
- Un socio registrado sin pago queda **inactivo** (antes quedaba activo). Los socios existentes no cambian.
- Si se anula el único pago de un socio, queda inactivo (antes: activo sin membresía).
- Los pagos existentes quedan registrados con IVA 13 % incluido (la migración asume esa tarifa).
- Un mes cerrado no admite cobros con fecha de ese mes ni anulaciones de cobros/ventas de ese mes.

## Pruebas actualizadas (por el cambio de regla, no por fallas)
test_members_api (alta → inactivo; activar exige membresía) · test_member_membership_info · test_refresh_job ·
test_payments_void_cash · test_receipts · conftest (los planes oficiales sembrados se retiran antes de las pruebas;
test_migrations verifica la semilla).
