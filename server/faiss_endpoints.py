# QuantumLeap - FAISS/RAG endpoints (used only after ICCP authorizes)
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth
from iccp import IdentityScope, build_context_packet, create_audit_entry, PolicyDecision
from iccp.audit import log_audit
from iccp.resources import RESOURCE_RAG_DOCS
from server.rag import search_faiss, build_faiss_index

# These will be set by main app (config)
FAISS_INDEX_PATH = Path("./data/faiss_index")
PDF_DIR = Path("./data/pdfs")

router = APIRouter(prefix="/api/rag", tags=["RAG"])


class RAGQuery(BaseModel):
    query: str
    top_k: int = 5


class RAGResponse(BaseModel):
    chunks: list[str]
    trace_id: str


@router.post("/search", response_model=RAGResponse)
async def search(
    body: RAGQuery,
    identity: IdentityScope = Depends(require_auth),
):
    # All AI/RAG access through ICCP: build context packet and authorize
    packet = build_context_packet(identity, requested_resources=[RESOURCE_RAG_DOCS])
    if RESOURCE_RAG_DOCS not in packet.authorized_resources:
        log_audit(create_audit_entry(
            packet.trace_id, identity.role, None, [], PolicyDecision.DENY,
            details={"reason": "rag_not_authorized"},
        ))
        raise HTTPException(status_code=403, detail="RAG access not authorized for your role")
    chunks = search_faiss(body.query, FAISS_INDEX_PATH, top_k=body.top_k)
    log_audit(create_audit_entry(
        packet.trace_id, identity.role, "rag_search",
        [RESOURCE_RAG_DOCS], PolicyDecision.ALLOW,
        details={"top_k": body.top_k},
    ))
    return RAGResponse(chunks=chunks, trace_id=packet.trace_id)


@router.post("/build-index")
async def build_index(identity: IdentityScope = Depends(require_auth)):
    """Build or rebuild FAISS index from PDFs (admin only in production)."""
    packet = build_context_packet(identity, requested_resources=[RESOURCE_RAG_DOCS])
    if identity.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can build index")
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    build_faiss_index(PDF_DIR, FAISS_INDEX_PATH)
    return {"status": "ok", "trace_id": packet.trace_id}
