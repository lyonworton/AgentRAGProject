import asyncio
import json
import structlog
from app.memory.base import BaseMemoryStore

DEFAULT_TTL = 86400  # 24h
logger = structlog.get_logger()


class ConversationMemory(BaseMemoryStore):
    """Short-term memory backed by Redis. Manages session-level conversation state."""

    def __init__(self, redis):
        self.redis = redis

    async def asave(self, key: str, data: dict, ttl: int | None = None) -> None:
        try:
            await self.redis.set(key, json.dumps(data, default=str), ex=ttl or DEFAULT_TTL)
        except Exception:
            logger.warning("memory.redis_save_failed", key=key, exc_info=True)

    async def aload(self, key: str) -> dict | None:
        try:
            raw = await self.redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            logger.warning("memory.redis_load_failed", key=key, exc_info=True)
            return None

    async def adelete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except Exception:
            logger.warning("memory.redis_delete_failed", key=key, exc_info=True)

    # ── Convenience methods ──────────────────────────────────────

    async def save_summary(self, session_id: str, summary: str) -> None:
        await self.asave(f"session:{session_id}:summary", {"text": summary})

    async def save_topic(self, session_id: str, topic: str) -> None:
        await self.asave(f"session:{session_id}:topic", {"text": topic})

    async def save_facts(self, session_id: str, facts: list[str]) -> None:
        await self.asave(f"session:{session_id}:facts", {"items": facts})

    async def save_window(self, session_id: str, messages: list[dict]) -> None:
        await self.asave(f"session:{session_id}:window", {"messages": messages[-10:]})

    async def get_context(self, session_id: str) -> dict:
        keys = [f"session:{session_id}:{suffix}" for suffix in ("summary", "topic", "facts", "window")]
        try:
            results = await asyncio.gather(*[self.aload(k) for k in keys])
        except Exception:
            logger.warning("memory.get_context_failed", session_id=session_id, exc_info=True)
            return {"summary": "", "topic": "", "facts": [], "window": []}
        summary, topic, facts, window = results
        return {
            "summary": (summary or {}).get("text", ""),
            "topic": (topic or {}).get("text", ""),
            "facts": (facts or {}).get("items", []),
            "window": (window or {}).get("messages", []),
        }