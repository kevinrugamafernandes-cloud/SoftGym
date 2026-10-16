import uuid

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.document_sequence import DocumentSequence


def next_document_number(db: Session, gym_id: uuid.UUID, doc_type: str) -> int:
    """
    Siguiente consecutivo del gimnasio para `doc_type`, sin saltos: UPDATE … RETURNING bloquea
    la fila del contador hasta el commit (dos ventas simultáneas se serializan) y, si la venta
    se revierte, el número también.
    """
    db.execute(
        pg_insert(DocumentSequence).values(gym_id=gym_id, doc_type=doc_type, last_number=0).on_conflict_do_nothing()
    )
    return db.execute(
        update(DocumentSequence)
        .where(DocumentSequence.gym_id == gym_id, DocumentSequence.doc_type == doc_type)
        .values(last_number=DocumentSequence.last_number + 1)
        .returning(DocumentSequence.last_number)
    ).scalar_one()
