"""
Registro central de todos los modelos SQLAlchemy (alembic/env.py los detecta desde aquí).
"""
from app.models.enums import Gender, MemberStatus  # noqa: F401
from app.models.gym import Gym                      # noqa: F401
from app.models.user import User, UserRole          # noqa: F401
from app.models.plan import Plan                    # noqa: F401
from app.models.member import Member                # noqa: F401
from app.models.membership import Membership, MembershipStatus  # noqa: F401
from app.models.payment import Payment, PaymentMethod           # noqa: F401
from app.models.receipt_sequence import ReceiptSequence         # noqa: F401
from app.models.body_measurement import BodyMeasurement         # noqa: F401
from app.models.cash_session import CashSession, CashSessionStatus  # noqa: F401
from app.models.product import InventoryMovement, MovementKind, Product  # noqa: F401
from app.models.sale import Sale, SaleItem                      # noqa: F401
from app.models.document_sequence import DocumentSequence       # noqa: F401
from app.models.monthly_close import MonthlyClose               # noqa: F401
from app.models.member_reminder import MemberReminder           # noqa: F401

__all__ = [
    "Gender", "MemberStatus", "MembershipStatus", "PaymentMethod", "UserRole",
    "Gym", "User", "Plan", "Member", "Membership", "Payment", "ReceiptSequence", "BodyMeasurement",
    "CashSession", "CashSessionStatus", "Product", "InventoryMovement", "MovementKind", "Sale", "SaleItem",
    "DocumentSequence", "MonthlyClose", "MemberReminder",
]
