from sqlalchemy.ext.asyncio import AsyncSession
from app.services.collection_service import get_collection
from app.services.agent_service import AgentService


class RAGService:
    def __init__(self):
        self.agent = AgentService()

    async def query(self, db: AsyncSession, user_id: str, query: str, collection_ids: list[str],
                    session_id: str | None = None, options: dict | None = None):
        # Validate access
        for col_id in collection_ids:
            col = await get_collection(db, col_id)
            if not col or col.owner_id != user_id:
                raise PermissionError(f"Collection {col_id} not found or access denied")

        return await self.agent.run(query, collection_ids, session_id, options)


_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
