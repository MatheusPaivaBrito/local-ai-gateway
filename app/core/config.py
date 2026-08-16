from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Defaults target the preferred development mode: FastAPI running directly in
    WSL/Linux and infrastructure exposed by Docker on loopback ports. The
    containerized gateway overrides these URLs from compose.yaml.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "local-ai-gateway"
    host: str = "127.0.0.1"
    port: int = 8001
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+asyncpg://local_ai:local_ai_change_me@127.0.0.1:5432/local_ai"
    )
    redis_url: str = "redis://127.0.0.1:6379/0"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_registry_base_url: str = "https://ollama.com"
    qdrant_base_url: str = "http://127.0.0.1:6333"

    # Stable public aliases are optional. The UI and /v1/models are still driven
    # by the models actually installed in Ollama.
    model_aliases: dict[str, str] = Field(default_factory=dict)

    inference_default_max_output_tokens: int = 256
    inference_default_reasoning_effort: Literal["none", "low", "medium", "high", "max"] = (
        "none"
    )

    rag_enabled: bool = True
    rag_embedding_model: str = "embeddinggemma"
    rag_default_collection: str = "local_knowledge"
    rag_chunk_size_chars: int = 1200
    rag_chunk_overlap_chars: int = 160
    rag_default_top_k: int = 5
    ollama_embedding_keep_alive: str = "15m"

    agent_default_memory_messages: int = 12

    bootstrap_api_key: str | None = "sk-local-dev-change-me"
    bootstrap_api_key_name: str = "bootstrap-dev"
    local_ui_enabled: bool = True
    local_ui_api_key_name: str = "local-ui"

    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    gpu_telemetry_enabled: bool = False
    gpu_sample_interval_ms: int = 100
    nvidia_gpu_index: int = 0
    electricity_price_per_kwh: float | None = None

    @property
    def ollama_openai_base_url(self) -> str:
        return f"{self.ollama_base_url.rstrip('/')}/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
