"""
Extra API routes — audit log, context packet, log file download.
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from iccp_engine import get_audit_log, get_audit_log_for_trace, AUDIT_LOG_FILE

router = APIRouter()
_context_packets: dict[str, dict] = {}


def store_context_packet(trace_id: str, packet: dict):
    _context_packets[trace_id] = packet


# ============ AUDIT LOG ============

@router.get("/audit-log")
async def get_full_audit_log():
    """View all audit entries (sanitized, no raw PII)."""
    log = get_audit_log()
    return {"total_entries": len(log), "entries": log}


@router.get("/audit-log/{trace_id}")
async def get_audit_entry(trace_id: str):
    """View a single audit entry by trace ID."""
    entry = get_audit_log_for_trace(trace_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return entry


@router.get("/audit-log-file")
async def download_audit_log_file():
    """Download the raw .jsonl audit log file (for judges)."""
    if not AUDIT_LOG_FILE.exists():
        raise HTTPException(status_code=404, detail="No audit log file yet. Make some queries first.")
    return FileResponse(
        path=str(AUDIT_LOG_FILE),
        filename="audit_log.jsonl",
        media_type="application/json",
    )


# ============ CONTEXT PACKET ============

@router.get("/context-packet/{trace_id}")
async def get_context_packet(trace_id: str):
    """View the CCP v1.0 Context Packet for a trace."""
    packet = _context_packets.get(trace_id)
    if not packet:
        raise HTTPException(status_code=404, detail=f"Context packet for {trace_id} not found")
    return packet


# ============ DEMO UTILS ============

@router.get("/demo/roles")
async def list_demo_roles():
    return {
        "roles": [
            {"user_id": "u101", "role": "Admin", "label": "Dean Robert Torres",
             "clearance": "Full-Access", "access": "All 4 tables"},
            {"user_id": "u202", "role": "Teacher", "label": "Dr. Sarah Chen",
             "clearance": "Department-Scoped", "access": "Grades, classes, own salary"},
            {"user_id": "u303", "role": "Student", "label": "Alex Rivera",
             "clearance": "Self-Scoped", "access": "Peer classes, own tuition"},
        ]
    }
