# QuantumLeap - ICCP protocol objects (Quantum Leap 2026 Hackathon)
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# --- Identity Scope (Required component) ---
class IdentityScope(BaseModel):
    """Who is making the request: user_id, role, clearance, session context."""
    user_id: str = Field(..., description="Unique user identifier")
    role: str = Field(..., description="admin | teacher | student")
    clearance: str = Field(default="", description="e.g. FERPA-Authorized for education data")
    session_id: str | None = Field(default=None, description="Session for traceability")


# --- Resource Descriptor ---
class ResourceDescriptor(BaseModel):
    """Declares origin, sensitivity, TTL, and allowed roles for a resource."""
    resource_id: str
    origin: str = Field(..., description="Source system e.g. MockSIS")
    sensitivity: str = Field(..., description="e.g. FERPA, PII")
    ttl_seconds: int = Field(default=300, ge=0)
    allowed_roles: list[str] = Field(default_factory=list)


# --- Model Descriptor (for LLM) ---
class ModelDescriptor(BaseModel):
    model_id: str
    provider: str = "local"
    compliance_classification: str = "internal"
    risk_level: str = "low"


# --- Context Packet (Required: every data access request) ---
class ContextPacket(BaseModel):
    """Encapsulates context for each request; required for policy and audit."""
    ccp_version: str = Field(default="1.0", description="Context Control Protocol version")
    trace_id: str = Field(..., description="Unique trace for audit")
    identity_scope: IdentityScope
    selected_model: ModelDescriptor | None = None
    authorized_resources: list[str] = Field(default_factory=list, description="Resource IDs allowed for this request")
    context_constraints: dict[str, Any] = Field(default_factory=dict)
    policy_hash: str | None = Field(default=None, description="Hash of policy applied")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Policy decision for audit ---
class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    MASKED = "masked"


# --- Audit log entry (Required: every invocation logged) ---
class AuditLogEntry(BaseModel):
    trace_id: str
    role: str
    model_invoked: str | None = None
    resources_accessed: list[str] = Field(default_factory=list)
    policy_decision: PolicyDecision
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)
