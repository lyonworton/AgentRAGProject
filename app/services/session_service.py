from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.session import Session
from app.domain.message import Message
from app.memory.conversation import ConversationMemory


async def create_session(
    db: AsyncSession, user_id: str, collection_id: str | None = None, title: str | None = None
) -> Session:
    session = Session(
        user_id=user_id,
        collection_id=collection_id,
        title=title,
        last_activity_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    return session


async def get_session(db: AsyncSession, session_id: str, user_id: str) -> Session | None:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_session(db: AsyncSession, session_id: str, user_id: str) -> bool:
    session = await get_session(db, session_id, user_id)
    if not session:
        return False
    session.is_active = False
    await db.flush()
    return True


async def get_history(
    db: AsyncSession, session_id: str, user_id: str, limit: int = 50
) -> list[Message]:
    session = await get_session(db, session_id, user_id)
    if not session:
        return []
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def add_message(
    db: AsyncSession, session_id: str, role: str, content: str,
    trace_id: str | None = None, citations: dict | None = None,
    thoughts: list[dict] | None = None, token_count: int | None = None,
) -> Message:
    msg = Message(
        session_id=session_id, role=role, content=content,
        trace_id=trace_id, citations=citations, thoughts=thoughts,
        token_count=token_count,
    )
    db.add(msg)
    await db.flush()

    session = await db.get(Session, session_id)
    if session:
        session.message_count = (session.message_count or 0) + 1
        session.last_activity_at = datetime.now(timezone.utc)
        await db.flush()

    return msg


async def list_sessions(db: AsyncSession, user_id: str, limit: int = 50) -> list[Session]:
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id, Session.is_active == True)
        .order_by(Session.last_activity_at.desc().nullslast())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_session_context(
    memory: ConversationMemory, session_id: str,
    summary: str | None = None, topic: str | None = None,
) -> None:
    if summary:
        await memory.save_summary(session_id, summary)
    if topic:
        await memory.save_topic(session_id, topic)