from abc import ABC, abstractmethod
from typing import AsyncIterator

class BaseLLM(ABC):
    @abstractmethod
    async def agenerate(self, prompt: str, system_prompt: str = "", **kwargs) -> str: ...
    @abstractmethod
    async def astream(self, prompt: str, system_prompt: str = "", **kwargs) -> AsyncIterator[str]: ...
    @abstractmethod
    async def agenerate_structured(self, prompt: str, system_prompt: str = "", output_schema: dict | None = None, **kwargs) -> dict: ...
