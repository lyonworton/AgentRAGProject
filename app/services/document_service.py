from sqlalchemy import select
from app.domain.document import Document
from app.domain.collection import Collection


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
        # Decrement collection stats before deleting
        if doc.collection_id and doc.chunk_count and doc.status not in ("processing",):
            col = await db.get(Collection, doc.collection_id)
            if col:
                col.doc_count = max(0, (col.doc_count or 0) - 1)
                col.chunk_count = max(0, (col.chunk_count or 0) - doc.chunk_count)
                await db.flush()
        await db.delete(doc)
        await db.flush()
