"""
==============================================
ICCP ENGINE — Integrated Context Control Protocol
==============================================
3 Users: Admin (Robert Torres), Teacher (Sarah Chen), Student (Alex Rivera)
4 Tables: Persons, Financial Information, Grades, Classes

Access Rules:
  - Admin:   sees EVERYTHING
  - Teacher: sees grades, classes, and ONLY their own salary
  - Student: sees peer classes, their OWN financial info, but nothing else
"""

import uuid, hashlib, json, copy, time, re, logging, logging.handlers, queue
from datetime import datetime, timezone
from pathlib import Path


# =============================================
# AUDIT LOGGER — QueueHandler Pipeline
# =============================================

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
AUDIT_LOG_FILE = LOG_DIR / "audit_log.jsonl"
AUDIT_LOG_MEMORY: list[dict] = []
SSN_PATTERN = re.compile(r"\d{3}-\d{2}-\d{4}")

def sanitize_for_log(data: dict) -> dict:
    sanitized = copy.deepcopy(data)
    def _scrub(obj):
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                val = obj[key]
                if key.lower() in ("ssn", "social_security"): obj[key] = "[REDACTED]"
                elif key.lower() in ("annual_salary", "amount_due", "amount_paid", "balance"): obj[key] = "[REDACTED-FINANCIAL]"
                elif isinstance(val, str): obj[key] = SSN_PATTERN.sub("[REDACTED-SSN]", val)
                else: _scrub(val)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str): obj[i] = SSN_PATTERN.sub("[REDACTED-SSN]", item)
                else: _scrub(item)
    _scrub(sanitized)
    return sanitized

class AuditFileHandler(logging.Handler):
    def __init__(self, filepath): super().__init__(); self.filepath = filepath
    def emit(self, record):
        try:
            e = getattr(record, "audit_entry", None)
            if e:
                with open(self.filepath, "a") as f: f.write(json.dumps(sanitize_for_log(e), default=str) + "\n")
        except: self.handleError(record)

class AuditMemoryHandler(logging.Handler):
    def emit(self, record):
        try:
            e = getattr(record, "audit_entry", None)
            if e: AUDIT_LOG_MEMORY.append(sanitize_for_log(e))
        except: self.handleError(record)

class AuditConsoleHandler(logging.Handler):
    def emit(self, record):
        try:
            e = getattr(record, "audit_entry", None)
            if not e: return
            s = e.get("session_context", {})
            print(f"\n{'='*60}")
            print(f"  AUDIT LOG — {e['trace_id']}")
            print(f"{'='*60}")
            print(f"  Timestamp : {e['timestamp']}")
            print(f"  User      : {e['user_id']} | Role: {e['role']} | Clearance: {e['clearance']}")
            print(f"  Session   : {s.get('session_id','N/A')}")
            print(f"  Model     : {e['model_invoked']}")
            print(f"  Decision  : {e['policy_decision']}")
            print(f"  Accessed  : {e['resources_accessed']}")
            print(f"  Denied    : {e['resources_denied']}")
            print(f"  Masked    : {e['fields_masked']}")
            print(f"  TTL       : {e.get('ttl_status',{})}")
            print(f"  Explain   : {e['explanation']}")
            print(f"{'='*60}")
        except: self.handleError(record)

_audit_queue = queue.Queue(-1)
_audit_logger = logging.getLogger("iccp.audit")
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False
_audit_logger.addHandler(logging.handlers.QueueHandler(_audit_queue))

_queue_listener = logging.handlers.QueueListener(
    _audit_queue, AuditFileHandler(AUDIT_LOG_FILE),
    AuditMemoryHandler(), AuditConsoleHandler(), respect_handler_level=True,
)
_queue_listener.start()
print(f"✅ Audit logger ready (QueueHandler → {AUDIT_LOG_FILE})")

def log_audit_entry(trace_id, identity_scope, session_context, model_descriptor,
                    resources_accessed, resources_denied, fields_masked,
                    policy_decision, explanation, ttl_status) -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "user_id": identity_scope["user_id"],
        "role": identity_scope["role"],
        "clearance": identity_scope["clearance"],
        "session_context": {
            "session_id": session_context.get("session_id", ""),
            "ip_address": session_context.get("ip_address", ""),
            "request_timestamp": session_context.get("request_timestamp", ""),
        },
        "model_invoked": model_descriptor["model_id"],
        "resources_accessed": resources_accessed,
        "resources_denied": resources_denied,
        "fields_masked": fields_masked,
        "policy_decision": policy_decision,
        "explanation": explanation,
        "ttl_status": ttl_status,
    }
    record = logging.LogRecord(name="iccp.audit", level=logging.INFO, pathname="", lineno=0, msg="audit", args=(), exc_info=None)
    record.audit_entry = entry
    _audit_logger.handle(record)
    return entry

def get_audit_log(): return AUDIT_LOG_MEMORY
def get_audit_log_for_trace(trace_id):
    for e in AUDIT_LOG_MEMORY:
        if e["trace_id"] == trace_id: return e
    return None
def shutdown_audit_logger(): _queue_listener.stop()


# =============================================
# PROTOCOL OBJECTS
# =============================================

def build_identity_scope(user_id: str, role: str, session_context: dict = None) -> dict:
    CLEARANCE = {"Admin": "Full-Access", "Teacher": "Department-Scoped", "Student": "Self-Scoped"}
    if not session_context: session_context = {}
    return {
        "user_id": user_id, "role": role,
        "clearance": CLEARANCE.get(role, "Unauthorized"),
        "session_context": {
            "session_id": session_context.get("session_id", f"sess-{uuid.uuid4().hex[:8]}"),
            "ip_address": session_context.get("ip_address", "0.0.0.0"),
            "request_timestamp": datetime.now(timezone.utc).isoformat(),
            "user_agent": session_context.get("user_agent", "EduShield/1.0"),
        },
    }

def build_resource_descriptor(resource_id: str) -> dict:
    REG = {
        "persons":               {"resource_id": "persons",               "origin": "MockSIS", "sensitivity": "FERPA",           "ttl": 300, "allowed_roles": ["Admin","Teacher","Student"]},
        "financial_information":  {"resource_id": "financial_information", "origin": "MockSIS", "sensitivity": "FERPA-Financial", "ttl": 120, "allowed_roles": ["Admin"]},
        "grades":                {"resource_id": "grades",                "origin": "MockSIS", "sensitivity": "FERPA",           "ttl": 300, "allowed_roles": ["Admin","Teacher"]},
        "classes":               {"resource_id": "classes",               "origin": "MockSIS", "sensitivity": "Institutional",   "ttl": 600, "allowed_roles": ["Admin","Teacher","Student"]},
    }
    return REG.get(resource_id, {"resource_id": resource_id, "origin": "Unknown", "sensitivity": "Restricted", "ttl": 0, "allowed_roles": []})

def build_model_descriptor() -> dict:
    return {"model_id": "claude-sonnet-4-20250514", "provider": "Anthropic", "compliance": "SOC2-certified", "risk_level": "low"}


# =============================================
# POLICY ENFORCEMENT ENGINE
# =============================================

INSTITUTION_POLICIES = {
    "mask_fields": ["ssn"],
    "prohibited_combinations": [
        ("Student", "grades"),
        ("Student", "financial_information_others"),
        ("Teacher", "financial_information_others"),
    ],
}

ROLE_POLICIES = {
    "Admin":   {"allowed_resources": ["persons","financial_information","grades","classes"], "mask_fields": []},
    "Teacher": {"allowed_resources": ["persons","grades","classes"], "mask_fields": [], "can_view_own_salary": True},
    "Student": {"allowed_resources": ["persons","classes"], "mask_fields": [], "can_view_own_financial": True},
}

USER_POLICIES = {}

class PolicyEngine:
    def __init__(self, identity_scope):
        self.role = identity_scope["role"]
        self.user_id = identity_scope["user_id"]
        self.role_policy = ROLE_POLICIES.get(self.role, {"allowed_resources": [], "mask_fields": []})
        self.user_policy = USER_POLICIES.get(self.user_id, {})

    def get_mask_fields(self):
        fields = set(INSTITUTION_POLICIES["mask_fields"])
        fields.update(self.role_policy.get("mask_fields", []))
        return list(fields)

    def get_authorized_resources(self):
        return self.role_policy.get("allowed_resources", [])

    def get_denied_resources(self):
        all_res = ["persons", "financial_information", "grades", "classes"]
        auth = set(self.get_authorized_resources())
        denied = [r for r in all_res if r not in auth]
        if self.role == "Teacher": denied.extend(["other_salaries", "student_financial_info"])
        elif self.role == "Student": denied.extend(["grades", "other_student_financials", "employee_salaries"])
        return denied


# =============================================
# DATA FILTER
# =============================================

def filter_data(sis_data, policy, user_id):
    role = policy.role
    mask_fields = policy.get_mask_fields()
    filtered = {}

    if "persons" in policy.get_authorized_resources():
        persons = copy.deepcopy(sis_data.get("persons", []))
        for p in persons:
            if "ssn" in mask_fields: p["ssn"] = "***-**-****"
        filtered["persons"] = persons

    financials = copy.deepcopy(sis_data.get("financial_information", []))
    if role == "Admin":
        filtered["financial_information"] = financials
    elif role == "Teacher":
        own = [f for f in financials if f["person_id"] == user_id]
        filtered["financial_information"] = own
        filtered["financial_information_note"] = "Restricted to your own salary only."
    elif role == "Student":
        own = [f for f in financials if f["person_id"] == user_id]
        filtered["financial_information"] = own
        filtered["financial_information_note"] = "Restricted to your own tuition info only."

    grades = copy.deepcopy(sis_data.get("grades", []))
    if role in ("Admin", "Teacher"): filtered["grades"] = grades
    elif role == "Student": filtered["grades"] = "[ACCESS DENIED — Students cannot access grades.]"

    classes = copy.deepcopy(sis_data.get("classes", []))
    if role in ("Admin", "Teacher"): filtered["classes"] = classes
    elif role == "Student":
        filtered["classes"] = [{"class_id": c["class_id"], "name": c["name"], "teacher_name": c["teacher_name"],
            "schedule": c["schedule"], "room": c["room"], "credits": c["credits"],
            "enrolled_students": c["enrolled_students"]} for c in classes]

    return filtered

def filtered_data_to_text(filtered):
    parts = []
    if "persons" in filtered:
        parts.append("=== PERSONS ===")
        for p in filtered["persons"]:
            line = f"  {p['name']} (ID: {p['person_id']}) — Role: {p['role']}"
            if p.get("major"): line += f", Major: {p['major']}, Year: {p['year']}"
            if p.get("department"): line += f", Dept: {p['department']}"
            if p.get("title"): line += f", Title: {p['title']}"
            line += f", Email: {p['email']}, SSN: {p['ssn']}"
            parts.append(line)

    if "financial_information" in filtered:
        parts.append("\n=== FINANCIAL INFORMATION ===")
        if isinstance(filtered["financial_information"], str): parts.append(f"  {filtered['financial_information']}")
        elif isinstance(filtered["financial_information"], list):
            if filtered.get("financial_information_note"): parts.append(f"  Note: {filtered['financial_information_note']}")
            for f in filtered["financial_information"]:
                if f.get("type") == "tuition": parts.append(f"  {f['person_id']}: Tuition — Due: ${f['amount_due']:,}, Paid: ${f['amount_paid']:,}, Balance: ${f['balance']:,}, Scholarship: {f['scholarship']}, Status: {f['status']}")
                elif f.get("type") == "salary": parts.append(f"  {f['person_id']}: Salary — ${f['annual_salary']:,}/year, {f['pay_frequency']}, Benefits: {f['benefits']}, Status: {f['status']}")

    if "grades" in filtered:
        parts.append("\n=== GRADES ===")
        if isinstance(filtered["grades"], str): parts.append(f"  {filtered['grades']}")
        elif isinstance(filtered["grades"], list):
            for g in filtered["grades"]: parts.append(f"  Student {g['student_id']} in {g['class_id']}: Midterm {g['midterm']}, Final {g['final']}, Grade: {g['grade']}, Attendance: {g['attendance_rate']*100:.0f}%")

    if "classes" in filtered:
        parts.append("\n=== CLASSES ===")
        if isinstance(filtered["classes"], str): parts.append(f"  {filtered['classes']}")
        elif isinstance(filtered["classes"], list):
            for c in filtered["classes"]:
                students = ", ".join(c.get("enrolled_students", []))
                parts.append(f"  {c['class_id']} — {c['name']} | Teacher: {c.get('teacher_name','N/A')} | {c['schedule']} | Room: {c['room']} | Students: [{students}]")
    return "\n".join(parts)


# =============================================
# CONTEXT PACKET (CCP v1.0)
# =============================================

def build_context_packet(trace_id, identity_scope, model_descriptor, authorized_resources, mask_fields, denied_resources, policy_decision):
    policy_state = json.dumps({"institution": INSTITUTION_POLICIES, "role_policies": ROLE_POLICIES}, sort_keys=True)
    policy_hash = "sha256:" + hashlib.sha256(policy_state.encode()).hexdigest()[:16]
    return {
        "ccp_version": "1.0", "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "identity_scope": {"user_id": identity_scope["user_id"], "role": identity_scope["role"],
            "clearance": identity_scope["clearance"], "session_context": identity_scope.get("session_context", {})},
        "selected_model": model_descriptor,
        "authorized_resources": authorized_resources,
        "context_constraints": {"mask_fields": mask_fields, "denied_resources": denied_resources,
            "prohibited_combinations": [f"{r}+{res}" for r, res in INSTITUTION_POLICIES["prohibited_combinations"]]},
        "policy_decision": policy_decision, "policy_hash": policy_hash,
    }


# =============================================
# MAIN ICCP PROCESSOR
# =============================================

class ICCPEngine:
    _resource_timestamps: dict[str, float] = {}

    def process(self, user_id, role, sis_data, query):
        trace_id = f"tr-{uuid.uuid4().hex[:8]}"
        identity = build_identity_scope(user_id, role)
        session_context = identity["session_context"]

        policy = PolicyEngine(identity)
        authorized = policy.get_authorized_resources()
        denied = policy.get_denied_resources()
        masked = policy.get_mask_fields()

        ttl_status = {}
        for r in authorized:
            desc = build_resource_descriptor(r)
            now = time.time()
            elapsed = now - self._resource_timestamps.get(r, 0)
            if elapsed > desc["ttl"]:
                self._resource_timestamps[r] = now
                ttl_status[r] = {"status": "refreshed", "ttl_seconds": desc["ttl"]}
            else:
                ttl_status[r] = {"status": "cached", "remaining_seconds": round(desc["ttl"] - elapsed)}

        filtered = filter_data(sis_data, policy, user_id)
        filtered_context = filtered_data_to_text(filtered)

        if not authorized: access_level, decision = "denied", "DENY"
        elif denied: access_level, decision = "partial", "ALLOW_PARTIAL"
        else: access_level, decision = "full", "ALLOW_FULL"

        model = build_model_descriptor()
        packet = build_context_packet(trace_id, identity, model, authorized, masked, denied, decision)
        explanation = self._explain(identity, authorized, denied, masked, decision)

        log_audit_entry(trace_id=trace_id, identity_scope=identity, session_context=session_context,
            model_descriptor=model, resources_accessed=authorized, resources_denied=denied,
            fields_masked=masked, policy_decision=decision, explanation=explanation, ttl_status=ttl_status)

        return {"filtered_context": filtered_context, "access_level": access_level,
                "masked_fields": masked, "denied_resources": denied,
                "trace_id": trace_id, "context_packet": packet}

    def _explain(self, identity, authorized, denied, masked, decision):
        p = [f"{identity['role']} ({identity['clearance']}) requested data."]
        if identity["role"] == "Admin": p.append("Full access granted to all 4 tables.")
        elif identity["role"] == "Teacher": p.append("Granted: persons, grades, classes. Financial restricted to own salary only. Prohibited: student tuition, other salaries.")
        elif identity["role"] == "Student": p.append("Granted: classes (peer view), own financial info. Prohibited: grades table, other financials, employee salaries.")
        if masked: p.append(f"Masked: {', '.join(masked)} (institution-level, all roles).")
        p.append(f"Decision: {decision}.")
        return " ".join(p)
