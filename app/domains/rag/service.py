import re
from typing import Any
from uuid import uuid4

from app.domains.rag.domain import RagHit, RagIngestResult
from app.domains.rag.infrastructure import OllamaEmbeddingClient, QdrantVectorStore

_COLLECTION_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def validate_collection_name(name: str) -> str:
    clean = name.strip()
    if not _COLLECTION_RE.fullmatch(clean):
        raise ValueError(
            "Collection must use only letters, numbers, '.', '_' or '-' and have at most 120 chars"
        )
    return clean


def chunk_text(text: str, *, size: int, overlap: int) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    size = max(size, 200)
    overlap = min(max(overlap, 0), size - 1)
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        if end < len(clean):
            # Prefer a natural boundary without allowing very small chunks.
            boundary = max(
                clean.rfind("\n", start + size // 2, end),
                clean.rfind(". ", start + size // 2, end),
            )
            if boundary > start:
                end = boundary + 1
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        start = max(start + 1, end - overlap)
    return chunks


class RagService:
    def __init__(
        self,
        *,
        embeddings: OllamaEmbeddingClient,
        store: QdrantVectorStore,
        default_collection: str,
        chunk_size: int,
        chunk_overlap: int,
        default_top_k: int,
    ) -> None:
        self.embeddings = embeddings
        self.store = store
        self.default_collection = validate_collection_name(default_collection)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.default_top_k = default_top_k

    async def ingest(
        self,
        *,
        text: str,
        collection: str | None = None,
        metadata: dict[str, Any] | None = None,
        source_id: str | None = None,
    ) -> RagIngestResult:
        target = validate_collection_name(collection or self.default_collection)
        chunks = chunk_text(text, size=self.chunk_size, overlap=self.chunk_overlap)
        if not chunks:
            raise ValueError("Document text cannot be empty")

        vectors = await self.embeddings.embed(chunks)
        if not vectors or not vectors[0]:
            raise RuntimeError("Embedding model returned an empty vector")
        vector_size = len(vectors[0])
        if any(len(vector) != vector_size for vector in vectors):
            raise RuntimeError("Embedding model returned inconsistent vector dimensions")

        await self.store.ensure_collection(target, vector_size)
        source = source_id or str(uuid4())
        safe_metadata = dict(metadata or {})
        points = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            points.append(
                {
                    "id": str(uuid4()),
                    "vector": vector,
                    "payload": {
                        "text": chunk,
                        "source_id": source,
                        "chunk_index": index,
                        "metadata": safe_metadata,
                    },
                }
            )
        await self.store.upsert(target, points)
        return RagIngestResult(
            collection=target,
            source_id=source,
            chunks=len(points),
            embedding_model=self.embeddings.model,
        )

    async def search(
        self,
        *,
        query: str,
        collection: str | None = None,
        limit: int | None = None,
    ) -> list[RagHit]:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Search query cannot be empty")
        target = validate_collection_name(collection or self.default_collection)
        top_k = min(max(limit or self.default_top_k, 1), 20)
        vector = (await self.embeddings.embed([clean_query]))[0]
        points = await self.store.query(target, vector, limit=top_k)
        hits: list[RagHit] = []
        for point in points:
            payload = dict(point.get("payload") or {})
            hits.append(
                RagHit(
                    id=str(point.get("id", "")),
                    score=float(point.get("score") or 0.0),
                    text=str(payload.get("text") or ""),
                    metadata=dict(payload.get("metadata") or {}),
                )
            )
        return hits

    async def context_for(
        self,
        *,
        query: str,
        collection: str | None,
        limit: int | None = None,
    ) -> tuple[str, list[RagHit]]:
        hits = await self.search(query=query, collection=collection, limit=limit)
        if not hits:
            return "", []
        blocks = [
            f"[Contexto {index} | score={hit.score:.4f}]\n{hit.text}"
            for index, hit in enumerate(hits, start=1)
        ]
        return "\n\n".join(blocks), hits
