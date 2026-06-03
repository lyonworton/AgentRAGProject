"""LLM-based relation extraction for graph_path ingestion pipeline.

Given raw text and pre-extracted candidate entities, this module uses an LLM
to disambiguate entities and extract semantic relationships between them.
"""

import json

RELATION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "person",
                            "location",
                            "organization",
                            "concept",
                            "term",
                        ],
                    },
                    "aliases": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "name", "type", "aliases"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_entity": {"type": "string"},
                    "to_entity": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "RELATED_TO",
                            "PART_OF",
                            "DEPENDS_ON",
                            "PRODUCES",
                            "DESCRIBES",
                            "LOCATED_IN",
                        ],
                    },
                },
                "required": ["from_entity", "to_entity", "type"],
            },
        },
    },
    "required": ["entities", "relations"],
}


async def extract_relations(text: str, entities: list[dict], llm) -> dict:
    """Disambiguate candidate entities and extract relationships via LLM.

    Args:
        text: Raw source text (truncated to 3000 characters internally).
        entities: Candidate entities as ``[{"name", "score", "type"}, ...]``.
        llm: ``BaseLLM`` instance  whose ``agenerate_structured`` method is
            called with the RELATION_SCHEMA.

    Returns:
        ``{"entities": [...], "relations": [...]}`` where each entity has
        ``id``, ``name``, ``type``, ``aliases`` and each relation has
        ``from_entity``, ``to_entity``, ``type``.
    """
    if not entities:
        return {"entities": [], "relations": []}

    truncated = text[:3000]
    entity_json = json.dumps(entities, ensure_ascii=False)

    prompt = f"""文本:
{truncated}

候选实体:
{entity_json}

任务:
1. 对候选实体进行消歧：同名不同义拆分为不同实体，同义不同名合并为一个实体（aliases 列出别名）
2. 提取实体之间的语义关系

返回符合 schema 的 JSON。"""

    system_prompt = (
        "你是一个知识图谱构建专家。仔细分析文本，准确提取实体和关系。"
    )

    return await llm.agenerate_structured(
        prompt,
        system_prompt=system_prompt,
        output_schema=RELATION_SCHEMA,
    )