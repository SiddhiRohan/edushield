# QuantumLeap - Chat endpoint (all AI calls through ICCP)
#
# LLM: OpenAI-compatible API. Default = Ollama at http://localhost:11434/v1, model "llama3.2".
#      Override via .env: OPENAI_BASE_URL, OPENAI_API_KEY (e.g. OpenAI, Azure, or another Ollama URL).
#
# Data: (1) SQLite DB quantumleap.db: persons, financial_info, grades, classes, enrollments
#       (2) RAG: PDFs in data/pdfs/, indexed in FAISS at data/faiss_index (optional).
#       Role-based filtering in server/data_access.py; only authorized data is sent to the LLM.
#
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth
from database.database import get_db
from server.data_access import gather_authorized_data, get_person_id_by_username
from iccp import (
    IdentityScope,
    build_context_packet,
    create_audit_entry,
    PolicyDecision,
    RESOURCE_CLASSES,
    RESOURCE_GRADES,
    RESOURCE_FINANCIAL,
    RESOURCE_PERSONS,
    RESOURCE_RAG_DOCS,
)
from iccp.audit import log_audit
from server.rag import search_faiss

# Config: set from main app on startup
FAISS_INDEX_PATH = __import__("pathlib").Path("./data/faiss_index")
OPENAI_BASE_URL = "http://localhost:11434/v1"
OPENAI_API_KEY = ""

router = APIRouter(prefix="/api", tags=["Chat"])


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    trace_id: str


def _build_context_string(data: dict, rag_chunks: list[str]) -> str:
    parts = []
    if data.get("classes"):
        parts.append("Classes: " + str(data["classes"]))
    if data.get("grades"):
        parts.append("Grades: " + str(data["grades"]))
    if data.get("financial"):
        parts.append("Financial (authorized): " + str(data["financial"]))
    if data.get("persons"):
        parts.append("Persons: " + str(data["persons"]))
    if rag_chunks:
        parts.append("Relevant documents (RAG): " + "\n---\n".join(rag_chunks[:3]))
    return "\n\n".join(parts) if parts else "No authorized data available for this query."


async def _call_llm(user_message: str, context: str, trace_id: str) -> str:
    """Call LLM with context only (no direct API from client). Uses OpenAI-compatible API (default: Ollama)."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=OPENAI_BASE_URL or "http://localhost:11434/v1", api_key=OPENAI_API_KEY or "ollama")
        # Model: default "llama3.2" for Ollama; set OPENAI_BASE_URL for another provider
        response = await client.chat.completions.create(
            model="llama3.2",
            messages=[
                {"role": "system", "content": "You are a helpful assistant with access to authorized institutional data. Answer only based on the context provided. If the context does not contain the answer, say so. Do not make up data."},
                {"role": "user", "content": f"Context:\n{context}\n\nUser question: {user_message}"},
            ],
            max_tokens=500,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        return f"[LLM unavailable: {e}. This is a placeholder reply. Context was: {context[:200]}...]"


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatMessage,
    identity: IdentityScope = Depends(require_auth),
    db=Depends(get_db),
):
    # 1) Build Context Packet (ICCP) and get authorized resources
    trace_id = str(uuid.uuid4())
    packet = build_context_packet(
        identity,
        trace_id=trace_id,
        requested_resources=[RESOURCE_CLASSES, RESOURCE_GRADES, RESOURCE_FINANCIAL, RESOURCE_PERSONS, RESOURCE_RAG_DOCS],
    )
    if not packet.authorized_resources:
        log_audit(create_audit_entry(trace_id, identity.role, None, [], PolicyDecision.DENY, details={"reason": "no_resources"}))
        raise HTTPException(status_code=403, detail="No resources authorized for your role")

    # 2) Gather authorized DB data (least privilege)
    person_id = await get_person_id_by_username(db, identity.user_id)
    person_id = person_id or 0
    data = await gather_authorized_data(db, identity, packet.authorized_resources, person_id)

    # 3) RAG: search if authorized
    rag_chunks = []
    if RESOURCE_RAG_DOCS in packet.authorized_resources and FAISS_INDEX_PATH and FAISS_INDEX_PATH.exists():
        rag_chunks = search_faiss(body.message, FAISS_INDEX_PATH, top_k=3)

    # 4) Build context string and call LLM (all AI through ICCP - no direct client call)
    context = _build_context_string(data, rag_chunks)
    reply = await _call_llm(body.message, context, trace_id)

    # 5) Audit
    log_audit(create_audit_entry(
        trace_id, identity.role, "chat_llm",
        packet.authorized_resources, PolicyDecision.ALLOW,
        details={"resources_used": list(data.keys()) + (["rag"] if rag_chunks else [])},
    ))
    return ChatResponse(reply=reply, trace_id=trace_id)
