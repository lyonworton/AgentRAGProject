import pytest
from app.adapters.preprocessor.base import ExtractedPDF
from app.adapters.preprocessor.table import TableExtractor


def _make_extracted_with_tables(pages_data, table_regions=None):
    """Helper to create an ExtractedPDF with optional table regions."""
    pages = [{"page": i + 1, "text": text, "type": "normal"} for i, text in enumerate(pages_data)]
    full_text = "\n\n".join(pages_data)
    boundaries = []
    offset = 0
    for text in pages_data:
        boundaries.append((offset, offset + len(text)))
        offset += len(text) + 2
    table_regions = table_regions or []
    return ExtractedPDF(
        pages=pages,
        full_text=full_text,
        page_boundaries=boundaries,
        has_tables=bool(table_regions),
        table_regions=table_regions,
    )


@pytest.mark.asyncio
async def test_table_extractor_converts_tables_to_markdown():
    """TableExtractor should convert table_regions to markdown tables in ExtractedPDF.tables."""
    extractor = TableExtractor()
    table_regions = [
        {
            "page": 1,
            "index": 0,
            "rows": [["Header 1", "Header 2"], ["Cell A", "Cell B"]],
        },
    ]
    data = _make_extracted_with_tables(
        ["Some intro text", "Page 2 content"],
        table_regions=table_regions,
    )
    result = await extractor.run(data)

    # Should have one converted table
    assert len(result.tables) == 1
    table = result.tables[0]
    assert table["page"] == 1
    assert table["index"] == 0
    assert "| Header 1 | Header 2 |" in table["markdown"]
    assert "| Cell A | Cell B |" in table["markdown"]


@pytest.mark.asyncio
async def test_table_extractor_skip_when_disabled_or_no_tables():
    """When has_tables is False or preprocessor_table_enabled is False, return data unchanged."""
    extractor = TableExtractor()

    # Case 1: has_tables is False
    data_no_tables = _make_extracted_with_tables(
        ["Page 1", "Page 2"],
        table_regions=[],
    )
    result = await extractor.run(data_no_tables)
    assert result.tables == []

    # Case 2: preprocessor_table_enabled is False
    data_with_tables = _make_extracted_with_tables(
        ["Page 1"],
        table_regions=[
            {
                "page": 1,
                "index": 0,
                "rows": [["A", "B"]],
            },
        ],
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PREPROCESSOR_TABLE_ENABLED", "false")
        # Need to re-import to pick up new env, or mock get_settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        result = await extractor.run(data_with_tables)
        assert result.tables == []
