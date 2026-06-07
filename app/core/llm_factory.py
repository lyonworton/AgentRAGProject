from app.adapters.llm.base import BaseLLM
from app.core.config import get_settings

_llm_instance: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    settings = get_settings()
    provider = settings.llm_provider

    if provider == "openai":
        from app.adapters.llm.openai import OpenAILLM
        _llm_instance = OpenAILLM()
    elif provider == "ollama":
        from app.adapters.llm.ollama import OllamaLLM
        _llm_instance = OllamaLLM(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    return _llm_instance