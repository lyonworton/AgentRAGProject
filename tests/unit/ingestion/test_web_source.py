import pytest
import os
import tempfile
from unittest.mock import AsyncMock, patch
from app.ingestion.sources.web import WebSource


@pytest.mark.asyncio
async def test_web_source_list_files_no_urls():
    source = WebSource(urls=[])
    files = await source.list_files()
    assert files == []


def test_extract_text_removes_noise_tags():
    html = """
    <html><head><script>alert('x')</script><style>body{}</style></head>
    <body>
        <nav>导航</nav>
        <header>页头</header>
        <main><p>正文内容在这里</p></main>
        <footer>页脚</footer>
        <aside>侧栏</aside>
    </body></html>
    """
    source = WebSource(urls=["http://example.com"])
    text = source._extract_text(html)

    assert "正文内容在这里" in text
    assert "导航" not in text
    assert "页头" not in text
    assert "页脚" not in text
    assert "侧栏" not in text
    assert "alert" not in text


def test_extract_text_empty_html():
    source = WebSource(urls=["http://example.com"])
    text = source._extract_text("<html></html>")
    assert isinstance(text, str)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_list_files_fetches_and_saves(mock_get):
    html = "<html><body><p>Hello World</p></body></html>"

    mock_response = AsyncMock()
    mock_response.text = html
    mock_response.raise_for_status = AsyncMock()
    mock_get.return_value = mock_response

    source = WebSource(urls=["http://example.com/test"], tmp_dir=tempfile.gettempdir())
    files = await source.list_files()

    assert len(files) == 1
    assert files[0].endswith(".txt")
    content = await source.get_file_content(files[0])
    assert b"Hello World" in content
    os.remove(files[0])