import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import MemberStatus
from app.models.member import Member
from app.schemas.member import normalize_identification


def _escape_like(value: str) -> str:
    """Escapa %, _ y \\ para que el texto del usuario se busque literalmente."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class MemberRepository:
    """Acceso a datos de Member. No hace commit: lo hace el servicio."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def get(self, member_id: uuid.UUID, *, include_deleted: bool = False) -> Optional[Member]:
        member = self._db.get(Member, member_id)
        # Un socio de OTRO gimnasio se trata exactamente como inexistente (sin filtrar su existencia).
        if member is None or member.gym_id != self._gym_id or (member.is_deleted and not include_deleted):
            return None
        return member

    def get_for_update(self, member_id: uuid.UUID, *, include_deleted: bool = False) -> Optional[Member]:
        """Igual que get(), pero BLOQUEA la fila hasta el commit: serializa los cobros de un mismo socio."""
        member = self._db.execute(
            select(Member).where(Member.id == member_id, Member.gym_id == self._gym_id).with_for_update()
        ).scalar_one_or_none()
        if member is None or (member.is_deleted and not include_deleted):
            return None
        return member

    def get_by_identification(
        self, identification: str, *, include_deleted: bool = False
    ) -> Optional[Member]:
        stmt = select(Member).where(Member.gym_id == self._gym_id, Member.identification == identification)
        if not include_deleted:
            stmt = stmt.where(Member.is_deleted.is_(False))
        return self._db.scalars(stmt).first()

    def search(
        self,
        *,
        search: Optional[str],
        status: Optional[MemberStatus],
        page: int,
        size: int,
    ) -> Tuple[List[Member], int]:
        """
        Listado paginado. `search` divide el texto en palabras y exige que CADA una
        coincida (sin distinguir mayúsculas ni tildes) con nombre, apellidos o cédula:
        "ana mora" encuentra a "Ana María Mora"; "1-1234" encuentra por cédula.
        """
        stmt = select(Member).where(Member.gym_id == self._gym_id, Member.is_deleted.is_(False))
        if status is not None:
            stmt = stmt.where(Member.status == status)

        for token in (search or "").split():
            like = f"%{_escape_like(token)}%"
            ident_like = f"%{_escape_like(normalize_identification(token))}%"
            stmt = stmt.where(
                or_(
                    func.unaccent(Member.first_name).ilike(func.unaccent(like), escape="\\"),
                    func.unaccent(Member.last_name).ilike(func.unaccent(like), escape="\\"),
                    Member.identification.ilike(ident_like, escape="\\"),
                )
            )

        total = self._db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self._db.scalars(
            stmt.order_by(Member.last_name, Member.first_name, Member.id)
            .offset((page - 1) * size)
            .limit(size)
        ).all()
        return list(items), total

    def add(self, member: Member) -> Member:
        self._db.add(member)
        self._db.flush()
        return member

    def flush(self) -> None:
        self._db.flush()
