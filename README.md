# 🛡️ EduShield AI

**ICCP-Governed University System**
Quantum Leap 2026 · ICCP Hackathon · Feb 24 · Coca-Cola Roxy, Atlanta

---

## What is EduShield?

EduShield AI is a responsible AI connector that uses the **Integrated Context Control Protocol (ICCP)** to govern what an AI model is allowed to see before it responds. It sits between users and the LLM, enforcing role-based access control over university records.

Three roles — **Admin**, **Teacher**, and **Student** — each see different data from the same system. ICCP ensures the AI never receives unauthorized information.

---

## Architecture

```
Users (Admin / Teacher / Student)
        ↓
   ICCP Engine
        ↓
  Mock SIS (4 Tables)
        ↓
   LLM (Claude API)
        ↓
    Audit Log
```

All AI calls pass through ICCP. No direct API calls allowed.

---

## Access Rules

| Table | Admin | Teacher | Student |
|-------|-------|---------|---------|
| Persons | All | All | All |
| Financial Info | All | Own salary only | Own tuition only |
| Grades | All | All | ❌ Denied |
| Classes | All | All | Peer view |

**SSN is always masked for every role** — institution-level policy.

---

## ICCP Components

### 1. Identity Scope
Defines who is making the request — user_id, role, clearance level, and session context.

### 2. Resource Descriptor
Defines each data table — origin system, sensitivity classification, TTL, and allowed roles.

### 3. Model Descriptor
Declares the AI model — model_id, provider, compliance certification, and risk level.

### 4. Policy Enforcement
Three-tier precedence: **Institution > Role > User**
- **Masking rule:** SSN → `***-**-****` for all roles
- **Role restriction:** Students cannot access the grades table
- **Prohibited combination:** Teacher + other people's financial records = DENY

### 5. Context Packet (CCP v1.0)
Every LLM call is wrapped in a Context Packet containing:
```json
{
  "ccp_version": "1.0",
  "trace_id": "tr-unique-id",
  "identity_scope": {},
  "selected_model": {},
  "authorized_resources": [],
  "context_constraints": {},
  "policy_hash": "sha256:..."
}
```

### 6. Audit Logger (QueueHandler)
Every invocation is logged with:
- trace_id, role, model invoked, resources accessed, resources denied, policy decision
- PII sanitized before writing — SSNs replaced with `[REDACTED]`, financial amounts scrubbed
- Three destinations: file (`logs/audit_log.jsonl`), memory (API), console (terminal)
- Non-blocking, thread-safe via Python's `QueueHandler + QueueListener`

---

## Ethical Requirements

| Requirement | Implementation |
|-------------|---------------|
| Least-privilege | Each role only sees what they need |
| Prevent sensitive field leakage | SSN masked, financial data scoped per role |
| No raw sensitive data in logs | PII sanitizer scrubs before write |
| TTL enforcement | Each resource has a TTL; data refreshed on expiry |
| Explainability | Every decision has a human-readable explanation |

---

## Project Structure

```
edushield/
├── frontend/
│   └── index.html              ← Login + Chat UI
│
└── server/
    ├── main.py                 ← FastAPI server + LLM connection
    ├── iccp_engine.py          ← ICCP governance engine
    ├── endpoints.py            ← Audit log + Context Packet API routes
    ├── mock_sis_data.json      ← Mock SIS data (3 users, 4 tables)
    ├── requirements.txt        ← Python dependencies
    └── .env                    ← API key (not committed)
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/edushield.git
cd edushield
```

### 2. Install dependencies

```bash
cd server
pip install -r requirements.txt
```

### 3. Add your API key (optional)

Create a `.env` file in `server/`:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Without an API key the app runs in demo mode — ICCP filtering still works, responses show filtered data directly.

### 4. Start the server

```bash
python -m uvicorn main:app --reload --port 8000
```

### 5. Start the frontend

In a new terminal:

```bash
cd frontend
python -m http.server 3000
```

### 6. Open the app

Go to http://localhost:3000

---

## Login Credentials

| User ID | Password | Name | Role |
|---------|----------|------|------|
| admin | admin | Robert Torres | Admin |
| teacher | teacher | Sarah Chen | Teacher |
| student | student | Alex Rivera | Student |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send a message (user_id, role, message) |
| `/health` | GET | Server status |
| `/audit-log` | GET | View all audit entries |
| `/audit-log/{trace_id}` | GET | View specific audit entry |
| `/audit-log-file` | GET | Download audit log as .jsonl |
| `/context-packet/{trace_id}` | GET | View CCP v1.0 packet |
| `/demo/roles` | GET | List available demo roles |
| `/docs` | GET | Interactive API documentation |

---

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript (no build step)
- **Backend:** Python, FastAPI, Uvicorn
- **AI Model:** Claude (Anthropic API) — called only through ICCP
- **Audit:** Python `logging.handlers.QueueHandler` + QueueListener
- **Data:** Mock SIS (JSON) — 4 tables, 3 users

---

## License

Built for Quantum Leap 2026 ICCP Hackathon.
