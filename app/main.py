import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.database import Database
from app.domains.agents.api import router as agents_router
from app.domains.agents.repository import AgentRepository
from app.domains.agents.service import AgentService
from app.domains.api_keys.api import router as api_keys_router
from app.domains.api_keys.repository import SqlAlchemyApiKeyRepository
from app.domains.api_keys.service import ApiKeyService
from app.domains.inference.api import router as inference_router
from app.domains.inference.infrastructure import OllamaOpenAIClient
from app.domains.inference.policy import InferencePolicy
from app.domains.inference.service import InferenceService
from app.domains.model_catalog.api import router as model_catalog_router
from app.domains.model_catalog.infrastructure import OllamaModelClient, OllamaRegistryClient
from app.domains.model_catalog.service import ModelCatalogService
from app.domains.rag.api import router as rag_router
from app.domains.rag.infrastructure import OllamaEmbeddingClient, QdrantVectorStore
from app.domains.rag.service import RagService
from app.domains.rate_limit.service import RateLimiter
from app.domains.usage.api import router as usage_router
from app.domains.usage.service import UsageRecorder
from app.domains.usage.telemetry import TelemetryService
from app.http.system import router as system_router
from app.http.web import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    database = Database(settings)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    api_keys = ApiKeyService(SqlAlchemyApiKeyRepository())
    rate_limiter = RateLimiter(
        redis,
        settings.rate_limit_requests,
        settings.rate_limit_window_seconds,
    )

    model_client = OllamaModelClient(settings.ollama_base_url)
    registry_client = OllamaRegistryClient(settings.ollama_registry_base_url)
    model_catalog = ModelCatalogService(
        model_client, settings.model_aliases, registry=registry_client
    )

    telemetry = TelemetryService(
        enabled=settings.gpu_telemetry_enabled,
        gpu_index=settings.nvidia_gpu_index,
        sample_interval_ms=settings.gpu_sample_interval_ms,
    )
    inference_client = OllamaOpenAIClient(settings.ollama_openai_base_url)
    inference = InferenceService(
        client=inference_client,
        model_catalog=model_catalog,
        policy=InferencePolicy(
            max_output_tokens=settings.inference_default_max_output_tokens,
            reasoning_effort=settings.inference_default_reasoning_effort,
        ),
        telemetry=telemetry,
        usage_recorder=UsageRecorder(),
        electricity_price_per_kwh=settings.electricity_price_per_kwh,
    )

    rag: RagService | None = None
    embedding_client: OllamaEmbeddingClient | None = None
    qdrant_store: QdrantVectorStore | None = None
    if settings.rag_enabled:
        embedding_client = OllamaEmbeddingClient(
            settings.ollama_base_url,
            model=settings.rag_embedding_model,
            keep_alive=settings.ollama_embedding_keep_alive,
        )
        qdrant_store = QdrantVectorStore(settings.qdrant_base_url)
        rag = RagService(
            embeddings=embedding_client,
            store=qdrant_store,
            default_collection=settings.rag_default_collection,
            chunk_size=settings.rag_chunk_size_chars,
            chunk_overlap=settings.rag_chunk_overlap_chars,
            default_top_k=settings.rag_default_top_k,
        )

    agents = AgentService(
        repository=AgentRepository(),
        inference=inference,
        rag=rag,
    )

    app.state.settings = settings
    app.state.database = database
    app.state.redis = redis
    app.state.api_keys = api_keys
    app.state.rate_limiter = rate_limiter
    app.state.model_catalog = model_catalog
    app.state.telemetry = telemetry
    app.state.inference = inference
    app.state.rag = rag
    app.state.agents = agents
    app.state.local_ui_api_key = None

    await database.create_schema()
    async with database.sessions() as session:
        await api_keys.ensure_bootstrap_key(
            session,
            raw_key=settings.bootstrap_api_key,
            name=settings.bootstrap_api_key_name,
        )
        app.state.local_ui_api_key = await api_keys.rotate_local_ui_key(
            session,
            name=settings.local_ui_api_key_name,
            enabled=settings.local_ui_enabled,
        )

    try:
        yield
    finally:
        await inference_client.close()
        await model_client.close()
        await registry_client.close()
        if embedding_client is not None:
            await embedding_client.close()
        if qdrant_store is not None:
            await qdrant_store.close()
        telemetry.close()
        await redis.aclose()
        await database.close()


app = FastAPI(title="Local AI Gateway", version="0.4.0", lifespan=lifespan)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = f"req_{uuid4().hex}"
    response = await call_next(request)
    response.headers.setdefault("x-request-id", request.state.request_id)
    return response


app.include_router(web_router)
app.include_router(system_router)
app.include_router(model_catalog_router)
app.include_router(inference_router)
app.include_router(api_keys_router)
app.include_router(usage_router)
app.include_router(rag_router)
app.include_router(agents_router)
