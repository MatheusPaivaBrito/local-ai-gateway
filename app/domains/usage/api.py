from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.core.errors import openai_error
from app.domains.usage.persistence import UsageEventRecord
from app.http.dependencies import AuthDep, DbDep

router = APIRouter()

_USAGE_KEYS = (
    "request_id",
    "endpoint",
    "public_model",
    "upstream_model",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_ms",
    "created_at",
    "gpu_name",
    "gpu_index",
    "utilization_avg_pct",
    "utilization_peak_pct",
    "memory_peak_mb",
    "temperature_avg_c",
    "temperature_peak_c",
    "power_avg_w",
    "power_peak_w",
    "energy_joules",
    "energy_wh",
    "energy_source",
    "joules_per_output_token",
    "output_tokens_per_wh",
    "output_tokens_per_second",
    "estimated_energy_cost",
)


def _usage_payload(event: UsageEventRecord) -> dict[str, Any]:
    payload = {key: getattr(event, key) for key in _USAGE_KEYS}
    payload["created_at"] = event.created_at.isoformat() if event.created_at else None
    return payload


@router.get("/admin/usage/{request_id}")
async def usage_by_request(request_id: str, auth: AuthDep, db: DbDep):
    if isinstance(auth, JSONResponse):
        return auth
    event = await db.scalar(
        select(UsageEventRecord).where(
            UsageEventRecord.request_id == request_id,
            UsageEventRecord.api_key_id == auth.api_key.id,
        )
    )
    if event is None:
        return openai_error(
            404,
            f"Usage event '{request_id}' was not found.",
            error_type="invalid_request_error",
            code="usage_not_found",
            param="request_id",
            headers=auth.rate_limit.headers(),
        )
    return JSONResponse(_usage_payload(event), headers=auth.rate_limit.headers())


@router.get("/admin/metrics/gpu")
async def gpu_metrics(request: Request, auth: AuthDep, db: DbDep):
    if isinstance(auth, JSONResponse):
        return auth
    if not request.app.state.settings.gpu_telemetry_enabled:
        return JSONResponse(
            {"telemetry_enabled": False, "requests_measured": 0, "latest": None},
            headers=auth.rate_limit.headers(),
        )

    aggregate = (
        await db.execute(
            select(
                func.count(UsageEventRecord.id),
                func.coalesce(func.sum(UsageEventRecord.input_tokens), 0),
                func.coalesce(func.sum(UsageEventRecord.output_tokens), 0),
                func.coalesce(func.sum(UsageEventRecord.energy_joules), 0.0),
                func.coalesce(func.sum(UsageEventRecord.energy_wh), 0.0),
                func.avg(UsageEventRecord.power_avg_w),
                func.max(UsageEventRecord.power_peak_w),
                func.avg(UsageEventRecord.utilization_avg_pct),
                func.max(UsageEventRecord.memory_peak_mb),
                func.avg(UsageEventRecord.temperature_avg_c),
                func.coalesce(func.sum(UsageEventRecord.estimated_energy_cost), 0.0),
            ).where(UsageEventRecord.energy_joules.is_not(None))
        )
    ).one()
    latest = await db.scalar(
        select(UsageEventRecord)
        .where(UsageEventRecord.energy_joules.is_not(None))
        .order_by(UsageEventRecord.created_at.desc())
        .limit(1)
    )
    output_tokens = int(aggregate[2])
    energy_joules = float(aggregate[3])
    energy_wh = float(aggregate[4])
    price = request.app.state.settings.electricity_price_per_kwh

    return JSONResponse(
        {
            "telemetry_enabled": True,
            "requests_measured": int(aggregate[0]),
            "input_tokens": int(aggregate[1]),
            "output_tokens": output_tokens,
            "energy_joules": energy_joules,
            "energy_wh": energy_wh,
            "average_power_w": float(aggregate[5]) if aggregate[5] is not None else None,
            "peak_power_w": float(aggregate[6]) if aggregate[6] is not None else None,
            "average_gpu_utilization_pct": (
                float(aggregate[7]) if aggregate[7] is not None else None
            ),
            "peak_memory_mb": float(aggregate[8]) if aggregate[8] is not None else None,
            "average_temperature_c": float(aggregate[9]) if aggregate[9] is not None else None,
            "joules_per_output_token": energy_joules / output_tokens if output_tokens else None,
            "output_tokens_per_wh": output_tokens / energy_wh if energy_wh > 0 else None,
            "estimated_energy_cost": float(aggregate[10]) if price is not None else None,
            "latest": _usage_payload(latest) if latest is not None else None,
        },
        headers=auth.rate_limit.headers(),
    )
