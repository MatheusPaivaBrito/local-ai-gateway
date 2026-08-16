from app.domains.inference.policy import InferencePolicy


def test_chat_policy_disables_reasoning_and_caps_output_by_default() -> None:
    policy = InferencePolicy(max_output_tokens=256, reasoning_effort="none")
    payload = policy.apply("/chat/completions", {"model": "public", "messages": []}, "qwen3:4b")
    assert payload["model"] == "qwen3:4b"
    assert payload["max_tokens"] == 256
    assert payload["reasoning_effort"] == "none"


def test_policy_never_overrides_explicit_client_choice() -> None:
    policy = InferencePolicy(max_output_tokens=256, reasoning_effort="none")
    payload = policy.apply(
        "/chat/completions",
        {"model": "x", "messages": [], "max_tokens": 900, "reasoning_effort": "high"},
        "x",
    )
    assert payload["max_tokens"] == 900
    assert payload["reasoning_effort"] == "high"


def test_responses_policy_uses_max_output_tokens() -> None:
    policy = InferencePolicy(max_output_tokens=128, reasoning_effort="none")
    payload = policy.apply("/responses", {"model": "x", "input": "oi"}, "x")
    assert payload["max_output_tokens"] == 128
