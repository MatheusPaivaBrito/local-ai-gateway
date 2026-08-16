import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import openai_error
from app.domains.rag.schemas import IngestDocumentRequest, SearchRagRequest
from app.http.dependencies import AuthDep, require_admin

router = APIRouter()


def _rag_or_error(request: Request):
    rag = request.app.state.rag
    if rag is None:
        return None, openai_error(
            503,
            "RAG is disabled.",
            error_type="server_error",
            code="rag_disabled",
        )
    return rag, None


@router.get("/admin/rag/collections")
async def list_collections(request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    rag, error = _rag_or_error(request)
    if error is not None:
        return error
    try:
        collections = await rag.store.list_collections()
    except Exception as exc:
        return openai_error(
            502,
            f"Qdrant unavailable: {exc}",
            error_type="upstream_error",
            code="qdrant_unavailable",
            headers=auth.rate_limit.headers(),
        )
    return JSONResponse(
        {
            "collections": collections,
            "default_collection": rag.default_collection,
            "embedding_model": rag.embeddings.model,
        },
        headers=auth.rate_limit.headers(),
    )


@router.post("/admin/rag/documents")
async def ingest_document(body: IngestDocumentRequest, request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    denied = require_admin(request, auth)
    if denied is not None:
        return denied
    rag, error = _rag_or_error(request)
    if error is not None:
        return error
    try:
        result = await rag.ingest(
            text=body.text,
            collection=body.collection,
            source_id=body.source_id,
            metadata=body.metadata,
        )
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        return openai_error(
            502,
            f"RAG dependency rejected the request: {detail}",
            error_type="upstream_error",
            code="rag_dependency_error",
            headers=auth.rate_limit.headers(),
        )
    except ValueError as exc:
        return openai_error(
            400,
            str(exc),
            error_type="invalid_request_error",
            code="invalid_rag_document",
            headers=auth.rate_limit.headers(),
        )
    except Exception as exc:
        return openai_error(
            502,
            f"RAG ingest failed: {exc}",
            error_type="upstream_error",
            code="rag_ingest_failed",
            headers=auth.rate_limit.headers(),
        )
    return JSONResponse(
        {
            "collection": result.collection,
            "source_id": result.source_id,
            "chunks": result.chunks,
            "embedding_model": result.embedding_model,
        },
        status_code=201,
        headers=auth.rate_limit.headers(),
    )


@router.post("/admin/rag/search")
async def search_rag(body: SearchRagRequest, request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    rag, error = _rag_or_error(request)
    if error is not None:
        return error
    try:
        hits = await rag.search(
            query=body.query,
            collection=body.collection,
            limit=body.limit,
        )
    except Exception as exc:
        return openai_error(
            502,
            f"RAG search failed: {exc}",
            error_type="upstream_error",
            code="rag_search_failed",
            headers=auth.rate_limit.headers(),
        )
    return JSONResponse(
        {
            "hits": [
                {"id": hit.id, "score": hit.score, "text": hit.text, "metadata": hit.metadata}
                for hit in hits
            ]
        },
        headers=auth.rate_limit.headers(),
    )
