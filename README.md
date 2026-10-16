# SoftGym — Lion Fitness Center

> Plataforma de gestión administrativa para gimnasios. Fase 1 — Infraestructura base.

## Stack

| Capa       | Tecnología                                         |
|------------|----------------------------------------------------|
| Frontend   | React 18 · TypeScript · Vite · TailwindCSS · Shadcn/UI |
| Backend    | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic     |
| Base datos | PostgreSQL 16 · Supabase (producción)              |
| Auth       | JWT (access token 15 min)                          |
| Deploy     | Vercel (frontend) · Railway/Render (backend)       |

---

## Inicio rápido — Docker (recomendado)

```bash
# 1. Clonar y entrar al proyecto
git clone <repo-url> softgym
cd softgym

# 2. Variables de entorno
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. Levantar todos los servicios
docker compose up --build

# 4. Ejecutar migraciones (primera vez)
docker compose exec backend alembic upgrade head
```

Servicios disponibles:
- **Frontend** → http://localhost:5173
- **Backend API** → http://localhost:8000
- **API Docs** → http://localhost:8000/docs
- **PostgreSQL** → localhost:5432

---

## Inicio manual (sin Docker)

Ver `backend/README.md` y `frontend/README.md` para instrucciones detalladas.

---

## Estructura del repositorio

```
softgym/
├── backend/          # FastAPI + SQLAlchemy
├── frontend/         # React + Vite + TailwindCSS
├── docker-compose.yml
└── README.md
```

---

## Roles del sistema

| Rol           | Permisos                                              |
|---------------|-------------------------------------------------------|
| admin         | Acceso completo, configuración, reportes              |
| receptionist  | Registrar clientes, pagos y asistencia                |

---

## Roadmap

| Fase | Contenido                                    | Estado     |
|------|----------------------------------------------|------------|
| 1    | Infraestructura, auth, layout, design system | ✅ Completa |
| 2    | Miembros, membresías, pagos                  | ⏳ Pendiente|
| 3    | Asistencia, morosidad, alertas               | ⏳ Pendiente|
| 4    | Dashboard métricas, reportes PDF/Excel       | ⏳ Pendiente|
| 5    | QA, optimización, deploy producción          | ⏳ Pendiente|
