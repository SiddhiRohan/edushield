# QuantumLeap 2026 – ICCP Responsible AI Connector

Web app with **login** (username, password, role), **chat** backed by a lightweight LLM, and **role-based access** to a database. All AI and data access goes through **ICCP** (Integrated Context Control Protocol); there are no direct client→LLM API calls.

## Roles & access

| Role    | Access |
|---------|--------|
| **Admin**  | All: persons, financial info, grades, classes, RAG documents |
| **Teacher**| Grades, classes, **own salary only**, RAG documents |
| **Student**| **Own classes only**, RAG documents (no grades, no financial) |

## Stack

- **Client:** FastAPI (serves HTML/JS), login page + chat UI
- **Server:** FastAPI (same app): ICCP gateway, RAG on PDF, FAISS endpoints, DB access
- **DB:** SQLite (dev): `persons`, `financial_info`, `grades`, `classes`, `enrollments`
- **RAG:** PDF → chunks → sentence-transformers → FAISS; search via `/api/rag/search`
- **LLM:** OpenAI-compatible API (e.g. Ollama at `http://localhost:11434/v1`); all calls go through the backend (ICCP), not from the browser

## Quick start

```bash
# Create venv and install
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Seed DB (admin, teacher1/2, student1/2/3 + classes, grades, financial)
python -m database.seed

# Run app
python main.py
```

Then open in your browser: **http://localhost:8000** (do not use http://0.0.0.0:8000).

- **Login:** http://localhost:8000/  
  Example: `admin` / `admin123` / Admin, or `teacher1` / `teach1` / Teacher, or `student1` / `stu1` / Student.
- **Chat:** After login you’re redirected to http://localhost:8000/chat . Ask about classes, grades (if allowed), or documents.

**LLM:** The app uses an **OpenAI-compatible** chat API. By default it calls **Ollama** at `http://localhost:11434/v1` with model **`llama3.2`**. Set `OPENAI_BASE_URL` and `OPENAI_API_KEY` in `.env` to use OpenAI, Azure, or another endpoint. If the LLM is unreachable, the app returns a placeholder reply.

**Data sources:** (1) **SQLite** `quantumleap.db` — tables `persons`, `financial_info`, `grades`, `classes`, `enrollments` (seed via `python -m database.seed`). (2) **RAG** — PDFs in `data/pdfs/`, FAISS index at `data/faiss_index` (build with `POST /api/rag/build-index` as admin). Only data allowed by the user’s role is sent to the LLM (see `server/data_access.py`).

## ICCP components (hackathon)

1. **Identity Scope** – `user_id`, `role`, `clearance` (e.g. FERPA-Authorized) from login/JWT.
2. **Resource descriptors** – `persons`, `financial_info`, `grades`, `classes`, `rag_documents` with origin, sensitivity, TTL, `allowed_roles`.
3. **Policy enforcement** – Precedence: Institution > Role > User; role restrictions and prohibited combinations (e.g. student cannot access grades/financial).
4. **Context Packet** – Built per request: `trace_id`, `identity_scope`, `authorized_resources`, `policy_hash`.
5. **Audit logging** – Every chat/RAG invocation logged (trace_id, role, resources, policy decision); no raw sensitive data in logs.

**Deliverables:**

- **Context Packet example:** `GET /api/iccp/context-packet-example`
- **Audit log sample:** `GET /api/audit/sample`

## Architecture (high level)

```
[Browser] → Login (username, password, role) → JWT
       → Chat UI → POST /api/chat (Bearer JWT)
                    ↓
              [FastAPI app]
                    ↓
         ICCP: Identity Scope + build Context Packet
                    ↓
         Policy: authorized_resources by role
                    ↓
         DB (role-scoped): classes, grades, financial, persons
         RAG (if allowed): POST /api/rag/search → FAISS
                    ↓
         LLM (server-side only) with allowed context
                    ↓
         Audit log (trace_id, role, resources, decision)
                    ↓
         Response → Browser
```

- **FAISS/RAG:** Put PDFs in `data/pdfs/`. Build index (admin): `POST /api/rag/build-index` with Bearer token. Query: `POST /api/rag/search` with `{"query": "...", "top_k": 5}`.

## Config

Copy `.env.example` to `.env` and set:

- `SECRET_KEY` – JWT signing
- `DATABASE_URL` – default `sqlite+aiosqlite:///./quantumleap.db`
- `OPENAI_BASE_URL`, `OPENAI_API_KEY` – for LLM (e.g. Ollama)

## Ethics & security

- **Least privilege:** Data access filtered by role and resource descriptors.
- **No sensitive data in logs:** Audit entries log trace_id, role, resources, decision only.
- **No direct AI calls from client:** All LLM and RAG use goes through the backend and ICCP.
