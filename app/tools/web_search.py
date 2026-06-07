import httpx
from app.tools.base import BaseTool

WEB_SEARCH_PROMPT = """Generate a concise search query from this task description.
Output ONLY the search query string, nothing else."""


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Web search via DuckDuckGo — for recent information not in local docs"

    async def _generate_query(self, task_description: str) -> str:
        try:
            from app.core.llm_factory import get_llm
            llm = get_llm()
            result = await llm.agenerate(
                f"{WEB_SEARCH_PROMPT}\nTask: {task_description}"
            )
            return result.strip()[:200]
        except Exception:
            return task_description

    async def arun(
        self, query: str, collection_ids: list[str] | None = None,
        top_k: int = 5
    ) -> list[dict]:
        search_query = await self._generate_query(query)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": search_query, "format": "json", "no_html": "1"},
                )
                data = resp.json()
                results = []
                if data.get("AbstractText"):
                    results.append({
                        "chunk_id": f"web_{hash(data['AbstractURL']) & 0x7FFFFFFF:08x}",
                        "document_id": "web_search",
                        "text": data["AbstractText"],
                        "score": 0.6,
                        "source": "web",
                        "metadata": {"url": data.get("AbstractURL", "")},
                    })
                for topic in data.get("RelatedTopics", [])[:top_k]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "chunk_id": f"web_{hash(topic.get('FirstURL', '')) & 0x7FFFFFFF:08x}",
                            "document_id": "web_search",
                            "text": topic["Text"],
                            "score": 0.4,
                            "source": "web",
                            "metadata": {"url": topic.get("FirstURL", "")},
                        })
                return results
        except Exception:
            return []