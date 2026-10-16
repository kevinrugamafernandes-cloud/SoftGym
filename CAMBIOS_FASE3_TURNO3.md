# SoftGym · Fase 3 · Turno 3 (backend: núcleo financiero)

Extraer en la raíz del proyecto (donde están `backend/` y `frontend/`) y aceptar sobrescribir.
Los archivos MODIFICADOS parten de la copia con los Turnos 1 y 2; si los editó después, compare antes de sobrescribir.

## Aplicar  (¡en este orden!)
    # 1) RESPALDAR LA BASE DE DATOS (la migración 0005 modifica tablas con datos)
    # 2) reconstruir la imagen: hay dependencias nuevas (reportlab, tzdata)
    docker compose build backend && docker compose up -d backend
    docker compose exec backend alembic upgrade head          # aplica 0005
    docker compose exec backend pytest app/tests -q           # 324 pruebas
    # 3) programar el trabajo diario de morosidad (ver backend/README.md)

## Cambios en código existente (y por qué)
- Todos los modelos de negocio llevan gym_id; repositorios y servicios filtran por el gimnasio del usuario.
- POST /auth/register: la cuenta nueva nace en el gimnasio del admin que la crea. `UserOut` incluye gym_id.
- scripts/create_admin.py: crea el admin en el gimnasio por defecto.
- Socio nuevo: la fecha de ingreso por defecto es la del GIMNASIO (antes: la del servidor, en UTC).
- MemberOut incluye `membership` (días restantes). Es un campo nuevo: el frontend actual lo ignora sin problema.
- payments.membership_id: FK de CASCADE a RESTRICT (un pago nunca se borra en cascada).
- requirements.txt: reportlab y tzdata.
