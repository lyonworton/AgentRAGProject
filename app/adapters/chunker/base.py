from abc import ABC, abstractmethod

class BaseChunker(ABC):
    @abstractmethod
    async def split(self, text: str, metadata: dict | None = None) -> list[dict]: ...
