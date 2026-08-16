from app.domains.inference.service import extract_assistant_text


def test_extract_assistant_text_from_chat_completion() -> None:
    payload = {"choices": [{"message": {"content": "ok"}}]}
    assert extract_assistant_text(payload) == "ok"


def test_extract_assistant_text_from_responses() -> None:
    payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}]}
    assert extract_assistant_text(payload) == "ok"
