from abc import ABC, abstractmethod

class BaseParser(ABC):
    @abstractmethod
    async def parse(self, file_path: str) -> str: ...
