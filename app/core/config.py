from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://agentrag:agentrag@localhost:5432/agentrag"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    llm_provider: str = "openai"  # "openai" | "ollama"
    ollama_model: str = "qwen2.5"
    ollama_base_url: str = "http://localhost:11434"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    app_env: str = "development"
    log_level: str = "INFO"
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 100
    max_query_tokens: int = 32000
    max_iterations: int = 5
    quality_threshold: float = 0.7

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "agentrag123"

    # Elasticsearch
    es_host: str = "http://localhost:9200"

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache()
def get_settings() -> Settings:
    return Settings()