# SoftGym · Frontend · Pagos y caja

Trabaja sobre el backend del núcleo financiero (Fase 3 · Turno 3). No hay dependencias nuevas:
`package.json` y `package-lock.json` no cambian. Verificado: `tsc --noEmit`, ESLint (sin avisos nuevos) y `vite build`.

## Probar
    docker compose up -d --build frontend backend
    # Iniciar sesión como administrador y como recepcionista en http://localhost:5173

1. **Pagos → Registrar cobro**: buscar socio por nombre o cédula (↑/↓ y Enter), elegir plan
   (el monto toma el precio de lista; si se baja, se muestra el descuento), método y referencia
   (obligatoria para SINPE y transferencia). Se ve la vista previa del nuevo periodo.
2. Repetir el MISMO cobro en menos de 60 s → aviso «¿Posible cobro duplicado?» con confirmación.
3. Tras cobrar: resumen del comprobante con botón **Ver / imprimir comprobante PDF**.
4. **Historial**: rangos rápidos (Hoy, 7 días, Este mes, Todo), método, mostrar/ocultar anulados,
   totales del filtro completo y paginación. Los filtros viven en la URL.
5. **Anular** (solo administrador): pide motivo (mín. 5 caracteres). Si no es el último pago del socio,
   el backend responde `void_latest_first` y el diálogo lo explica.
6. **Caja del día** (`/payments/caja`): total, efectivo esperado, anulaciones, desglose por método,
   cobros del día, navegación por días, **Imprimir cierre** (versión clara para papel) y arqueo de
   efectivo (sobrante/faltante; es de apoyo y NO se guarda).
7. **Ficha del socio**: panel «Membresía y pagos» con días restantes, botón Renovar/Cobrar y últimos pagos.

## Permisos de interfaz
- Administrador: cobrar, ver historial y caja, anular.
- Recepcionista: cobrar, ver historial y caja. No ve el botón de anular.
- Entrenador: no ve Pagos ni el panel de pagos en la ficha.

## Archivos
NUEVOS: types/payments.ts · services/payments.service.ts · hooks/usePayments.ts · lib/{money,dates}.ts ·
features/payments/{schemas,receipt}.ts · features/payments/components/{PaymentFormDialog,MemberPicker,
MembershipStateText,ReceiptSummary,VoidPaymentDialog,PaymentsTable,PaymentsNav,MemberBillingPanel}.tsx ·
components/common/StatTile.tsx · pages/payments/{PaymentsPage,CashPage}.tsx
MODIFICADOS: types/{index,members}.ts (Member.membership) · lib/{labels,query-keys}.ts ·
features/auth/permissions.ts (payments.*, cash.view) · routes/index.tsx · components/layout/Sidebar.tsx ·
layouts/AppLayout.tsx (oculta menú al imprimir) · styles/globals.css (@media print) · pages/members/MemberDetailPage.tsx

## Pendiente detectado (backend)
- Sesiones de caja (apertura con fondo, cierre con conteo y diferencia guardada, por cajero).
  Hoy la «caja» es un resumen diario calculado; el arqueo de la pantalla no se persiste.
