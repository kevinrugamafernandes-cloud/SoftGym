import math
import re
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.exceptions import BusinessRuleException, ConflictException, NotFoundException
from app.models.enums import MemberStatus
from app.models.member import Member
from app.repositories.member_repository import MemberRepository
from app.schemas.member import (
    CedulaLookupOut,
    MemberCreate,
    MemberListOut,
    MemberOut,
    MemberUpdate,
    normalize_identification,
)
from app.services.cedula_lookup_service import CedulaLookupService
from app.core.config import settings
from app.repositories.membership_repository import MembershipRepository
from app.services.membership_service import MembershipService
from app.services.membership_status import member_status_for

# "moroso" y "por_vencer" los calcula el sistema a partir de la vigencia de la
# membresía (tarea programada de la Fase 3); el personal solo puede alternar
# entre activo e inactivo a mano.
_MANUAL_STATUSES = {MemberStatus.ACTIVE, MemberStatus.INACTIVE}


class MemberService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock | None = None) -> None:
        self._db = db
        self._gym_id = gym_id
        self._repo = MemberRepository(db, gym_id)
        self._memberships = MembershipService(db, gym_id, clock or Clock())

    def _latest_membership(self, member_id: uuid.UUID):
        return MembershipRepository(self._db, self._gym_id).latest_for_member(member_id)

    def _decorate(self, members: list[Member]) -> list[Member]:
        """Adjunta `member.membership` (resumen con días restantes) con UNA consulta para toda la página."""
        summaries = self._memberships.summaries_for([m.id for m in members])
        for m in members:
            m.membership = summaries.get(m.id)  # type: ignore[attr-defined]
        return members

    # ── Consultas ─────────────────────────────────────────────────────────────
    def list(
        self, *, search: Optional[str], status: Optional[MemberStatus], page: int, size: int
    ) -> MemberListOut:
        items, total = self._repo.search(search=search, status=status, page=page, size=size)
        self._decorate(items)
        return MemberListOut(
            items=[MemberOut.model_validate(m) for m in items],
            total=total,
            page=page,
            size=size,
            pages=math.ceil(total / size) if total else 0,
        )

    def get(self, member_id: uuid.UUID) -> Member:
        member = self._repo.get(member_id)
        if member is None:
            raise NotFoundException("Socio", code="member_not_found")
        return self._decorate([member])[0]

    # ── Altas ─────────────────────────────────────────────────────────────────
    def create(self, data: MemberCreate) -> Member:
        """
        Alta SIN cobro: el socio nace INACTIVO ("sin membresía") y se activa con su primer pago.
        Así nunca queda un perfil activo sin membresía ni pago. Para inscribir y cobrar en un solo
        paso (lo normal en recepción) use EnrollmentService (POST /members/enroll).
        """
        try:
            member = self.add_in_transaction(data)
            self._db.commit()
        except IntegrityError:
            # Carrera: otra petición insertó la misma cédula entre la consulta y el INSERT.
            self._db.rollback()
            raise ConflictException(
                f"Ya existe un socio registrado con la cédula {data.identification}",
                code="member_exists",
            )
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(member)
        return self._decorate([member])[0]

    def add_in_transaction(self, data: MemberCreate) -> Member:
        """Valida y agrega el socio SIN commit (lo usa la inscripción con cobro)."""
        existing = self._repo.get_by_identification(data.identification, include_deleted=True)
        if existing is not None:
            if existing.is_deleted:
                raise ConflictException(
                    "Existe un socio dado de baja con esa cédula. "
                    "Pida a un administrador que lo restaure en lugar de crear uno nuevo.",
                    code="member_deleted",
                )
            raise ConflictException(
                f"Ya existe un socio registrado con la cédula {data.identification}",
                code="member_exists",
            )
        member = Member(
            gym_id=self._gym_id,
            **data.model_dump(exclude={"joined_at"}),
            status=MemberStatus.INACTIVE,
            # Hoy en la zona horaria del GIMNASIO (date.today() es la fecha del servidor, en UTC).
            joined_at=data.joined_at or self._memberships.today,
        )
        self._repo.add(member)
        return member

    # ── Edición ───────────────────────────────────────────────────────────────
    def update(self, member_id: uuid.UUID, data: MemberUpdate) -> Member:
        member = self.get(member_id)
        changes = data.model_dump(exclude_unset=True)

        new_status = changes.get("status")
        if new_status is not None and new_status not in _MANUAL_STATUSES:
            raise BusinessRuleException(
                f"El estado '{new_status.value}' lo calcula el sistema automáticamente; "
                "solo se puede cambiar manualmente entre 'activo' e 'inactivo'",
                code="status_not_manual",
            )

        if new_status == MemberStatus.ACTIVE and member.status != MemberStatus.ACTIVE:
            # Activar a mano solo tiene sentido si hay una membresía: el estado real lo da su vencimiento.
            latest = self._latest_membership(member.id)
            if latest is None:
                raise BusinessRuleException(
                    "El socio no tiene membresía: registre un cobro para activarlo",
                    code="membership_required",
                )
            changes["status"] = member_status_for(
                latest.end_date, self._memberships.today,
                settings.MEMBERSHIP_EXPIRING_DAYS, settings.MEMBERSHIP_GRACE_DAYS,
            )

        for field, value in changes.items():
            setattr(member, field, value)
        self._db.commit()
        self._db.refresh(member)
        return self._decorate([member])[0]

    # ── Baja lógica y restauración (solo administradores, ver router) ─────────
    def delete(self, member_id: uuid.UUID) -> None:
        """Baja lógica: conserva el historial de pagos y mediciones."""
        member = self.get(member_id)
        member.is_deleted = True
        member.status = MemberStatus.INACTIVE
        self._db.commit()

    def restore(self, member_id: uuid.UUID) -> Member:
        member = self._repo.get(member_id, include_deleted=True)
        if member is None:
            raise NotFoundException("Socio", code="member_not_found")
        if not member.is_deleted:
            raise ConflictException("El socio no está dado de baja", code="member_not_deleted")
        member.is_deleted = False  # queda 'inactivo': el personal lo reactiva explícitamente
        self._db.commit()
        self._db.refresh(member)
        return self._decorate([member])[0]

    # ── Fácil Inscripción ─────────────────────────────────────────────────────
    def lookup_by_identification(
        self, identification: str, lookup: CedulaLookupService
    ) -> CedulaLookupOut:
        """
        1) valida el formato  2) si ya es socio, lo indica SIN consultar a Hacienda
        3) si no, consulta el servicio externo (con caché y cortacircuitos).
        """
        ident = normalize_identification(identification)
        if not re.fullmatch(r"\d{9,12}", ident):
            raise BusinessRuleException(
                "La consulta automática requiere una cédula o DIMEX de 9 a 12 dígitos, solo números",
                code="invalid_identification",
            )

        existing = self._repo.get_by_identification(ident, include_deleted=True)
        if existing is not None:
            return CedulaLookupOut(
                identification=ident,
                full_name=existing.full_name,
                first_name=existing.first_name,
                last_name=existing.last_name,
                birth_date=existing.birth_date,
                source="local",
                needs_review=False,
                already_registered=True,
                existing_member_id=existing.id,
                existing_member_deleted=existing.is_deleted,
            )

        result = lookup.lookup(ident)
        if result.identification_type == "juridica":
            raise BusinessRuleException(
                "La cédula corresponde a una persona jurídica (empresa); "
                "un socio debe ser una persona física",
                code="lookup_legal_entity",
            )
        return CedulaLookupOut(
            identification=ident,
            full_name=result.full_name,
            first_name=result.first_name,
            last_name=result.last_name,
            identification_type=result.identification_type,
            source="hacienda",
            needs_review=True,
        )
