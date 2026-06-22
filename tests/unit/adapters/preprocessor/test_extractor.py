import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_extractor_uses_pypdf_when_successful(tmp_path):
    """When pypdf succeeds, use it and don't call pdfplumber."""
    from app.adapters.preprocessor.extractor import PDFTextExtractor
    from app.adapters.preprocessor.base import ExtractedPDF

    # Create a valid PDF file (just needs to exist for the path)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()

    # Mock pypdf to avoid needing a real PDF file
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page 1 content"
    mock_reader.pages = [mock_page]
    mock_reader.__len__ = MagicMock(return_value=1)

    with patch("app.adapters.preprocessor.extractor.PdfReader", return_value=mock_reader):
        extractor = PDFTextExtractor()
        result = await extractor.extract(str(pdf_path))

    assert isinstance(result, ExtractedPDF)
    assert result.full_text == "Page 1 content"
    assert len(result.pages) == 1
    assert result.pages[0]["page"] == 1
    assert result.pages[0]["text"] == "Page 1 content"
    assert result.pages[0]["type"] == "normal"
    assert result.page_boundaries == [(0, 14)]
    assert result.has_tables is False


@pytest.mark.asyncio
async def test_extractor_falls_back_to_pdfplumber_on_pypdf_failure(tmp_path):
    """When pypdf raises, fall back to pdfplumber."""
    from app.adapters.preprocessor.extractor import PDFTextExtractor
    from app.adapters.preprocessor.base import ExtractedPDF

    mock_reader = MagicMock()
    mock_reader.pages = []
    mock_reader.__len__ = MagicMock(return_value=0)
    mock_reader.__iter__ = MagicMock(return_value=iter([]))

    with patch("app.adapters.preprocessor.extractor.PdfReader", side_effect=Exception("corrupt PDF")), \
         patch("app.adapters.preprocessor.extractor.pdfplumber.open") as mock_plumber:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Plumber content"
        mock_page.chars = [{"text": "P", "x0": 0, "x1": 10, "y0": 0, "y1": 14}, ]
        mock_doc.pages = [mock_page]
        mock_plumber.return_value.__enter__ = MagicMock(return_value=mock_doc)
        mock_plumber.return_value.__exit__ = MagicMock(return_value=False)

        extractor = PDFTextExtractor()
        result = await extractor.extract(str(tmp_path / "fake.pdf"))

    assert result.full_text == "Plumber content"
    assert result.has_tables is False


@pytest.mark.asyncio
async def test_extractor_returns_page_boundaries():
    """page_boundaries correctly maps char offsets per page."""
    mock_reader = MagicMock()
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Hello"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "World"
    mock_reader.pages = [mock_page1, mock_page2]
    mock_reader.__len__ = MagicMock(return_value=2)

    fake_pdf = "/fake/path.pdf"

    with patch("app.adapters.preprocessor.extractor.PdfReader", return_value=mock_reader):
        from app.adapters.preprocessor.extractor import PDFTextExtractor
        extractor = PDFTextExtractor()
        result = await extractor.extract(fake_pdf)

    # full_text = "Hello" + "\n\n" + "World" = "Hello\n\nWorld" (13 chars)
    # page 0: 0-5, page 1: 7-12
    assert result.page_boundaries == [(0, 5), (7, 12)]
