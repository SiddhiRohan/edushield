# QuantumLeap 2026 ICCP - Responsible AI Connector
# Client: login + chat UI. All AI calls through ICCP (no direct API).
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from config import get_settings
from database.database import init_db, get_db, async_session
from database.models import Person
from auth import verify_password, create_access_token
from server.faiss_endpoints import router as rag_router
from server.chat import router as chat_router
from server import chat as chat_module
from server import faiss_endpoints as faiss_module

STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
FAISS_INDEX = DATA_DIR / "faiss_index"


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str  # admin | teacher | student


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db(settings.database_url)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    # Optional: build FAISS index if PDFs exist and index missing
    if not FAISS_INDEX.exists() and any(PDF_DIR.glob("*.pdf")):
        try:
            from server.rag import build_faiss_index
            build_faiss_index(PDF_DIR, FAISS_INDEX)
        except Exception as e:
            print(f"FAISS index not built: {e}")
    # Inject config into server modules
    chat_module.FAISS_INDEX_PATH = FAISS_INDEX
    chat_module.OPENAI_BASE_URL = getattr(settings, "openai_base_url", "http://localhost:11434/v1")
    chat_module.OPENAI_API_KEY = getattr(settings, "openai_api_key", "") or "ollama"
    faiss_module.FAISS_INDEX_PATH = FAISS_INDEX
    faiss_module.PDF_DIR = PDF_DIR
    yield
    # shutdown
    pass


# Valid app URL for browser (never use 0.0.0.0 in the browser)
APP_URL = "http://localhost:8000"

app = FastAPI(
    title="QuantumLeap ICCP Connector",
    description="Build Your First Responsible AI Connector - All AI calls through ICCP",
    lifespan=lifespan,
    servers=[{"url": APP_URL, "description": "Local (use this in your browser)"}],
)

# Mount FastAPI-MCP so server exposes tools at /mcp (ICCP still gates all access)
try:
    from fastapi_mcp import FastApiMCP
    mcp = FastApiMCP(app)
    mcp.mount_http()
except Exception:
    pass  # optional: run without MCP mount

# Static files (login + chat UI)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    """Serve login page."""
    if STATIC_DIR.exists():
        login = STATIC_DIR / "login.html"
        if login.exists():
            return FileResponse(login)
    return {"message": "QuantumLeap ICCP - use /static/login.html to log in"}


@app.get("/chat")
async def chat_page():
    """Serve chat interface (after login)."""
    if STATIC_DIR.exists():
        chat = STATIC_DIR / "chat.html"
        if chat.exists():
            return FileResponse(chat)
    return {"message": "Log in first, then open /chat"}


@app.post("/api/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Login: username, password, role. Returns JWT for Identity Scope (ICCP)."""
    async with async_session() as session:
        r = await session.execute(
            select(Person).where(Person.username == body.username)
        )
        person = r.scalar_one_or_none()
    if not person or not verify_password(body.password, person.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if person.role != body.role:
        raise HTTPException(status_code=403, detail="Role does not match account")
    token = create_access_token(
        {"sub": person.username, "username": person.username, "role": person.role}
    )
    return LoginResponse(
        access_token=token,
        role=person.role,
        user_id=person.username,
    )


# API routes (RAG + Chat) - all require auth → Identity Scope → ICCP
app.include_router(rag_router)
app.include_router(chat_router)


@app.get("/api/audit/sample")
async def audit_sample():
    """Deliverable: audit log sample (no sensitive data)."""
    from iccp.audit import get_audit_sample
    return {"entries": get_audit_sample(20)}


@app.get("/api/iccp/context-packet-example")
async def context_packet_example():
    """Deliverable: example Context Packet structure."""
    from iccp import build_context_packet, IdentityScope, RESOURCE_GRADES, RESOURCE_CLASSES
    scope = IdentityScope(user_id="u123", role="teacher", clearance="FERPA-Authorized")
    packet = build_context_packet(scope, requested_resources=[RESOURCE_GRADES, RESOURCE_CLASSES])
    return packet.model_dump()


if __name__ == "__main__":
    import os
    import uvicorn
    # Bind to localhost so the link works in the browser (never 0.0.0.0)
    host = os.environ.get("UVICORN_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    url = f"http://localhost:{port}"
    print("\n" + "=" * 50)
    print("  QuantumLeap – open in your browser:")
    print(f"  {url}")
    print("  (Do NOT use http://0.0.0.0:8000)")
    print("=" * 50 + "\n")
    # reload=False so the host is not overridden by the reloader (which can show 0.0.0.0)
    uvicorn.run("main:app", host=host, port=port, reload=False)
