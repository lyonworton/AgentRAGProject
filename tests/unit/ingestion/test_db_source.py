import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
from app.ingestion.sources.database import DBSource


def test_row_to_document_basic():
    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT * FROM articles",
        title_column="title",
        content_columns=["summary", "body"],
    )

    class FakeRow:
        def __getitem__(self, key):
            return {"title": "Test Title", "summary": "Summary text.", "body": "Full body text."}[key]
        def get(self, key, default=None):
            return {"title": "Test Title", "summary": "Summary text.", "body": "Full body text."}.get(key, default)

    doc = source._row_to_document(FakeRow())
    assert "# Test Title" in doc
    assert "Summary text." in doc
    assert "Full body text." in doc


def test_row_to_document_single_column():
    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT * FROM notes",
        title_column="name",
        content_columns=["text"],
    )

    class FakeRow:
        def __getitem__(self, key):
            return {"name": "Note 1", "text": "Just one content column."}[key]
        def get(self, key, default=None):
            return {"name": "Note 1", "text": "Just one content column."}.get(key, default)

    doc = source._row_to_document(FakeRow())
    assert doc == "# Note 1\n\nJust one content column."


def test_row_to_document_null_values():
    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT * FROM t",
        title_column="title",
        content_columns=["col1", "col2"],
    )

    class FakeRow:
        def __getitem__(self, key):
            return {"title": "T", "col1": "A", "col2": None}[key]
        def get(self, key, default=None):
            return {"title": "T", "col1": "A", "col2": None}.get(key, default)

    doc = source._row_to_document(FakeRow())
    assert "# T" in doc
    assert "A" in doc
    assert "None" not in doc


@pytest.mark.asyncio
@patch("app.ingestion.sources.database.create_engine")
async def test_list_files_executes_query(mock_create_engine):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_result
    mock_result.mappings.return_value = [
        {"title": "Doc 1", "body": "Content 1"},
        {"title": "Doc 2", "body": "Content 2"},
    ]

    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT title, body FROM articles",
        title_column="title",
        content_columns=["body"],
        tmp_dir=tempfile.gettempdir(),
    )

    files = await source.list_files()

    assert len(files) == 2
    assert all(f.endswith(".md") for f in files)

    content = await source.get_file_content(files[0])
    assert b"# Doc 1" in content
    assert b"Content 1" in content

    for f in files:
        os.remove(f)