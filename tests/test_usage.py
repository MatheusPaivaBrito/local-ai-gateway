from app.domains.usage.domain import TokenUsage, extract_usage


def test_usage_accepts_responses_api_fields() -> None:
    assert extract_usage(
        {"usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}
    ) == TokenUsage(10, 5, 15)


def test_usage_accepts_chat_completions_fields() -> None:
    assert extract_usage(
        {"usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}
    ) == TokenUsage(11, 7, 18)
