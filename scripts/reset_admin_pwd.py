"""Reset admin password hash to fix bcrypt compatibility issue."""
import asyncio
from app.core.security import hash_password
from app.core.di import get_db
from app.domain.user import User
from sqlalchemy import select, update


async def reset():
    async for db in get_db():
        result = await db.execute(select(User).where(User.username == "admin"))
        u = result.scalar_one_or_none()
        new_hash = hash_password("admin")
        print(f"Old hash: {u.password_hash[:30]}...")
        print(f"New hash: {new_hash[:30]}...")
        await db.execute(
            update(User).where(User.id == u.id).values(password_hash=new_hash)
        )
        await db.commit()
        print("Password reset OK.")
        break


if __name__ == "__main__":
    asyncio.run(reset())