import os

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("LOCAL_AI_API_KEY", "sk-local-dev-change-me"),
    base_url=os.getenv("LOCAL_AI_BASE_URL", "http://localhost:8001/v1"),
)
models = list(client.models.list().data)
if not models:
    raise SystemExit("No Ollama model installed. Install one from /ui or make pull-model MODEL=...")

model = models[0].id
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Diga apenas: funcionando"}],
    max_tokens=16,
    extra_body={"reasoning_effort": "none"},
)
print(response.choices[0].message.content)
