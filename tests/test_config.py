from app.core.config import Settings


def test_defaults_target_bare_metal_fastapi_and_local_container_ports() -> None:
    settings = Settings(_env_file=None)
    assert settings.host == "127.0.0.1"
    assert "@127.0.0.1:5432/" in settings.database_url
    assert settings.redis_url.startswith("redis://127.0.0.1:6379")
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_registry_base_url == "https://ollama.com"
    assert settings.qdrant_base_url == "http://127.0.0.1:6333"
    assert settings.gpu_telemetry_enabled is False
    assert settings.model_aliases == {}
    assert settings.inference_default_max_output_tokens == 256
    assert settings.inference_default_reasoning_effort == "none"
    assert settings.rag_embedding_model == "embeddinggemma"


def test_empty_electricity_price_is_ignored(monkeypatch) -> None:
    monkeypatch.setenv("ELECTRICITY_PRICE_PER_KWH", "")
    settings = Settings(_env_file=None)
    assert settings.electricity_price_per_kwh is None
