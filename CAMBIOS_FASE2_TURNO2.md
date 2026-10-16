# SoftGym · Fase 2 · Turno 2 (API de socios, planes y ficha física)

Extraer en la raíz del proyecto (donde están `backend/` y `frontend/`) y aceptar sobrescribir.
Los archivos MODIFICADOS parten de la copia del proyecto que se envió; si hubo ediciones
posteriores en ellos, compare con `git diff` antes de sobrescribir.

## Aplicar
    docker compose exec backend pip install -r requirements.txt     # (rebuild si hace falta)
    docker compose exec backend alembic upgrade head                 # aplica 0004 (unaccent)
    docker compose exec backend python -m app.scripts.create_admin --email ... --name "..."
    docker compose exec backend pytest app/tests -q                  # 223 tests

## Antes de producción (obligatorio)
Definir JWT_SECRET (>= 32 caracteres) en el entorno. Con ENVIRONMENT distinto de
development la app NO arranca con la clave por defecto. Ver backend/.env.example.

## Cambios en código existente de la Fase 1 (y por qué)
- dependencies/auth.py   : token inválido/expirado daba HTTP 500 (decode devolvía None); ahora 401.
- core/security (config) : JWT_SECRET tenía un valor público por defecto y .env.example documentaba
                           otra variable (SECRET_KEY) que nunca se leía.
- repositories/user_repository.py : correos comparados con distinción de mayúsculas; ahora no.
- routers/auth.py        : POST /auth/register solo para administradores.
- schemas/auth.py, services/auth_service.py, core/exceptions.py : mensajes en español.
- tests/test_auth.py     : test_register_missing_fields -> test_register_requires_authentication
                           (cambió por diseño: register ahora exige admin).
- alembic/env.py         : acepta ALEMBIC_DATABASE_URL (BD de pruebas) y no deshabilita loggers.
