from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InferenceResult:
    status_code: int
    payload: dict[str, Any]
    public_model: str
    upstream_model: str
    latency_ms: float
