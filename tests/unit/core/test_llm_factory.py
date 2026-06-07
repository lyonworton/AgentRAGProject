import pytest
from unittest.mock import patch


class TestGetLLM:
    def test_returns_openai_by_default(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None
        llm = factory.get_llm()
        from app.adapters.llm.openai import OpenAILLM
        assert isinstance(llm, OpenAILLM)

    def test_returns_ollama_when_configured(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None
        with patch("app.core.llm_factory.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "ollama"
            mock_settings.return_value.ollama_model = "llama3"
            mock_settings.return_value.ollama_base_url = "http://localhost:11434"
            llm = factory.get_llm()
            from app.adapters.llm.ollama import OllamaLLM
            assert isinstance(llm, OllamaLLM)

    def test_invalid_provider_raises(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None
        with patch("app.core.llm_factory.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "invalid"
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                factory.get_llm()

    def test_singleton_returns_same_instance(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None
        a = factory.get_llm()
        b = factory.get_llm()
        assert a is b