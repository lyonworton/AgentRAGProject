"""Xinference GPU embedding adapter via OpenAI-compatible API."""

import asyncio
import structlog
from openai import APITimeoutError, AsyncOpenAI
from app.adapters.embedding.base import BaseEmbedding

logger = structlog.get_logger()


class XinferenceEmbedding(BaseEmbedding):
    """Xinference OpenAI-compatible embedding adapter (GPU-accelerated)."""

    def __init__(self, endpoint: str, model: str):
        self.client = AsyncOpenAI(
            base_url=f"{endpoint}/v1",
            api_key="xst-token",
            timeout=30.0,
        )
        self.model = model

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(input=texts, model=self.model)
        return [d.embedding for d in resp.data]

    async def aembed_query(self, query: str) -> list[float]:
        resp = await self.client.embeddings.create(input=[query], model=self.model)
        return resp.data[0].embedding

    async def warmup(self) -> bool:
        """Verify connectivity to Xinference service."""
        try:
            await asyncio.wait_for(
                self.aembed_query("warmup"),
                timeout=10.0,
            )
            return True
        except (APITimeoutError, TimeoutError, Exception):
            return False
