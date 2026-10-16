"""
Inscripción con cobro obligatorio: el socio y su primer pago se registran juntos o no se
registra nada. Así recepción nunca deja perfiles activos sin membresía ni pago.
"""
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.exceptions import ConflictException
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut
from app.schemas.member import MemberOut
from app.schemas.payment import PaymentCreate
from app.services.member_service import MemberService
from app.services.payment_service import PaymentService


class EnrollmentService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._members = MemberService(db, gym_id, clock)
        self._payments = PaymentService(db, gym_id, clock)

    def enroll(self, data: EnrollmentCreate, user: User) -> EnrollmentOut:
        try:
            member = self._members.add_in_transaction(data.member)
            p = data.payment
            payment = self._payments.register_in_transaction(
                PaymentCreate(
                    member_id=member.id, plan_id=p.plan_id, amount=p.amount, method=p.method,
                    reference=p.reference, notes=p.notes, confirm_duplicate=True,   # socio nuevo: no hay duplicado posible
                ),
                user,
            )
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ConflictException(
                f"Ya existe un socio registrado con la cédula {data.member.identification}", code="member_exists"
            )
        except Exception:
            self._db.rollback()   # todo o nada: ni socio, ni membresía, ni comprobante
            raise
        return EnrollmentOut(
            member=MemberOut.model_validate(self._members.get(member.id)),
            payment=self._payments.get(payment.id),
        )
