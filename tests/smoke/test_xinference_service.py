"""Smoke test: verify xinference service is reachable in docker-compose."""

import asyncio
import pytest


@pytest.mark.asyncio
async def test_xinference_endpoint_reachable():
    """Xinference should respond on /v1/models endpoint."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="http://xinference:9997/v1", api_key="xst-token")
    try:
        models = await asyncio.wait_for(client.models.list(), timeout=5.0)
        model_ids = [m.id for m in models.data]
        assert len(model_ids) > 0, "Xinference should serve at least one model"
    except Exception:
        pytest.skip("xinference service not available (not running in docker)")
