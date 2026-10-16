"""
Recalcula el estado de los socios (activo / por vencer / moroso) para TODOS los gimnasios.

Programar UNA vez al día, poco después de medianoche hora de Costa Rica, por ejemplo con cron:

    5 0 * * *  cd /ruta/softgym && docker compose exec -T backend python -m app.jobs.refresh_statuses

Es idempotente: ejecutarlo varias veces el mismo día no cambia nada la segunda vez.
Aun sin este trabajo, cada cobro o anulación recalcula al instante el estado de ese socio.
"""
import logging
import sys

from app.core.clock import Clock
from app.db.session import SessionLocal
from app.services.status_refresh_service import StatusRefreshService

logger = logging.getLogger("softgym.jobs.refresh_statuses")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    with SessionLocal() as db:
        results = StatusRefreshService(db, Clock()).refresh_all()
    for r in results:
        logger.info("gimnasio %s: %d membresías vencidas, %d socios actualizados", r.gym_id, r.memberships_expired, r.members_updated)
    print(f"OK: {sum(r.members_updated for r in results)} socios actualizados en {len(results)} gimnasio(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
