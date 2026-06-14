from sqlalchemy import select
from app.domain.collection import Collection


async def create_collection(db, owner_id, name, description=None):
    col = Collection(owner_id=owner_id, name=name, description=description)
    db.add(col)
    await db.flush()
    return col


async def list_collections(db, owner_id):
    r = await db.execute(
        select(Collection).where(
            Collection.owner_id == owner_id,
            Collection.status.notin_(["deleted", "archived"]),
        )
    )
    return r.scalars().all()


async def get_collection(db, col_id):
    return await db.get(Collection, col_id)


async def delete_collection(db, col_id):
    col = await db.get(Collection, col_id)
    if col:
        col.status = "archived"
        await db.flush()
