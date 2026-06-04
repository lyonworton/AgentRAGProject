from abc import ABC, abstractmethod


class BaseMemoryStore(ABC):
    @abstractmethod
    async def asave(self, key: str, data: dict, ttl: int | None = None) -> None:
        ...

    @abstractmethod
    async def aload(self, key: str) -> dict | None:
        ...

    @abstractmethod
    async def adelete(self, key: str) -> None:
        ...