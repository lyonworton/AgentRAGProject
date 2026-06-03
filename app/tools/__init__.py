from app.tools.base import BaseTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tool_descriptions(self) -> str:
        return "\n".join(
            f"- {t.name}: {t.description}" for t in self._tools.values()
        )


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        from app.tools.semantic_search import SemanticSearchTool  # noqa: F811
        from app.tools.kg_search import KGSearchTool
        from app.tools.keyword_search import KeywordSearchTool
        _registry = ToolRegistry()
        _registry.register(SemanticSearchTool())
        _registry.register(KGSearchTool())
        _registry.register(KeywordSearchTool())
    return _registry


__all__ = ["BaseTool", "ToolRegistry", "get_tool_registry"]