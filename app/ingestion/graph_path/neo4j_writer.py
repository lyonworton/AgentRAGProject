async def write_graph_to_neo4j(
    doc_id: str, entities: list[dict], relations: list[dict], kg_store
) -> None:
    """将实体和关系写入 Neo4j 知识图谱。

    Args:
        doc_id: 文档 ID
        entities: 消歧后的实体列表 [{"id", "name", "type", "aliases"}, ...]
        relations: 关系列表 [{"from_entity", "to_entity", "type"}, ...]
        kg_store: Neo4jKGStore 实例
    """
    await kg_store.acreate_graph(doc_id, entities, relations)