from abc import ABC, abstractmethod

class BaseEmbedding(ABC):
    @abstractmethod
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...
    @abstractmethod
    async def aembed_query(self, query: str) -> list[float]: ...
