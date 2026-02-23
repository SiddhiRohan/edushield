"""
SERVER — FastAPI + ICCP + Audit
Run: python -m uvicorn main:app --reload --port 8000
"""

import json
import os
import sys
import traceback
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from iccp_engine import ICCPEngine, shutdown_audit_logger
from endpoints import router as extra_router, store_context_packet

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
if api_key:
    print(f"✅ API key loaded (starts with: {api_key[:12]}...)", flush=True)
else:
    print("⚠️  No API key found — running in DEMO MODE", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 EduShield AI starting...", flush=True)
    yield
    shutdown_audit_logger()


app = FastAPI(title="EduShield AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extra_router)


class ChatRequest(BaseModel):
    user_id: str
    role: str
    message: str


class ChatResponse(BaseModel):
    response: str
    role: str
    access_level: str
    masked_fields: list[str]
    denied_resources: list[str]
    trace_id: str


DATA_PATH = Path(__file__).parent / "mock_sis_data.json"
with open(DATA_PATH, "r") as f:
    SIS_DATA = json.load(f)

print(f"✅ Loaded SIS: {len(SIS_DATA['persons'])} persons, "
      f"{len(SIS_DATA['financial_information'])} financial, "
      f"{len(SIS_DATA['grades'])} grades, "
      f"{len(SIS_DATA['classes'])} classes", flush=True)


def call_llm(user_message: str, filtered_context: str, role: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return (
            f"[DEMO MODE — No API key]\n\n"
            f"Your role ({role}) sees this ICCP-filtered data:\n\n"
            f"{filtered_context}"
        )

    try:
        print(f"📡 Calling Claude API for role={role}...", flush=True)

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = (
            f"You are EduShield AI, an ICCP-governed university assistant. "
            f"Current user role: {role}. "
            f"ONLY use the data below. Do NOT make up information. "
            f"If data shows [ACCESS DENIED] or is masked (***), tell the user their role cannot access it. "
            f"Be helpful and concise.\n\n"
            f"--- ICCP-FILTERED DATA ---\n{filtered_context}\n--- END ---"
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        result = response.content[0].text
        print(f"✅ Claude responded ({len(result)} chars)", flush=True)
        return result

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"\n❌ LLM ERROR: {error_msg}", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        # Return error details so we can debug
        return f"[AI Error: {error_msg}]"


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        print(f"\n📨 Chat: user={request.user_id}, role={request.role}, msg={request.message[:50]}", flush=True)

        iccp = ICCPEngine()
        iccp_result = iccp.process(
            user_id=request.user_id,
            role=request.role,
            sis_data=SIS_DATA,
            query=request.message,
        )

        store_context_packet(iccp_result["trace_id"], iccp_result["context_packet"])

        ai_response = call_llm(
            user_message=request.message,
            filtered_context=iccp_result["filtered_context"],
            role=request.role,
        )

        return ChatResponse(
            response=ai_response,
            role=request.role,
            access_level=iccp_result["access_level"],
            masked_fields=iccp_result["masked_fields"],
            denied_resources=iccp_result["denied_resources"],
            trace_id=iccp_result["trace_id"],
        )

    except Exception as e:
        print(f"\n❌ ENDPOINT ERROR: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        raise


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "tables": ["persons", "financial_information", "grades", "classes"],
        "iccp": "active",
        "audit_logger": "QueueHandler",
        "api_key_loaded": bool(os.getenv("ANTHROPIC_API_KEY")),
    }
