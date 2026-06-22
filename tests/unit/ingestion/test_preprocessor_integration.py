"""Integration test: PreprocessorPipeline wired into ingestion pipeline."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.adapters.preprocessor.base import ChunkedDocument, ExtractedPDF


class TestPreprocessorPipeline:
    """Test that PreprocessorPipeline chains all steps correctly."""

    @pytest.mark.asyncio
    async def test_pipeline_runs_all_steps_and_returns_chunked_document(self, tmp_path):
        """PreprocessorPipeline(file_path).run() returns ChunkedDocument with child_chunks."""
        from app.ingestion.preprocessor import PreprocessorPipeline

        fake_text = "# Introduction\n\nThis is introductory content for testing the preprocessor pipeline.\n\n## Details\n\nMore detailed content here to ensure we have enough text for chunking."

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("fake pdf content")

        mock_extracted = ExtractedPDF(
            pages=[{"page": 1, "text": fake_text, "type": "normal"}],
            full_text=fake_text,
            page_boundaries=[(0, len(fake_text))],
            has_tables=False,
        )

        mock_chunked = ChunkedDocument(
            child_chunks=[
                {
                    "chunk_id": "chunk_0",
                    "parent_group_id": "parent_test",
                    "text": "This is introductory content",
                    "metadata": {
                        "parent_group_id": "parent_test",
                        "source_page": 1,
                        "content_type": "chunk",
                    },
                }
            ],
            parent_groups={
                "parent_test": {
                    "text": fake_text,
                    "content_start": 0,
                    "content_end": len(fake_text),
                    "child_ids": ["chunk_0"],
                    "heading": "Introduction",
                }
            },
            cleaned_full_text=fake_text,
        )

        with patch(
            "app.ingestion.preprocessor.PDFTextExtractor"
        ) as mock_extractor_cls, \
             patch(
            "app.ingestion.preprocessor.HeaderFooterCleaner"
        ) as mock_cleaner_cls, \
             patch(
            "app.ingestion.preprocessor.TableExtractor"
        ) as mock_table_cls, \
             patch(
            "app.ingestion.preprocessor.ParentChildChunker"
        ) as mock_chunker_cls:

            mock_extractor = AsyncMock()
            mock_extractor.extract = AsyncMock(return_value=mock_extracted)
            mock_extractor.run = AsyncMock(return_value=mock_extracted)
            mock_extractor_cls.return_value = mock_extractor

            mock_cleaner = AsyncMock()
            mock_cleaner.run = AsyncMock(return_value=mock_extracted)
            mock_cleaner_cls.return_value = mock_cleaner

            mock_table = AsyncMock()
            mock_table.run = AsyncMock(return_value=mock_extracted)
            mock_table_cls.return_value = mock_table

            mock_chunker = AsyncMock()
            mock_chunker.run = AsyncMock(return_value=mock_chunked)
            mock_chunker_cls.return_value = mock_chunker

            pipeline = PreprocessorPipeline(str(pdf_path))
            result = await pipeline.run()

        # Verify the result
        assert isinstance(result, ChunkedDocument)
        assert len(result.child_chunks) > 0
        assert result.cleaned_full_text == fake_text

        # Verify all steps were called in order
        mock_extractor.extract.assert_called_once_with(str(pdf_path))
        mock_cleaner.run.assert_called_once()
        mock_table.run.assert_called_once()
        mock_chunker.run.assert_called_once()


class TestRunSemanticPathWithPreprocessor:
    """Test run_semantic_path integrates PreprocessorPipeline when enabled."""

    @pytest.mark.asyncio
    async def test_semantic_path_uses_preprocessor_when_enabled(self):
        """When preprocessor_enabled=True, run_semantic_path uses PreprocessorPipeline."""
        from app.ingestion.pipeline import run_semantic_path

        doc = MagicMock()
        doc.content = "original content"
        doc.id = "doc_001"
        doc.source_path = "/tmp/test.pdf"

        with patch(
            "app.ingestion.pipeline.get_settings"
        ) as mock_settings, patch(
            "app.ingestion.pipeline.PreprocessorPipeline",
        ) as mock_pp_cls, patch(
            "app.ingestion.semantic_path.embedder.get_embedder"
        ) as mock_embedder_factory:
            mock_cfg = MagicMock()
            mock_cfg.preprocessor_enabled = True
            mock_cfg.embedding_dim = 1024
            mock_settings.return_value = mock_cfg

            mock_chunked = ChunkedDocument(
                child_chunks=[
                    {
                        "chunk_id": "c1",
                        "parent_group_id": "pg1",
                        "text": "preprocessed chunk",
                        "metadata": {"parent_group_id": "pg1"},
                    }
                ],
                parent_groups={"pg1": {"text": "preprocessed", "heading": "Section"}},
                cleaned_full_text="preprocessed content",
            )

            mock_pipeline = AsyncMock()
            mock_pipeline.run = AsyncMock(return_value=mock_chunked)
            mock_pp_cls.return_value = mock_pipeline

            mock_embedder = AsyncMock()
            mock_embedder.aembed_documents = AsyncMock(
                return_value=[[0.1] * 1024]
            )
            mock_embedder_factory.return_value = mock_embedder

            result = await run_semantic_path(doc, "col_test", 1024)

        # Verify: doc.content was updated with cleaned text
        assert doc.content == "preprocessed content"
        # Verify: chunks came from preprocessor (child_chunks)
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["text"] == "preprocessed chunk"
        # Verify: embeddings were computed
        assert len(result["embeddings"]) == 1

    @pytest.mark.asyncio
    async def test_semantic_path_fallback_when_preprocessor_disabled(self):
        """When preprocessor_enabled=False, run_semantic_path uses original chunk_text."""
        from app.ingestion.pipeline import run_semantic_path

        doc = MagicMock()
        doc.content = "fallback content"
        doc.id = "doc_002"
        doc.source_path = "/tmp/test.txt"

        with patch(
            "app.ingestion.pipeline.get_settings"
        ) as mock_settings, patch(
            "app.ingestion.pipeline.chunk_text"
        ) as mock_chunk, patch(
            "app.ingestion.semantic_path.embedder.get_embedder"
        ) as mock_embedder_factory:
            mock_cfg = MagicMock()
            mock_cfg.preprocessor_enabled = False
            mock_cfg.embedding_dim = 1024
            mock_settings.return_value = mock_cfg

            mock_chunk.return_value = [
                {"text": "fallback chunk", "metadata": {"source": "/tmp/test.txt"}}
            ]

            mock_embedder = AsyncMock()
            mock_embedder.aembed_documents = AsyncMock(
                return_value=[[0.2] * 1024]
            )
            mock_embedder_factory.return_value = mock_embedder

            result = await run_semantic_path(doc, "col_test", 1024)

        # Verify: original chunk_text was used
        mock_chunk.assert_called_once()
        # Verify: doc.content unchanged (no preprocessor)
        assert doc.content == "fallback content"
        # Verify: chunks came from chunk_text
        assert result["chunks"][0]["text"] == "fallback chunk"


class TestBatchFlushMilvusParentChunkId:
    """Test batch_flush_milvus sets parent_chunk_id from metadata."""

    @pytest.mark.asyncio
    async def test_batch_flush_sets_parent_chunk_id_from_metadata(self):
        """batch_flush_milvus should set parent_chunk_id from chunk metadata parent_group_id."""
        from app.ingestion.pipeline import batch_flush_milvus

        mock_store = MagicMock()
        mock_store.insert = AsyncMock()

        with patch("app.ingestion.pipeline.MilvusStore", return_value=mock_store):
            batch_data = [
                {
                    "doc_id": "d1",
                    "chunks": [
                        {
                            "text": "chunk1",
                            "metadata": {"parent_group_id": "pg_abc"},
                        },
                        {
                            "text": "chunk2",
                            "metadata": {"parent_group_id": "pg_abc"},
                        },
                    ],
                    "embeddings": [[0.1] * 1024, [0.2] * 1024],
                    "count": 2,
                }
            ]

            count = await batch_flush_milvus("col_test", batch_data)

        assert count == 2
        # Verify insert was called with records that have parent_chunk_id set
        call_args = mock_store.insert.call_args
        records = call_args[0][1]  # first positional arg after col_name
        assert len(records) == 2
        assert records[0]["parent_chunk_id"] == "pg_abc"
        assert records[1]["parent_chunk_id"] == "pg_abc"
