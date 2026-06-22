import pytest
from app.adapters.preprocessor.base import ExtractedPDF
from app.adapters.preprocessor.chunker import ParentChildChunker, ChunkedDocument


def _make_extracted(pages_data):
    """Helper to create an ExtractedPDF from page text data."""
    pages = [{"page": i + 1, "text": text, "type": "normal"} for i, text in enumerate(pages_data)]
    full_text = "\n\n".join(pages_data)
    boundaries = []
    offset = 0
    for text in pages_data:
        boundaries.append((offset, offset + len(text)))
        offset += len(text) + 2
    return ExtractedPDF(pages=pages, full_text=full_text, page_boundaries=boundaries)


@pytest.mark.asyncio
async def test_chunker_creates_parent_groups_from_headings():
    """ParentChildChunker should detect headings and create parent groups per section."""
    chunker = ParentChildChunker(parentchunk_size=2000, subchunk_size=128)
    pages = [
        "# Introduction\n\nThis is the intro text with enough content to fill some space.\n\n## Background\n\nBackground information here with more text to pad out the section length for testing purposes.",
    ]
    data = _make_extracted(pages)
    result = await chunker.run(data)

    assert isinstance(result, ChunkedDocument)
    # Should have parent groups with the expected headings
    headings = {pg["heading"] for pg in result.parent_groups.values()}
    assert "Introduction" in headings
    assert "Background" in headings

    # Each parent group should have required fields
    for pg_id, pg in result.parent_groups.items():
        assert "text" in pg
        assert "content_start" in pg
        assert "content_end" in pg
        assert "child_ids" in pg
        assert "heading" in pg
        assert isinstance(pg["child_ids"], list)


@pytest.mark.asyncio
async def test_chunker_splits_large_sections_into_multiple_parents():
    """When a section exceeds parentchunk_size, it should be split via sliding window."""
    chunker = ParentChildChunker(parentchunk_size=100, subchunk_size=50)
    # Create a section longer than parentchunk_size
    long_content = " ".join([f"word{i}" for i in range(50)])
    pages = [
        f"# Big Section\n\n{long_content}",
    ]
    data = _make_extracted(pages)
    result = await chunker.run(data)

    big_section_parents = [
        pg for pg in result.parent_groups.values()
        if pg["heading"] == "Big Section"
    ]
    # Should have at least 2 parent groups since content > 100 chars
    assert len(big_section_parents) >= 2

    # Verify sliding window overlap: consecutive parents should share ~50 chars
    big_section_parents.sort(key=lambda p: p["content_start"])
    for i in range(len(big_section_parents) - 1):
        curr_end = big_section_parents[i]["content_end"]
        next_start = big_section_parents[i + 1]["content_start"]
        overlap = curr_end - next_start
        assert overlap > 0, "Consecutive parent groups should overlap"


@pytest.mark.asyncio
async def test_chunker_produces_child_chunks_with_metadata():
    """Each parent group should produce child chunks split by subchunk_size."""
    chunker = ParentChildChunker(parentchunk_size=2000, subchunk_size=80)
    pages = [
        "# Section A\n\nThis is a paragraph with some text. Here is more text to make it longer. And even more text to ensure we exceed the subchunk size limit and force splitting into multiple child chunks.",
    ]
    data = _make_extracted(pages)
    result = await chunker.run(data)

    assert isinstance(result, ChunkedDocument)
    assert len(result.child_chunks) > 0

    # Each child chunk should have required fields
    for child in result.child_chunks:
        assert "chunk_id" in child
        assert "parent_group_id" in child
        assert "text" in child
        assert "metadata" in child
        meta = child["metadata"]
        assert "parent_group_id" in meta
        assert "content_start" in meta
        assert "content_end" in meta
        assert "source_page" in meta
        assert "content_type" in meta

    # Child chunks should link to parent groups
    for child in result.child_chunks:
        assert child["parent_group_id"] in result.parent_groups

    # All parent child_ids should match children
    for pg_id, pg in result.parent_groups.items():
        child_ids_in_children = {c["chunk_id"] for c in result.child_chunks if c["parent_group_id"] == pg_id}
        assert set(pg["child_ids"]) == child_ids_in_children
