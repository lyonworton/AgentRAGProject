from openai import AsyncOpenAI
from app.adapters.embedding.base import BaseEmbedding
from app.core.config import get_settings
settings = get_settings()

class OpenAIEmbedding(BaseEmbedding):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.model = settings.embedding_model

    async def aembed_documents(self, texts):
        resp = await self.client.embeddings.create(input=texts, model=self.model)
        return [d.embedding for d in resp.data]

    async def aembed_query(self, query):
        resp = await self.client.embeddings.create(input=[query], model=self.model)
        return resp.data[0].embedding
