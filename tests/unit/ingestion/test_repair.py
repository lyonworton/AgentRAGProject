import pytest
from unittest.mock import AsyncMock, patch
from app.workers.repair import enqueue_repair, BACKOFF


def test_backoff_length():
    assert len(BACKOFF) == 4
    assert BACKOFF == [60, 300, 900, 3600]


@pytest.mark.asyncio
@patch("app.workers.repair.create_pool")
async def test_enqueue_repair(mock_create_pool):
    mock_redis = AsyncMock()
    mock_redis.enqueue_job.return_value = AsyncMock(job_id="repair_001")
    mock_create_pool.return_value = mock_redis

    await enqueue_repair("doc_001", "neo4j", attempt=0)

    mock_redis.enqueue_job.assert_called_once()
    call_args = mock_redis.enqueue_job.call_args
    assert call_args[0][0] == "repair_document_path"
    assert call_args[0][1] == "doc_001"
    assert call_args[0][2] == "neo4j"
    assert call_args[0][3] == 0


@pytest.mark.asyncio
@patch("app.workers.repair._repair_graph_path")
@patch("app.workers.repair._update_path_status")
@patch("app.workers.repair._check_all_ok_and_set_ready")
async def test_repair_document_path_neo4j_success(
    mock_check_ready, mock_update_status, mock_repair
):
    mock_repair.return_value = None
    mock_update_status.return_value = None
    mock_check_ready.return_value = None

    mock_ctx = {}

    from app.workers.repair import repair_document_path
    await repair_document_path(mock_ctx, "doc_001", "neo4j", attempt=0)

    mock_repair.assert_called_once_with("doc_001")
    mock_update_status.assert_called_once_with("doc_001", "neo4j", "ok")
    mock_check_ready.assert_called_once_with("doc_001")


@pytest.mark.asyncio
@patch("app.workers.repair._repair_graph_path")
async def test_repair_abandons_after_max_attempts(mock_repair):
    mock_repair.side_effect = Exception("still failing")
    mock_ctx = {"redis": AsyncMock()}

    from app.workers.repair import repair_document_path
    await repair_document_path(mock_ctx, "doc_001", "neo4j", attempt=3)

    mock_ctx["redis"].enqueue_job.assert_not_called()


@pytest.mark.asyncio
@patch("app.workers.repair._repair_graph_path")
async def test_repair_reenqueues_on_failure(mock_repair):
    mock_repair.side_effect = Exception("still failing")
    mock_redis = AsyncMock()
    mock_ctx = {"redis": mock_redis}

    from app.workers.repair import repair_document_path
    await repair_document_path(mock_ctx, "doc_001", "neo4j", attempt=1)

    mock_redis.enqueue_job.assert_called_once()
    call_args = mock_redis.enqueue_job.call_args
    assert call_args[0][0] == "repair_document_path"
    assert call_args[0][3] == 2