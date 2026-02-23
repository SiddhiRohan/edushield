# QuantumLeap - Resource descriptors and policy (ICCP)
from .models import ResourceDescriptor

# Resource IDs used in policy
RESOURCE_PERSONS = "persons"
RESOURCE_FINANCIAL = "financial_info"
RESOURCE_GRADES = "grades"
RESOURCE_CLASSES = "classes"
RESOURCE_RAG_DOCS = "rag_documents"

# Registry of resource descriptors (origin, sensitivity, TTL, allowed_roles)
RESOURCE_DESCRIPTORS: dict[str, ResourceDescriptor] = {
    RESOURCE_PERSONS: ResourceDescriptor(
        resource_id=RESOURCE_PERSONS,
        origin="QuantumLeap_SIS",
        sensitivity="PII",
        ttl_seconds=300,
        allowed_roles=["admin"],
    ),
    RESOURCE_FINANCIAL: ResourceDescriptor(
        resource_id=RESOURCE_FINANCIAL,
        origin="QuantumLeap_SIS",
        sensitivity="FERPA",
        ttl_seconds=300,
        allowed_roles=["admin", "teacher"],  # teacher: own salary only (enforced in code)
    ),
    RESOURCE_GRADES: ResourceDescriptor(
        resource_id=RESOURCE_GRADES,
        origin="QuantumLeap_SIS",
        sensitivity="FERPA",
        ttl_seconds=300,
        allowed_roles=["admin", "teacher"],
    ),
    RESOURCE_CLASSES: ResourceDescriptor(
        resource_id=RESOURCE_CLASSES,
        origin="QuantumLeap_SIS",
        sensitivity="internal",
        ttl_seconds=300,
        allowed_roles=["admin", "teacher", "student"],
    ),
    RESOURCE_RAG_DOCS: ResourceDescriptor(
        resource_id=RESOURCE_RAG_DOCS,
        origin="QuantumLeap_RAG",
        sensitivity="internal",
        ttl_seconds=300,
        allowed_roles=["admin", "teacher", "student"],
    ),
}

# Prohibited resource combination: e.g. grades + financial together for non-admin
PROHIBITED_COMBINATIONS: list[tuple[str, str]] = [
    # (resource_a, resource_b) - cannot access both in same request for certain roles
    # Enforced per-role in policy layer
]

# Masking rules: which fields to mask for which role (applied when returning data)
# e.g. financial.amount -> "***" for teacher when viewing others
MASKING_RULES: dict[str, dict[str, list[str]]] = {
    "teacher": {
        RESOURCE_FINANCIAL: ["amount", "description"],  # mask unless own record
    },
}
