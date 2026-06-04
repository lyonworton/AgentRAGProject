import json
from app.memory.base import BaseMemoryStore

DEFAULT_TTL = 86400  # 24h


class ConversationMemory(BaseMemoryStore):
    """Short-term memory backed by Redis. Manages session-level conversation state."""

    def __init__(self, redis):
        self.redis = redis

    async def asave(self, key: str, data: dict, ttl: int | None = None) -> None:
        await self.redis.set(key, json.dumps(data, default=str), ex=ttl or DEFAULT_TTL)

    async def aload(self, key: str) -> dict | None:
        raw = await self.redis.get(key)
        return json.loads(raw) if raw else None

    async def adelete(self, key: str) -> None:
        await self.redis.delete(key)

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
        results = [await self.aload(k) for k in keys]
        summary, topic, facts, window = results
        return {
            "summary": (summary or {}).get("text", ""),
            "topic": (topic or {}).get("text", ""),
            "facts": (facts or {}).get("items", []),
            "window": (window or {}).get("messages", []),
        }