from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ParsedDocument:
    title: str
    content: str
    mime_type: str
    file_size: int
    metadata: dict

class BaseLoader(ABC):
    @abstractmethod
    async def load(self, file_path: str) -> ParsedDocument: ...
