from sqlalchemy import select
from app.domain.document import Document


async def list_documents(db, collection_id):
    r = await db.execute(
        select(Document).where(Document.collection_id == collection_id)
    )
    return r.scalars().all()


async def get_document(db, doc_id):
    return await db.get(Document, doc_id)


async def delete_document(db, doc_id):
    doc = await db.get(Document, doc_id)
    if doc:
        await db.delete(doc)
        await db.flush()
