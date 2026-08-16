import json
import logging
import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inference.domain import InferenceResult
from app.domains.inference.infrastructure import OllamaOpenAIClient
from app.domains.inference.policy import InferencePolicy
from app.domains.model_catalog.service import ModelCatalogService
from app.domains.usage.domain import extract_usage
from app.domains.usage.service import UsageRecorder
from app.domains.usage.telemetry import TelemetryResult, TelemetryService

logger = logging.getLogger(__name__)


class InferenceService:
    def __init__(
        self,
        *,
        client: OllamaOpenAIClient,
        model_catalog: ModelCatalogService,
        policy: InferencePolicy,
        telemetry: TelemetryService,
        usage_recorder: UsageRecorder,
        electricity_price_per_kwh: float | None,
    ) -> None:
        self.client = client
        self.model_catalog = model_catalog
        self.policy = policy
        self.telemetry = telemetry
        self.usage_recorder = usage_recorder
        self.electricity_price_per_kwh = electricity_price_per_kwh

    async def prepare(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        public_model = payload.get("model")
        if not isinstance(public_model, str) or not public_model.strip():
            raise ValueError("Field 'model' is required")
        upstream_model = await self.model_catalog.resolve(public_model)
        return public_model, upstream_model, self.policy.apply(endpoint, payload, upstream_model)

    async def generate(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        api_key_id: int,
        db: AsyncSession,
        request_id: str,
    ) -> InferenceResult:
        public_model, upstream_model, prepared = await self.prepare(endpoint, payload)
        if prepared.get("stream"):
            raise ValueError("generate() only supports non-stream requests")

        started = time.perf_counter()
        monitor = self.telemetry.new_monitor()
        if monitor is not None:
            await monitor.start()

        telemetry_result: TelemetryResult | None = None
        try:
            response = await self.client.post(endpoint, prepared)
            latency_ms = (time.perf_counter() - started) * 1000.0
            try:
                response_payload = response.json()
            except json.JSONDecodeError:
                response_payload = {
                    "error": {
                        "message": response.text or "Invalid upstream response",
                        "type": "upstream_error",
                        "param": None,
                        "code": "invalid_upstream_response",
                    }
                }

            if not isinstance(response_payload, dict):
                response_payload = {"data": response_payload}

            if monitor is not None:
                usage = extract_usage(response_payload)
                telemetry_result = await monitor.stop(
                    output_tokens=usage.output_tokens,
                    electricity_price_per_kwh=self.electricity_price_per_kwh,
                )

            # Usage persistence is observability. A DB write failure must not hide
            # a valid model reply.
            try:
                await self.usage_recorder.record(
                    db=db,
                    api_key_id=api_key_id,
                    request_id=request_id,
                    endpoint=endpoint,
                    public_model=public_model,
                    upstream_model=upstream_model,
                    payload=response_payload,
                    latency_ms=latency_ms,
                    telemetry=telemetry_result,
                )
            except Exception:
                await db.rollback()
                logger.exception("Failed to persist usage for request_id=%s", request_id)

            return InferenceResult(
                status_code=response.status_code,
                payload=response_payload,
                public_model=public_model,
                upstream_model=upstream_model,
                latency_ms=latency_ms,
            )
        except Exception:
            if monitor is not None and telemetry_result is None:
                try:
                    await monitor.stop(
                        output_tokens=0,
                        electricity_price_per_kwh=self.electricity_price_per_kwh,
                    )
                except Exception:
                    logger.exception("Failed to stop telemetry monitor")
            raise

    async def open_stream(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
    ) -> tuple[httpx.Response, str, str]:
        public_model, upstream_model, prepared = await self.prepare(endpoint, payload)
        prepared["stream"] = True
        response = await self.client.open_stream(endpoint, prepared)
        return response, public_model, upstream_model


def extract_assistant_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content

    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                return str(content.get("text") or "")
    return ""
