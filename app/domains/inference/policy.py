from copy import deepcopy
from typing import Any


class InferencePolicy:
    """Applies conservative local defaults without overriding explicit client choices."""

    def __init__(self, *, max_output_tokens: int, reasoning_effort: str) -> None:
        self.max_output_tokens = max(1, max_output_tokens)
        self.reasoning_effort = reasoning_effort

    def apply(self, endpoint: str, payload: dict[str, Any], upstream_model: str) -> dict[str, Any]:
        prepared = deepcopy(payload)
        prepared["model"] = upstream_model
        prepared["stream"] = bool(prepared.get("stream", False))

        if endpoint == "/chat/completions":
            prepared.setdefault("max_tokens", self.max_output_tokens)
            # Ollama's OpenAI compatibility exposes reasoning control for chat completions.
            prepared.setdefault("reasoning_effort", self.reasoning_effort)
        elif endpoint == "/responses":
            prepared.setdefault("max_output_tokens", self.max_output_tokens)

        return prepared
