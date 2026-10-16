# SoftGym · Fase 2 · Frontend · Turno 1 (módulo de Socios)

Extraer en la raíz del proyecto (donde están `backend/` y `frontend/`) y aceptar sobrescribir.
No hay dependencias nuevas: `package.json` y `package-lock.json` no cambian.

## Probar
    docker compose up -d --build frontend backend
    docker compose exec backend alembic upgrade head          # (Turnos anteriores)
    docker compose exec backend python -m app.scripts.create_admin --email admin@lionfitness.com --name "Admin"

Luego crear usuarios de prueba (como admin, en http://localhost:8000/docs → POST /api/v1/auth/register)
con roles `receptionist` y `trainer`, e iniciar sesión en http://localhost:5173 con cada uno.

## Qué revisar por rol
- Administrador: Nuevo socio · Editar · Dar de baja · Restaurar socio · ficha física (editar/eliminar medidas).
- Recepcionista: Nuevo socio (con consulta de cédula) · Editar. Sin baja ni medidas.
- Entrenador: solo consulta; registra medidas (botón de regla en la fila o en la ficha).

## Consulta de cédula (Fácil Inscripción)
Escribir la cédula y presionar Enter (o «Consultar»). Para probar sin Hacienda real:
`CEDULA_LOOKUP_ENABLED=false` en el backend → la UI muestra "servicio no disponible" y deja registrar a mano.

## Archivos
NUEVOS: types/{members,plans,measurements}.ts · lib/{labels,numbers,query-keys,report-error,form-errors}.ts ·
services/{members,plans,measurements}.service.ts · hooks/{useMembers,usePlans,useMeasurements,useDebounce}.ts ·
features/auth/{permissions,usePermissions}.ts · features/members/** · features/measurements/** ·
components/ui/{dialog,select,textarea,table,alert}.tsx · components/common/{Pagination,ConfirmDialog,SearchInput,Spinner}.tsx ·
pages/members/{MembersPage,MemberDetailPage}.tsx
MODIFICADOS: types/index.ts · lib/{axios,query-client}.ts · utils/index.ts · routes/{index,guards}.tsx ·
features/auth/index.ts · components/layout/{Sidebar,Header}.tsx · layouts/AppLayout.tsx · README.md
