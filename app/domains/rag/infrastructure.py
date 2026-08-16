from typing import Any

import httpx


class OllamaEmbeddingClient:
    def __init__(self, base_url: str, *, model: str, keep_alive: str) -> None:
        self.model = model
        self.keep_alive = keep_alive
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(180.0, connect=5.0),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.post(
            "/api/embed",
            json={
                "model": self.model,
                "input": texts,
                "keep_alive": self.keep_alive,
            },
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings") or []
        if len(embeddings) != len(texts):
            raise RuntimeError("Ollama returned an unexpected number of embeddings")
        return [[float(value) for value in vector] for vector in embeddings]


class QdrantVectorStore:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def ready(self) -> bool:
        try:
            response = await self.client.get("/readyz", timeout=3.0)
            return response.is_success
        except Exception:
            return False

    async def list_collections(self) -> list[str]:
        response = await self.client.get("/collections")
        response.raise_for_status()
        payload = response.json()
        collections = (payload.get("result") or {}).get("collections") or []
        return sorted(str(item.get("name")) for item in collections if item.get("name"))

    async def ensure_collection(self, collection: str, vector_size: int) -> None:
        response = await self.client.get(f"/collections/{collection}")
        if response.status_code == 404:
            created = await self.client.put(
                f"/collections/{collection}",
                json={"vectors": {"size": vector_size, "distance": "Cosine"}},
            )
            created.raise_for_status()
            return
        response.raise_for_status()

        payload = response.json().get("result") or {}
        vectors = ((payload.get("config") or {}).get("params") or {}).get("vectors") or {}
        existing_size = vectors.get("size") if isinstance(vectors, dict) else None
        if existing_size is not None and int(existing_size) != vector_size:
            raise ValueError(
                f"Collection '{collection}' uses vectors of size {existing_size}, "
                f"but the configured embedding model returned {vector_size}."
            )

    async def upsert(self, collection: str, points: list[dict[str, Any]]) -> None:
        response = await self.client.put(
            f"/collections/{collection}/points",
            params={"wait": "true"},
            json={"points": points},
        )
        response.raise_for_status()

    async def query(
        self,
        collection: str,
        vector: list[float],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        response = await self.client.post(
            f"/collections/{collection}/points/query",
            json={
                "query": vector,
                "limit": limit,
                "with_payload": True,
                "with_vectors": False,
            },
        )
        response.raise_for_status()
        result = response.json().get("result") or {}
        if isinstance(result, dict):
            return list(result.get("points") or [])
        if isinstance(result, list):
            return result
        return []
