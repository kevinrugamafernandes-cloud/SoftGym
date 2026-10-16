# SoftGym — Backend

FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · JWT

---

## Requisitos

- Python 3.12+
- PostgreSQL 16+ (o cuenta en [Supabase](https://supabase.com))

---

## Instalación local

```bash
cd backend

# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno
cp .env.example .env
# Editar .env con tus credenciales reales
```

### Variables de entorno obligatorias

| Variable                      | Descripción                               |
|-------------------------------|-------------------------------------------|
| `DATABASE_URL`                | URL de conexión PostgreSQL                |
| `SECRET_KEY`                  | Clave secreta JWT (mínimo 32 caracteres)  |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del access token (default: 15)   |

---

## Migraciones

```bash
# Aplicar todas las migraciones
alembic upgrade head

# Crear nueva migración (después de cambiar modelos)
alembic revision --autogenerate -m "descripcion del cambio"

# Ver historial
alembic history

# Revertir última migración
alembic downgrade -1
```

---

## Ejecutar el servidor

```bash
# Desarrollo con hot-reload
uvicorn app.main:app --reload --port 8000

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## API Docs

Con `DEBUG=true` en `.env`:
- Swagger UI → http://localhost:8000/docs
- ReDoc → http://localhost:8000/redoc

---

## Endpoints Fase 1

| Método | Ruta               | Auth     | Descripción                      |
|--------|--------------------|----------|----------------------------------|
| GET    | `/api/v1/health`   | No       | Health check del sistema         |
| POST   | `/api/v1/auth/login`    | No  | Login → retorna access token     |
| POST   | `/api/v1/auth/register` | No  | Registrar nuevo usuario          |
| GET    | `/api/v1/auth/me`       | Sí  | Usuario autenticado actual       |

### Ejemplo: login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@lionfitness.com", "password": "tu_password"}'
```

### Ejemplo: endpoint protegido

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

---

## Tests

```bash
pytest app/tests/ -v
```

---

## Arquitectura

```
app/
├── api/v1/routers/   # Endpoints HTTP (auth, health)
├── core/             # config, security, exceptions
├── db/               # engine, session, Base
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic request/response
├── services/         # Business logic
├── repositories/     # Data access layer
├── middleware/        # Error handlers
└── dependencies/     # FastAPI Depends (auth, db)
```

**Patrón:** Router → Service → Repository → Database

Cada capa tiene una responsabilidad única (SRP). Los servicios no conocen
HTTP; los repositorios no conocen lógica de negocio.

---

## Fase 2 — Socios, planes y ficha física

### Primer administrador
`POST /auth/register` ahora **exige un administrador autenticado**. La primera cuenta se crea por consola:

```bash
docker compose exec backend python -m app.scripts.create_admin \
    --email admin@lionfitness.com --name "Administrador Lion"
```

### Variables de entorno nuevas
| Variable | Descripción |
|---|---|
| `JWT_SECRET` | Clave de firma de los JWT. **Obligatoria (≥ 32 caracteres) si `ENVIRONMENT` no es de desarrollo**; la app no arranca con la clave por defecto. |
| `CEDULA_LOOKUP_*` | Consulta de cédula: URL, timeout, reintentos, caché, cortacircuitos y orden del nombre. Ver `.env.example`. |
| `TEST_DATABASE_URL` | BD para pruebas (su nombre debe terminar en `_test`). |

### Endpoints
| Recurso | Rutas | Roles |
|---|---|---|
| Socios | `GET/POST /members`, `GET/PATCH /members/{id}` | lectura: admin, recepcionista, entrenador · escritura: admin, recepcionista |
| Baja lógica | `DELETE /members/{id}`, `POST /members/{id}/restore` | solo admin |
| Fácil Inscripción | `GET /members/cedula-lookup/{cedula}` | admin, recepcionista |
| Ficha física | `GET/POST /members/{id}/measurements`, `GET/PATCH …/{mid}` | admin, recepcionista, entrenador |
| | `DELETE /members/{id}/measurements/{mid}` | solo admin |
| Planes | `GET /plans`, `GET /plans/{id}` | admin, recepcionista |
| | `POST/PATCH/DELETE /plans…` | solo admin |

El rol `member` (socio) no accede a ningún endpoint administrativo.

### Consulta de cédula — qué es y qué no es
La fuente es el **padrón de contribuyentes del Ministerio de Hacienda** (`api.hacienda.go.cr/fe/ae`), no el Registro Civil:
devuelve un único campo `nombre`, **no incluye la fecha de nacimiento** y solo conoce a personas inscritas como contribuyentes.
El nombre se separa en nombre/apellidos de forma aproximada, por eso la respuesta trae `needs_review: true` y el formulario
debe dejar los campos editables. Hacienda bloquea la IP 10 minutos si se superan sus límites, por lo que el cliente usa caché
(positiva y negativa), no reintenta ante 429 y tiene cortacircuitos. Si falla, responde `503` con `code: lookup_unavailable`
y el registro manual sigue disponible.

### Pruebas
```bash
docker compose exec backend pytest app/tests -q
```
Las pruebas de API usan una BD PostgreSQL real (`<nombre>_test`, creada automáticamente en el servidor local/Docker) con
migraciones reales y reversión por test. Contra un host remoto (p. ej. Supabase) se omiten salvo que se defina `TEST_DATABASE_URL`.

---

## Fase 3 · Núcleo financiero (membresías, pagos, caja, morosidad)

### Multi-gimnasio (`gym_id`)
Toda tabla de negocio pertenece a un gimnasio (`gyms`). El gimnasio se toma **de la base de datos según el usuario
autenticado, nunca del token**, y todos los repositorios filtran por él: un gimnasio no ve ni modifica datos de otro.
La migración `0005` crea "Lion Fitness Center" y asigna a él todos los datos existentes.

### Endpoints nuevos
| Recurso | Ruta | Roles |
|---|---|---|
| Cobrar | `POST /payments` | admin, recepcionista |
| Listar / detalle | `GET /payments`, `GET /payments/{id}` | admin, recepcionista |
| Cierre de caja | `GET /payments/cash-summary?date=` | admin, recepcionista |
| Comprobante | `GET /payments/{id}/receipt` (JSON) · `/receipt.pdf` | admin, recepcionista |
| Anular | `POST /payments/{id}/void` | solo admin |
| Historial de membresías | `GET /members/{id}/memberships` | admin, recepcionista |
| Recalcular estados | `POST /system/refresh-statuses` | solo admin |

`GET /members` y `GET /members/{id}` ahora incluyen `membership` con `days_remaining`, `state` y `label`.

### Reglas del cobro (todo en UNA transacción)
- `end_date` es el **último día con acceso**: plan de 30 días pagado el 1/oct cubre del 1 al 30; el 31 ya es atraso.
- Si el socio aún tiene membresía vigente, el nuevo periodo empieza **al día siguiente de su vencimiento** (renovar antes no pierde días).
- Si no pasó nada o ya venció, empieza en la fecha del pago. Un pago con fecha pasada (fichas en papel) es válido.
- SINPE y transferencia **exigen referencia**. Un cobro idéntico (socio, plan y monto) en menos de 60 s se detiene (`possible_duplicate`) salvo `confirm_duplicate`.
- Los pagos **no se borran: se anulan** (motivo obligatorio, solo admin, solo el último pago del socio).
- Comprobantes `R-000001…`, consecutivos y sin saltos por gimnasio, aun con cobros simultáneos.
- "Hoy" es la fecha de la **zona horaria del gimnasio** (en Costa Rica el día de UTC cambia a las 6 p. m.).

### Morosidad
Cada cobro/anulación recalcula al instante el estado del socio. Además, **programar una vez al día**:

    5 0 * * *  cd /ruta/softgym && docker compose exec -T backend python -m app.jobs.refresh_statuses

Es idempotente. No toca a socios `inactivos`, dados de baja ni sin membresías. Ajustes: `MEMBERSHIP_EXPIRING_DAYS` (aviso, def. 5) y `MEMBERSHIP_GRACE_DAYS` (gracia, def. 0).

## Fase 3 · Turno 4 — Sesiones de caja y punto de venta (tienda)

### Sesiones de caja
Cada cajero **abre** su turno con un fondo inicial y lo **cierra** contando el efectivo. Todo cobro de
membresía y toda venta de la tienda quedan ligados a la caja abierta de quien los registra. Al cerrar se
guarda una instantánea inmutable: efectivo esperado (fondo + efectivo cobrado), contado y diferencia
(+ sobrante / − faltante). Si hay diferencia, las observaciones son obligatorias.

- Un cajero no puede tener dos cajas abiertas (índice único parcial en la BD).
- Cobro y cierre simultáneos se serializan (bloqueo de la fila de la sesión): nada entra a una caja cerrada.
- `CASH_SESSION_REQUIRED=true` (por defecto): sin caja abierta no se cobran membresías. Las ventas la exigen siempre.

| Método | Ruta | Rol |
|---|---|---|
| GET | `/api/v1/cash-sessions/current` | admin, recepcionista |
| POST | `/api/v1/cash-sessions/open` | admin, recepcionista |
| POST | `/api/v1/cash-sessions/{id}/close` | el cajero dueño o un admin |
| GET | `/api/v1/cash-sessions` · `/{id}` | recepcionista: solo las suyas; admin: todas |

### Productos, inventario y ventas
- `price` es el precio FINAL con IVA incluido (tarifas 13/4/2/1/0 %). Cada línea de venta guarda base,
  IVA y una instantánea del producto (nombre, CABYS, precio, tarifa): lista para el libro de ventas y la factura 4.4.
- El stock solo cambia por movimientos auditados (`inventory_movements`): inicial, entrada, venta, anulación, ajuste.
- La venta descuenta el stock de forma ATÓMICA: bloquea los productos en orden de id, verifica, descuenta y
  registra todo en una transacción; la BD impide stock negativo (CHECK). Probado con 12 compradores
  simultáneos sobre 6 unidades.
- Consecutivo de ventas por gimnasio (`V-000001`) en `document_sequences`.

| Método | Ruta | Rol |
|---|---|---|
| GET | `/api/v1/products` · `/categories` · `/{id}` · `/{id}/movements` | admin, recepcionista |
| POST/PATCH | `/api/v1/products` · `/{id}` · `/{id}/stock` | admin |
| POST | `/api/v1/sales` | admin, recepcionista (con caja abierta) |
| GET | `/api/v1/sales` · `/{id}` · `/{id}/ticket.pdf` · `/{id}/whatsapp` | admin, recepcionista |
| POST | `/api/v1/sales/{id}/void` | admin (devuelve el stock) |
| GET | `/api/v1/payments/{id}/whatsapp` | admin, recepcionista |

`GET /payments/cash-summary` ahora suma cobros + ventas (campos `payments_*` y `sales_*` para separarlos).

### WhatsApp
Enlaces «clic para chatear» (`https://wa.me/<número>?text=<mensaje>`), sin API de Meta ni costos: el backend
arma el mensaje y el número (8 dígitos → prefijo `WHATSAPP_DEFAULT_COUNTRY_CODE`, por defecto 506) y la
recepcionista lo envía desde su WhatsApp Web o app.

## Fase 3 · Turno 5 — Configuración, inscripción con cobro, morosos y contabilidad

### Reglas nuevas
- **Ningún socio queda activo sin pago.** `POST /members/enroll` registra socio + primer cobro en una sola
  transacción (si el cobro falla, el socio no se crea). `POST /members` (alta sin cobro, uso administrativo)
  deja al socio **inactivo** hasta su primer pago. Activarlo a mano exige una membresía (`membership_required`),
  y si se anula su único pago vuelve a inactivo.
- **IVA en membresías:** cada plan tiene `tax_rate` (13 % por defecto, precio con IVA incluido) y cada pago
  guarda la tarifa vigente al cobrar (`payments.tax_rate`). `PaymentOut` expone `subtotal` y `tax_amount`.
- **Cierre mensual:** al cerrar un mes se guarda la instantánea de sus totales y el periodo queda bloqueado
  (`period_closed`): no se registran cobros con fecha de ese mes ni se anulan sus cobros o ventas. Solo se
  puede cerrar un mes terminado y sin cajas abiertas de ese periodo.

### Planes oficiales (migración 0007)
Pase de Día ₡2 000 (1 día) · Quincena ₡13 000 (15 días) · Mensualidad ₡20 000 (30 días), activos y con IVA 13 %
incluido. Si ya existía un plan equivalente ("Mensual", "Pase diario", "Quincenal"…) se actualiza en vez de duplicarse.

### Endpoints
| Método | Ruta | Rol |
|---|---|---|
| GET / PATCH | `/api/v1/settings` | ver: personal · editar: admin |
| POST | `/api/v1/members/enroll` | admin, recepcionista (con caja abierta) |
| GET | `/api/v1/collections?state=vencida\|por_vencer` | admin, recepcionista |
| POST | `/api/v1/collections/{member_id}/reminders` | admin, recepcionista |
| GET | `/api/v1/dashboard` | admin, recepcionista |
| GET | `/api/v1/reports/sales-book` · `/sales-book.csv` | admin |
| GET | `/api/v1/reports/monthly` · `/monthly.pdf` | admin |
| GET / POST | `/api/v1/reports/monthly-closes` | admin |

Mensajes de WhatsApp personalizables con `{nombre}`, `{gimnasio}`, `{plan}`, `{fecha_vencimiento}`, `{dias}`, `{telefono}`.

### Asistencia
El módulo de asistencia está oculto en la interfaz. Nota: aún no existe en el backend (no hay tablas ni
endpoints de asistencia); queda para una fase futura.
