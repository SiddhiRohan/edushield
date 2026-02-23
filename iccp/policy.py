# QuantumLeap - Policy enforcement (ICCP: Institution > Role > User)
import hashlib
import uuid
from .models import IdentityScope, ContextPacket, ModelDescriptor, PolicyDecision, AuditLogEntry
from .resources import (
    RESOURCE_PERSONS,
    RESOURCE_FINANCIAL,
    RESOURCE_GRADES,
    RESOURCE_CLASSES,
    RESOURCE_RAG_DOCS,
    RESOURCE_DESCRIPTORS,
    PROHIBITED_COMBINATIONS,
)

# Default model descriptor for our LLM
DEFAULT_MODEL = ModelDescriptor(
    model_id="quantumleap-connector",
    provider="QuantumLeap",
    compliance_classification="internal",
    risk_level="low",
)


def _policy_hash(identity: IdentityScope, authorized: list[str]) -> str:
    raw = f"{identity.role}:{','.join(sorted(authorized))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def enforce_policy(
    identity: IdentityScope,
    requested_resources: list[str],
    user_id_for_data: int | None = None,
) -> tuple[list[str], PolicyDecision, str]:
    """
    Enforce precedence: Institution > Role > User.
    Returns (authorized_resource_ids, decision, reason).
    """
    role = identity.role
    authorized: list[str] = []

    # Institution-level: base allowed resources per role
    if role == "admin":
        authorized = [RESOURCE_PERSONS, RESOURCE_FINANCIAL, RESOURCE_GRADES, RESOURCE_CLASSES, RESOURCE_RAG_DOCS]
    elif role == "teacher":
        authorized = [RESOURCE_GRADES, RESOURCE_CLASSES, RESOURCE_FINANCIAL, RESOURCE_RAG_DOCS]
        # Role restriction: teacher can only see own salary for financial (enforced when querying, not here)
    elif role == "student":
        authorized = [RESOURCE_CLASSES, RESOURCE_RAG_DOCS]
        # Student: only their own classes (filter by person_id in query layer)
    else:
        return [], PolicyDecision.DENY, "unknown_role"

    # Restrict to only what was requested and allowed
    allowed_set = set(authorized)
    requested_set = set(requested_resources)
    final = list(allowed_set & requested_set) if requested_set else list(allowed_set)

    # Prohibited combination: student must not get grades (they are not in allowed for student)
    # Teacher: financial only for self - we don't revoke RESOURCE_FINANCIAL here; we filter rows in DB layer
    if role == "student" and (RESOURCE_GRADES in final or RESOURCE_FINANCIAL in final):
        final = [r for r in final if r not in (RESOURCE_GRADES, RESOURCE_FINANCIAL)]
    if role == "teacher" and RESOURCE_PERSONS in final:
        final = [r for r in final if r != RESOURCE_PERSONS]

    if not final and requested_resources:
        return [], PolicyDecision.DENY, "no_authorized_resources"
    decision = PolicyDecision.ALLOW
    reason = "ok"
    return final, decision, reason


def build_context_packet(
    identity: IdentityScope,
    trace_id: str | None = None,
    requested_resources: list[str] | None = None,
) -> ContextPacket:
    """Build a valid Context Packet for a request; enforces policy and sets authorized_resources."""
    trace_id = trace_id or str(uuid.uuid4())
    requested_resources = requested_resources or [
        RESOURCE_CLASSES,
        RESOURCE_GRADES,
        RESOURCE_FINANCIAL,
        RESOURCE_PERSONS,
        RESOURCE_RAG_DOCS,
    ]
    authorized, decision, _ = enforce_policy(identity, requested_resources)
    policy_hash = _policy_hash(identity, authorized)
    return ContextPacket(
        ccp_version="1.0",
        trace_id=trace_id,
        identity_scope=identity,
        selected_model=DEFAULT_MODEL,
        authorized_resources=authorized,
        context_constraints={"policy_decision": decision.value},
        policy_hash=policy_hash,
    )


def create_audit_entry(
    trace_id: str,
    role: str,
    model_invoked: str | None,
    resources_accessed: list[str],
    policy_decision: PolicyDecision,
    details: dict | None = None,
) -> AuditLogEntry:
    return AuditLogEntry(
        trace_id=trace_id,
        role=role,
        model_invoked=model_invoked,
        resources_accessed=resources_accessed,
        policy_decision=policy_decision,
        details=details or {},
    )
