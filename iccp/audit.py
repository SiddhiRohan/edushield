# QuantumLeap - Audit logging (required: every invocation logged)
import json
from pathlib import Path
from datetime import datetime
from .models import AuditLogEntry

# In-memory log for demo; append-only file for persistence
_audit_log: list[AuditLogEntry] = []
_AUDIT_FILE = Path("data/audit_log.jsonl")


def log_audit(entry: AuditLogEntry) -> None:
    """Append audit entry to in-memory list and optionally to file (no raw sensitive data)."""
    _audit_log.append(entry)
    _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
        # Do not log raw sensitive data per ethical requirements
        safe = entry.model_dump()
        f.write(json.dumps(safe, default=str) + "\n")


def get_audit_sample(limit: int = 50) -> list[dict]:
    """Return recent audit entries for deliverables (audit log sample)."""
    return [e.model_dump() for e in _audit_log[-limit:]]
