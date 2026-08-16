from collections.abc import AsyncIterator
from typing import Any

import httpx


class OllamaOpenAIClient:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=None,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def post(self, endpoint: str, payload: dict[str, Any]) -> httpx.Response:
        return await self.client.post(endpoint, json=payload)

    async def open_stream(self, endpoint: str, payload: dict[str, Any]) -> httpx.Response:
        request = self.client.build_request("POST", endpoint, json=payload)
        return await self.client.send(request, stream=True)

    @staticmethod
    async def iter_bytes(response: httpx.Response) -> AsyncIterator[bytes]:
        async for chunk in response.aiter_bytes():
            yield chunk
