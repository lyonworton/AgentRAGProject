from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)
    memory_id: str | None = None
    content_start: int | None = None
    content_end: int | None = None
    parent_group_id: str | None = None

    def __post_init__(self) -> None:
        if self.content_start is None:
            self.content_start = self.metadata.get("content_start")
        if self.content_end is None:
            self.content_end = self.metadata.get("content_end")
        if self.parent_group_id is None:
            self.parent_group_id = self.metadata.get("parent_group_id")

class BaseVectorStore(ABC):
    @abstractmethod
    async def create_collection(self, collection_name: str, dim: int): ...
    @abstractmethod
    async def insert(self, collection_name: str, chunks: list[dict], embeddings: list[list[float]]): ...
    @abstractmethod
    async def search(self, collection_name: str, query_embedding: list[float], top_k: int = 10) -> list[SearchResult]: ...
    @abstractmethod
    async def delete_collection(self, collection_name: str): ...
    @abstractmethod
    async def delete_by_document(self, collection_name: str, document_id: str): ...
