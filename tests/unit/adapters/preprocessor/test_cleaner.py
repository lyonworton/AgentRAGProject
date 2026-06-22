import pytest
from app.adapters.preprocessor.base import ExtractedPDF
from app.adapters.preprocessor.cleaner import HeaderFooterCleaner


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
async def test_auto_detect_repeated_header():
    """Pages with identical top-N text should be detected as headers and stripped."""
    cleaner = HeaderFooterCleaner(top_lines=2, bottom_lines=2)
    pages = [
        "CONFIDENTIAL\nSection A\nActual content line 1\nActual content line 2",
        "CONFIDENTIAL\nSection A\nMore content here\nAnd more text",
        "CONFIDENTIAL\nSection A\nThird page stuff\nStill going",
    ]
    data = _make_extracted(pages)
    result = await cleaner.run(data)

    # The repeated top-2 lines should be stripped from all pages
    for page in result.pages:
        assert "CONFIDENTIAL" not in page["text"]
        assert "Section A" not in page["text"]


@pytest.mark.asyncio
async def test_regex_filter_applied():
    """Custom regex patterns should filter matching text."""
    cleaner = HeaderFooterCleaner(top_lines=2, bottom_lines=2, regex_patterns=[r"^Page \d+/\d+$"])
    pages = [
        "Page 1/3\nRegular text one",
        "Page 2/3\nRegular text two",
        "Page 3/3\nRegular text three",
    ]
    data = _make_extracted(pages)
    result = await cleaner.run(data)

    for page in result.pages:
        assert "Page" not in page["text"]


@pytest.mark.asyncio
async def test_no_change_when_no_headers():
    """If no repeated headers found and no regex matches, data is unchanged."""
    cleaner = HeaderFooterCleaner(top_lines=2, bottom_lines=2)
    pages = ["Unique content A", "Different content B", "Another thing C"]
    data = _make_extracted(pages)
    result = await cleaner.run(data)

    for i, page in enumerate(result.pages):
        assert page["text"] == pages[i]
