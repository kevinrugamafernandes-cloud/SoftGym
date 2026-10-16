# SoftGym — Frontend

React 18 · TypeScript · Vite · TailwindCSS · Shadcn/UI · TanStack Query

---

## Requisitos

- Node.js 20+
- npm 10+

---

## Instalación local

```bash
cd frontend

# Instalar dependencias
npm install

# Variables de entorno
cp .env.example .env
# Editar VITE_API_URL si el backend no corre en localhost:8000
```

---

## Comandos

```bash
# Desarrollo con hot-reload
npm run dev

# Type checking
npm run type-check

# Build de producción
npm run build

# Preview del build
npm run preview

# Lint
npm run lint
```

Servidor de desarrollo: http://localhost:5173

---

## Estructura de carpetas

```
src/
├── app/              # App root, providers
├── assets/           # Imágenes, íconos estáticos
├── components/
│   ├── ui/           # Shadcn/UI + componentes base
│   └── layout/       # Sidebar, Header
├── features/
│   └── auth/         # AuthContext, useAuth hook
├── hooks/            # useToast y hooks reutilizables
├── layouts/          # AppLayout (wrapper de páginas protegidas)
├── lib/              # axios instance, queryClient
├── pages/            # Una carpeta por sección/módulo
├── routes/           # AppRouter, ProtectedRoute, PublicRoute
├── services/         # Llamadas a la API por dominio
├── styles/           # globals.css, tokens
├── types/            # Interfaces TypeScript globales
└── utils/            # cn(), formatDate(), getInitials()
```

---

## Rutas

| Ruta         | Auth | Descripción                          |
|--------------|------|--------------------------------------|
| `/login`     | No   | Página de login                      |
| `/dashboard` | Sí   | Dashboard principal (placeholder)    |
| `*`          | —    | Página 404                           |

Las rutas de Fase 2+ (`/members`, `/payments`, etc.) están reservadas
en el router y se activarán conforme avance el desarrollo.

---

## Design System

Paleta de colores SoftGym (Lion Fitness Center):

| Token      | Valor     | Uso                     |
|------------|-----------|-------------------------|
| gold       | `#C8B68A` | Primario, CTAs          |
| gold-dark  | `#A39165` | Hover de primario       |
| background | `#0F1115` | Fondo de la app         |
| card       | `#1A1D24` | Superficies, sidebar    |
| foreground | `#FFFFFF` | Texto principal         |
| muted      | `#A8A8A8` | Texto secundario        |

Fuente: **Inter** (Google Fonts)
Inspiración visual: Stripe Dashboard · Vercel · Linear

---

## Agregar componentes Shadcn/UI

```bash
npx shadcn-ui@latest add <component-name>
# Ejemplo:
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add select
npx shadcn-ui@latest add table
```

---

## Estado global

- **Auth**: `AuthContext` + `useAuth()` — usuario autenticado, login/logout
- **Server state**: TanStack Query — cache, re-fetch, loading/error states
- **Forms**: React Hook Form + Zod — validación tipada en cliente

---

## Fase 2 · Módulo de Socios

### Rutas nuevas
| Ruta | Descripción | Roles |
|---|---|---|
| `/members` | Listado paginado, búsqueda y filtro por estado | admin, recepcionista, entrenador |
| `/members/:memberId` | Ficha del socio y ficha física (medidas e IMC) | admin, recepcionista*, entrenador |

\* La recepcionista ve los datos del socio; la ficha física es para admin y entrenador (ver `features/auth/permissions.ts`).

### Permisos en la interfaz
Toda la matriz vive en **`src/features/auth/permissions.ts`**; los componentes preguntan `can("members.edit")` con `usePermissions()`.
El backend siempre valida de nuevo (403), esto solo decide qué botones se muestran.

### Capa de datos
`services/*.service.ts` (Axios) → `hooks/useMembers|usePlans|useMeasurements.ts` (React Query) → componentes.
- Errores: `lib/query-client.ts` muestra un Toast global con el `detail` del backend (en español); las mutaciones son
  `silent` porque cada formulario muestra el error en línea **y** con Toast (`lib/report-error.ts`).
- Claves de caché: `lib/query-keys.ts`.

### Convenciones que se deben mantener
- Formularios: `<form onSubmit={handleSubmit(onSubmit)}>` + botón `type="submit"` (ENTER envía).
- Toda la interfaz, validaciones Zod y Toasts en español.
- El IMC y su clasificación **nunca** se calculan en el cliente: vienen del servidor.
- No modificar la guarda del interceptor 401 de `lib/axios.ts`.
