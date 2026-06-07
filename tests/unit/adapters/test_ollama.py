import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# Pre-mock langchain_ollama before any test import touches ollama.py
@pytest.fixture(autouse=True)
def _mock_langchain_ollama():
    """Prevent import errors from missing langchain_ollama in local env."""
    fake_chat = MagicMock()
    fake_chat.return_value = fake_chat
    sys.modules["langchain_ollama"] = MagicMock(ChatOllama=fake_chat)
    yield
    sys.modules.pop("langchain_ollama", None)


class TestOllamaLLM:
    """Tests for the Ollama LLM adapter."""

    def test_init_defaults(self):
        from app.adapters.llm.ollama import OllamaLLM
        llm = OllamaLLM()
        assert llm.llm is not None

    def test_init_custom(self):
        from app.adapters.llm.ollama import OllamaLLM
        llm = OllamaLLM(model="llama3", base_url="http://other:11434")
        assert llm.llm is not None

    @pytest.mark.asyncio
    async def test_agenerate_returns_content(self):
        from app.adapters.llm.ollama import OllamaLLM
        llm = OllamaLLM()
        mock_resp = MagicMock()
        mock_resp.content = "Hello, world!"
        llm.llm.ainvoke = AsyncMock(return_value=mock_resp)

        result = await llm.agenerate("Say hello")
        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_agenerate_with_system_prompt(self):
        from app.adapters.llm.ollama import OllamaLLM
        from langchain_core.messages import SystemMessage

        llm = OllamaLLM()
        mock_resp = MagicMock()
        mock_resp.content = "response"
        llm.llm.ainvoke = AsyncMock(return_value=mock_resp)

        result = await llm.agenerate("prompt", system_prompt="Be helpful")
        assert result == "response"
        call_msgs = llm.llm.ainvoke.call_args[0][0]
        assert any(isinstance(m, SystemMessage) for m in call_msgs)

    @pytest.mark.asyncio
    async def test_astream_yields_chunks(self):
        from app.adapters.llm.ollama import OllamaLLM

        chunk1 = MagicMock()
        chunk1.content = "Hello"
        chunk2 = MagicMock()
        chunk2.content = " world"

        async def gen(_msgs):
            for c in [chunk1, chunk2]:
                yield c

        llm = OllamaLLM()
        llm.llm.astream = gen

        chunks = [c async for c in llm.astream("prompt")]
        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_astream_skips_empty_chunks(self):
        from app.adapters.llm.ollama import OllamaLLM

        chunk1 = MagicMock(); chunk1.content = ""
        chunk2 = MagicMock(); chunk2.content = None
        chunk3 = MagicMock(); chunk3.content = "data"

        async def gen(_msgs):
            for c in [chunk1, chunk2, chunk3]:
                yield c

        llm = OllamaLLM()
        llm.llm.astream = gen

        chunks = [c async for c in llm.astream("prompt")]
        assert chunks == ["data"]

    @pytest.mark.asyncio
    async def test_agenerate_structured_parses_json(self):
        from app.adapters.llm.ollama import OllamaLLM

        llm = OllamaLLM()
        mock_resp = MagicMock()
        mock_resp.content = '{"key": "value"}'
        llm.llm.ainvoke = AsyncMock(return_value=mock_resp)

        result = await llm.agenerate_structured("prompt")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_agenerate_structured_strips_code_fence(self):
        from app.adapters.llm.ollama import OllamaLLM

        llm = OllamaLLM()
        mock_resp = MagicMock()
        mock_resp.content = '```json\n{"a": 1}\n```'
        llm.llm.ainvoke = AsyncMock(return_value=mock_resp)

        result = await llm.agenerate_structured("prompt")
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_agenerate_structured_includes_schema(self):
        from app.adapters.llm.ollama import OllamaLLM

        llm = OllamaLLM()
        mock_resp = MagicMock()
        mock_resp.content = '{"name": "test"}'
        llm.llm.ainvoke = AsyncMock(return_value=mock_resp)

        schema = {"name": "string", "age": "int"}
        result = await llm.agenerate_structured("prompt", output_schema=schema)
        assert result == {"name": "test"}