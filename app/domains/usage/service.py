from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.usage.domain import extract_usage
from app.domains.usage.persistence import UsageEventRecord
from app.domains.usage.telemetry import TelemetryResult


class UsageRecorder:
    async def record(
        self,
        *,
        db: AsyncSession,
        api_key_id: int,
        request_id: str,
        endpoint: str,
        public_model: str,
        upstream_model: str,
        payload: dict[str, object],
        latency_ms: float,
        telemetry: TelemetryResult | None,
    ) -> None:
        usage = extract_usage(payload)
        telemetry_data = telemetry.as_dict() if telemetry is not None else {}
        db.add(
            UsageEventRecord(
                api_key_id=api_key_id,
                request_id=request_id,
                endpoint=endpoint,
                public_model=public_model,
                upstream_model=upstream_model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                latency_ms=latency_ms,
                **telemetry_data,
            )
        )
        await db.commit()
