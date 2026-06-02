import pytest
from app.adapters.chunker.recursive import RecursiveChunker


@pytest.mark.asyncio
async def test_recursive_chunker_splits_text():
    chunker = RecursiveChunker(chunk_size=200, chunk_overlap=50)
    text = "This is the first sentence. And this is the second sentence. " * 20
    chunks = await chunker.split(text)
    assert len(chunks) > 1
    for c in chunks:
        assert "text" in c
        assert len(c["text"]) > 0


@pytest.mark.asyncio
async def test_recursive_chunker_empty_text():
    chunker = RecursiveChunker()
    chunks = await chunker.split("")
    assert len(chunks) == 0
