async def write_document_to_es(
    doc_id: str,
    collection_id: str,
    title: str,
    content: str,
    metadata: dict,
    search_store,
) -> None:
    """将完整文档写入 Elasticsearch（不分块）。

    Args:
        doc_id: 文档 ID
        collection_id: 知识库 ID
        title: 文档标题
        content: 完整文档内容（不分块）
        metadata: 文档元数据 (source_type, source_path, mime_type, language, page_number 等)
        search_store: ElasticsearchStore 实例
    """
    await search_store.aindex_document(
        collection_id, doc_id, title, content, metadata
    )