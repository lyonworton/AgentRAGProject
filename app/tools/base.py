from abc import ABC, abstractmethod


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        """Execute retrieval, return list of result dicts.

        Each dict MUST include:
          - chunk_id: str
          - text: str
          - score: float
          - source: str  ("milvus" | "kg" | "keyword")

        Optional:
          - document_id: str
        """
        ...