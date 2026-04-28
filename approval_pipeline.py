"""
approval_pipeline.py  —  Smart Hierarchical Agentic Approval Pipeline
======================================================================

Flow:
  1. Junior Agent    → fills form, system classifier runs automatically
  2. System Classifier → reads change type, assigns risk, determines routing
  3. Senior Agent    → auto-reviews quality (may auto-pass low-risk)
  4. Tech Lead Agent → validates technical safety, writes CTO/CEO briefing email
  5. CTO / CEO Agent → reads briefing, decides to auto-approve or escalate to human
                       (CEO if security/external/financial, CTO otherwise)
  6. YOU             → only manual step — approve/reject in dashboard, upload doc
  7. KB Sync         → auto-triggered on approval → writes to resolved_issues
"""

import streamlit as st
import time
import json
import requests
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
HEARTBEAT_SEC   = 8
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# ── Change type routing rules ─────────────────────────────────────────────────
CHANGE_TYPES = {
    "Documentation Update": {"risk": "Low",    "needs_ceo": False, "auto_senior": True,  "category": "docs"},
    "Code Change":          {"risk": "Medium",  "needs_ceo": False, "auto_senior": False, "category": "tech"},
    "Security Patch":       {"risk": "High",    "needs_ceo": True,  "auto_senior": False, "category": "security"},
    "API Change":           {"risk": "High",    "needs_ceo": True,  "auto_senior": False, "category": "api"},
    "Financial Report":     {"risk": "High",    "needs_ceo": True,  "auto_senior": False, "category": "finance"},
    "Policy Document":      {"risk": "Medium",  "needs_ceo": False, "auto_senior": False, "category": "policy"},
    "Employee Data":        {"risk": "High",    "needs_ceo": True,  "auto_senior": False, "category": "hr"},
    "Vendor Contract":      {"risk": "Medium",  "needs_ceo": False, "auto_senior": False, "category": "legal"},
    "System Architecture":  {"risk": "High",    "needs_ceo": False, "auto_senior": False, "category": "tech"},
}

CATEGORY_LABELS = {
    "docs":     "Internal Documentation",
    "tech":     "Technical Change",
    "security": "Security-Critical",
    "api":      "External API / Integration",
    "finance":  "Financial Data",
    "policy":   "Policy / Compliance",
    "hr":       "People & HR",
    "legal":    "Legal / Vendor",
}

AGENTS = [
    {"id": "classifier", "label": "System Classifier", "icon": "🔍", "color": "#6366f1", "bg": "#eef2ff",  "manual": False, "desc": "Reads change type, assigns risk, determines routing path"},
    {"id": "senior",     "label": "Senior Agent",       "icon": "👨‍💼", "color": "#0ea5e9", "bg": "#f0f9ff",  "manual": False, "desc": "Reviews edit quality — may auto-pass low-risk requests"},
    {"id": "techlead",   "label": "Tech Lead Agent",    "icon": "🧑‍🔧", "color": "#8b5cf6", "bg": "#f5f3ff",  "manual": False, "desc": "Validates technical safety, writes CTO/CEO briefing email"},
    {"id": "cto",        "label": "CTO / CEO Agent",    "icon": "🏛️",  "color": "#f59e0b", "bg": "#fffbeb",  "manual": False, "desc": "Reads briefing, decides to auto-approve or escalate to you"},
    {"id": "human",      "label": "Your Approval",      "icon": "✅",  "color": "#059669", "bg": "#f0fdf4",  "manual": True,  "desc": "THE ONLY MANUAL STEP — approve or reject in dashboard"},
    {"id": "kb",         "label": "KB Sync",            "icon": "📚",  "color": "#10b981", "bg": "#ecfdf5",  "manual": False, "desc": "Auto-triggered on approval → writes to resolved_issues"},
]
AGENT_BY_ID = {a["id"]: a for a in AGENTS}

# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');

.hier { display:flex; flex-direction:column; gap:0; margin:16px 0 8px; }
.hnode { display:flex; align-items:flex-start; gap:0; position:relative; }
.hnode:not(:last-child) .hline-wrap::after {
    content:''; position:absolute; left:19px; top:42px; width:2px;
    height:calc(100% - 2px); background:linear-gradient(180deg,#94a3b855,#94a3b811); z-index:0;
}
.hline-wrap { position:relative; display:flex; flex-direction:column; align-items:center; }
.hdot {
    width:40px; height:40px; border-radius:50%; display:flex; align-items:center;
    justify-content:center; font-size:18px; flex-shrink:0; z-index:1;
    border:2px solid #e2e8f0; background:#f8fafc; transition:all .3s; margin-top:2px;
}
.hdot.idle    { background:#f1f5f9; border-color:#cbd5e1; filter:grayscale(.6); }
.hdot.active  { border-width:3px; animation:activeglow 1.4s ease-in-out infinite; }
.hdot.done    { border-width:2px; }
.hdot.fail    { background:#fee2e2 !important; border-color:#dc2626 !important; }
.hdot.skip    { background:#dbeafe !important; border-color:#3b82f6 !important; }
@keyframes activeglow {
    0%,100% { box-shadow:0 0 0 0 rgba(99,102,241,.4); }
    50%      { box-shadow:0 0 0 8px rgba(99,102,241,0); }
}
.harrow { font-size:13px; color:#94a3b8; margin:3px 0; line-height:1; z-index:1; }
.hbody { flex:1; padding:6px 0 22px 16px; }
.htitle { font-family:'Syne',sans-serif; font-size:14px; font-weight:700; color:#0f172a;
          display:flex; align-items:center; gap:8px; }
.badge-auto   { font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#ede9fe;color:#7c3aed; }
.badge-manual { font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#fef3c7;color:#92400e; }
.badge-skip   { font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#dbeafe;color:#1e40af; }
.badge-active { font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#dcfce7;color:#166534;animation:waitpulse 1.5s infinite; }
@keyframes waitpulse { 0%,100%{opacity:1}50%{opacity:.55} }
.hdesc { font-size:12px; color:#64748b; margin-top:2px; }
.hresult { font-size:12px; margin-top:7px; padding:8px 12px; border-radius:9px; line-height:1.6; }
.hresult.done    { background:#f0fdf4; color:#166534; border-left:3px solid #059669; }
.hresult.fail    { background:#fef2f2; color:#991b1b; border-left:3px solid #dc2626; }
.hresult.active  { background:#f5f3ff; color:#4c1d95; border-left:3px solid #7c3aed; }
.hresult.skip    { background:#eff6ff; color:#1e40af; border-left:3px solid #3b82f6; }

/* Email card */
.email-card {
    background:#fafaf9; border:1px solid #e5e7eb; border-radius:10px;
    padding:14px 16px; margin-top:10px; font-size:13px;
}
.email-meta { display:grid; grid-template-columns:auto 1fr; gap:3px 10px;
              font-size:11px; font-family:monospace; color:#6b7280;
              padding-bottom:10px; border-bottom:1px solid #e5e7eb; margin-bottom:10px; }
.email-meta span:nth-child(odd) { font-weight:600; color:#374151; }
.email-body { line-height:1.7; color:#374151; font-style:italic; }

/* Classifier block */
.cls-block { background:#f8fafc; border:1px solid #e2e8f0; border-radius:9px;
             padding:12px 14px; margin:8px 0; }
.cls-tags  { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.cls-tag   { font-size:11px; font-family:monospace; padding:3px 9px; border-radius:12px; }
.tag-low   { background:#dcfce7; color:#166534; }
.tag-med   { background:#fef3c7; color:#92400e; }
.tag-high  { background:#fee2e2; color:#991b1b; }
.tag-sec   { background:#fce7f3; color:#9d174d; }
.tag-info  { background:#dbeafe; color:#1e40af; }
.tag-gray  { background:#f1f5f9; color:#475569; }

/* Metric cards */
.mc { background:white; border-radius:12px; padding:14px; text-align:center;
      box-shadow:0 2px 8px rgba(0,0,0,.06); }
.mc-n { font-family:'Syne',sans-serif; font-size:26px; font-weight:800; color:#6366f1; }
.mc-l { font-size:11px; color:#6b7280; margin-top:2px; }

/* Status pills */
.spill { display:inline-block; padding:2px 10px; border-radius:20px;
         font-size:11px; font-weight:700; margin-right:4px; }

/* Filter tab pills — override Streamlit default button style */
div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
    border-radius: 20px !important;
    padding: 4px 8px !important;
    font-size: 12px !important;
    font-weight: 400 !important;
    min-height: 0 !important;
    line-height: 1.4 !important;
}

/* Heartbeat */
.hbbar { display:flex; align-items:center; gap:10px; background:#f5f3ff;
         border-radius:10px; padding:8px 14px; font-size:13px; color:#4c1d95;
         margin-bottom:16px; border:1px solid #ede9fe; }
.hbdot { width:9px; height:9px; border-radius:50%; background:#7c3aed;
         animation:hbp 1.4s ease-in-out infinite; }
@keyframes hbp { 0%,100%{opacity:1;transform:scale(1.1)}50%{opacity:.3;transform:scale(.7)} }

/* Routing summary */
.route-box { background:#fffbeb; border:1px solid #fde68a; border-radius:9px;
             padding:12px 14px; margin:8px 0; font-size:12px; color:#92400e; }
</style>
"""

# ── Supabase ──────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _db():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None

def _now():
    return datetime.now(timezone.utc).isoformat()

def _load_sr(task):
    try:
        return json.loads(task.get("stage_results") or "{}")
    except Exception:
        return {}

def _create_task(title, requester, dept, doc_type, desc, priority):
    db = _db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    row = {
        "title":         title,
        "requester":     requester,
        "department":    dept,
        "request_type":  doc_type,
        "description":   desc,
        "priority":      priority,
        "stage":         "classifier",
        "status":        "Classifying",
        "stage_results": json.dumps({
            "junior": {
                "agent":    "Junior Agent",
                "action":   "Submitted request",
                "decision": "Approved",
                "reason":   f"Submitted by {requester}. System classifier running.",
                "risk":     "Pending",
            }
        }),
        "risk_level":    "Pending",
        "created_at":    _now(),
        "updated_at":    _now(),
    }
    r = db.table("approval_requests").insert(row).execute()
    if r.data:
        return r.data[0]
    raise Exception("Insert failed.")

def _get_tasks_for_agent(status):
    db = _db()
    if db is None:
        return []
    try:
        return (db.table("approval_requests")
                  .select("*").eq("status", status)
                  .order("created_at").execute().data or [])
    except Exception:
        return []

def _get_all_tasks(status_filter=None):
    db = _db()
    if db is None:
        return []
    try:
        q = db.table("approval_requests").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        return q.execute().data or []
    except Exception:
        return []

def _update_task(tid, **kw):
    db = _db()
    if db is None:
        return
    kw["updated_at"] = _now()
    db.table("approval_requests").update(kw).eq("id", tid).execute()

def _delete_task(tid):
    db = _db()
    if db:
        db.table("approval_requests").delete().eq("id", tid).execute()

def _write_kb(query, solution):
    db = _db()
    if db is None:
        return
    try:
        ex = db.table("resolved_issues").select("id").eq("query", query).execute()
        if ex.data:
            db.table("resolved_issues").update({"solution": solution}).eq("query", query).execute()
        else:
            db.table("resolved_issues").insert({"query": query, "solution": solution}).execute()
    except Exception as e:
        st.warning(f"KB write: {e}")

def _stats():
    rows = _get_all_tasks()
    in_progress = {"Classifying", "Senior Review", "TechLead Review", "CTO Review", "CEO Review"}
    return {
        "total":    len(rows),
        "progress": sum(1 for r in rows if r.get("status") in in_progress),
        "awaiting": sum(1 for r in rows if r.get("status") == "Awaiting Approval"),
        "approved": sum(1 for r in rows if r.get("status") == "Approved"),
        "rejected": sum(1 for r in rows if r.get("status") == "Rejected"),
    }

# ── Claude API ────────────────────────────────────────────────────────────────
def _claude(system: str, user: str, max_tokens: int = 500) -> dict:
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model":      ANTHROPIC_MODEL,
                "max_tokens": max_tokens,
                "system":     system,
                "messages":   [{"role": "user", "content": user}],
            },
            timeout=45,
        )
        raw = ""
        for block in resp.json().get("content", []):
            if block.get("type") == "text":
                raw += block["text"]
        raw = raw.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception as e:
        return {"decision": "Escalate", "reason": f"Agent error: {e}", "risk": "Medium"}

# ── Agent: System Classifier ──────────────────────────────────────────────────
def run_classifier(task: dict):
    """
    Reads the request and determines:
    - category, risk level, whether security/external is involved
    - routing path (auto-pass senior? escalate to CEO?)
    """
    type_info = CHANGE_TYPES.get(task.get("request_type", ""), {})

    result = _claude(
        """You are a change management classifier. Analyze the request and return ONLY raw JSON.
Keys:
  "category": one of [docs, tech, security, api, finance, policy, hr, legal]
  "risk": one of [Low, Medium, High, Critical]
  "involves_security": boolean — true if touches auth, access control, credentials, encryption
  "involves_external": boolean — true if touches external APIs, third parties, or customer-facing surfaces
  "summary": one-sentence plain English summary of what this change is (max 20 words)
  "routing_note": one sentence explaining the routing decision
  "auto_pass_senior": boolean — true only if risk is Low and change is purely internal documentation""",
        f"Title: {task['title']}\nType: {task['request_type']}\nDept: {task['department']}\nDesc: {task['description']}",
        max_tokens=300,
    )

    sr = _load_sr(task)
    needs_ceo = (
        result.get("involves_security")
        or result.get("involves_external")
        or type_info.get("needs_ceo", False)
        or result.get("risk") in ("High", "Critical")
    )

    sr["classifier"] = {
        "agent":           "System Classifier",
        "action":          "Classified and routed",
        "decision":        "Routed",
        "category":        result.get("category", "tech"),
        "risk":            result.get("risk", "Medium"),
        "involves_security": result.get("involves_security", False),
        "involves_external": result.get("involves_external", False),
        "summary":         result.get("summary", ""),
        "routing_note":    result.get("routing_note", ""),
        "auto_pass_senior": result.get("auto_pass_senior", False),
        "needs_ceo":       needs_ceo,
    }
    risk = result.get("risk", type_info.get("risk", "Medium"))
    _update_task(task["id"],
        status="Senior Review",
        stage="senior",
        risk_level=risk,
        stage_results=json.dumps(sr),
        # store routing flags as JSON in a field — we'll use risk_level for display
    )

# ── Agent: Senior ─────────────────────────────────────────────────────────────
def run_senior_agent(task: dict):
    sr        = _load_sr(task)
    cls       = sr.get("classifier", {})
    auto_pass = cls.get("auto_pass_senior", False)

    if auto_pass:
        # Low-risk internal docs — auto-pass with a note
        sr["senior"] = {
            "agent":    "Senior Agent",
            "action":   "Auto-passed (low risk internal change)",
            "decision": "Approve",
            "reason":   "Low-risk internal documentation change — auto-approved at senior level.",
            "risk":     cls.get("risk", "Low"),
            "skipped":  True,
        }
        _update_task(task["id"],
            status="TechLead Review",
            stage="techlead",
            stage_results=json.dumps(sr))
        return

    result = _claude(
        """You are a Senior Engineer reviewing a change request. Be concise and decisive.
Return ONLY raw JSON:
  "decision": "Approve" or "Reject"
  "reason": 1-2 sentences
  "notes": brief technical note for Tech Lead""",
        f"Title: {task['title']}\nType: {task['request_type']}\nDept: {task['department']}\n"
        f"Classifier summary: {cls.get('summary', '')}\nRisk: {cls.get('risk', 'Medium')}\n"
        f"Description: {task['description']}",
    )

    sr["senior"] = {
        "agent":    "Senior Agent",
        "action":   "Reviewed change quality",
        "decision": result.get("decision", "Approve"),
        "reason":   result.get("reason", ""),
        "notes":    result.get("notes", ""),
        "risk":     cls.get("risk", "Medium"),
    }

    if result.get("decision") == "Reject":
        _update_task(task["id"],
            status="Rejected", stage="senior",
            stage_results=json.dumps(sr))
    else:
        _update_task(task["id"],
            status="TechLead Review",
            stage="techlead",
            stage_results=json.dumps(sr))

# ── Agent: Tech Lead ──────────────────────────────────────────────────────────
def run_techlead_agent(task: dict):
    sr           = _load_sr(task)
    cls          = sr.get("classifier", {})
    senior_notes = sr.get("senior", {}).get("notes", "")
    needs_ceo    = cls.get("needs_ceo", False)

    result = _claude(
        """You are a Tech Lead in a change management pipeline. Assess technical safety and write a briefing.
Return ONLY raw JSON:
  "decision": "Approve" or "Reject"
  "reason": 1-2 sentences
  "cto_email_body": 2-3 sentence manager-style email to the CTO/CEO explaining what the change is and what they need to decide. Write it as if you're emailing a busy executive — clear, direct, no jargon.
  "technical_note": one line of technical context for the executive""",
        f"Title: {task['title']}\nType: {task['request_type']}\nDept: {task['department']}\n"
        f"Risk: {cls.get('risk', 'Medium')}\nInvolves security: {cls.get('involves_security', False)}\n"
        f"Involves external: {cls.get('involves_external', False)}\nNeeds CEO: {needs_ceo}\n"
        f"Senior notes: {senior_notes}\nDescription: {task['description']}",
        max_tokens=500,
    )

    sr["techlead"] = {
        "agent":          "Tech Lead Agent",
        "action":         "Validated technical safety",
        "decision":       result.get("decision", "Approve"),
        "reason":         result.get("reason", ""),
        "cto_email_body": result.get("cto_email_body", ""),
        "technical_note": result.get("technical_note", ""),
        "needs_ceo":      needs_ceo,
    }

    if result.get("decision") == "Reject":
        _update_task(task["id"],
            status="Rejected", stage="techlead",
            stage_results=json.dumps(sr))
        return

    next_status = "CEO Review" if needs_ceo else "CTO Review"
    _update_task(task["id"],
        status=next_status,
        stage="cto",
        stage_results=json.dumps(sr))

# ── Agent: CTO / CEO ──────────────────────────────────────────────────────────
def run_cto_ceo_agent(task: dict):
    sr        = _load_sr(task)
    cls       = sr.get("classifier", {})
    tl        = sr.get("techlead", {})
    needs_ceo = cls.get("needs_ceo", False)
    role      = "CEO" if needs_ceo else "CTO"

    result = _claude(
        f"""You are the {role} reviewing a change that has been escalated to you.
You just received a briefing email from the Tech Lead. Be decisive.
Return ONLY raw JSON:
  "decision": "Approve" or "Reject" or "Escalate_Human"
  "reason": 1-2 sentences as if writing to the requester
  "risk_assessment": "Low", "Medium", or "High"
  "requires_human_approval": boolean — true if any doubt, high risk, external impact, or policy change
Auto-approve ONLY if risk is genuinely Low and the change is routine internal.""",
        f"Briefing from Tech Lead:\n{tl.get('cto_email_body', '')}\n\n"
        f"Technical note: {tl.get('technical_note', '')}\n\n"
        f"Title: {task['title']}\nType: {task['request_type']}\nRisk: {cls.get('risk', 'Medium')}\n"
        f"Security: {cls.get('involves_security', False)}\nExternal: {cls.get('involves_external', False)}\n"
        f"Desc: {task['description']}",
    )

    sr["cto"] = {
        "agent":    f"{role} Agent",
        "action":   f"Final review as {role}",
        "decision": result.get("decision", "Escalate_Human"),
        "reason":   result.get("reason", ""),
        "risk":     result.get("risk_assessment", "Medium"),
        "role":     role,
    }

    decision = result.get("decision", "Escalate_Human")

    if decision == "Reject":
        _update_task(task["id"],
            status="Rejected", stage="cto",
            stage_results=json.dumps(sr))
        return

    if decision == "Approve" and not result.get("requires_human_approval", True):
        # Auto-approve — write KB directly
        sr["human"] = {"agent": "Auto", "decision": "Approved", "reason": f"Auto-approved by {role} agent (low risk)."}
        _update_task(task["id"],
            status="Approved", stage="kb",
            stage_results=json.dumps(sr))
        _run_kb({**task, "stage_results": json.dumps(sr)})
        return

    # Escalate to human
    _update_task(task["id"],
        status="Awaiting Approval",
        stage="human",
        stage_results=json.dumps(sr))

def _run_kb(task: dict):
    sr = _load_sr(task)
    reason = (
        sr.get("cto",    {}).get("reason", "")
        or sr.get("techlead", {}).get("reason", "")
        or "Approved via pipeline."
    )
    solution = f"[Pipeline Approved] {reason}"
    _write_kb(task["title"], solution)
    sr["kb"] = {"status": "updated", "written_at": _now()}
    _update_task(task["id"],
        status="Done",
        stage_results=json.dumps(sr))

# ── Heartbeat ─────────────────────────────────────────────────────────────────
def heartbeat_tick():
    processed = 0
    for status, runner in [
        ("Classifying",    run_classifier),
        ("Senior Review",  run_senior_agent),
        ("TechLead Review",run_techlead_agent),
        ("CTO Review",     run_cto_ceo_agent),
        ("CEO Review",     run_cto_ceo_agent),
    ]:
        tasks = _get_tasks_for_agent(status)
        for t in tasks[:2]:
            try:
                runner(t)
                processed += 1
            except Exception as e:
                st.warning(f"Agent error on task #{t.get('id')}: {e}")
    return processed

# ── Renderers ─────────────────────────────────────────────────────────────────
def _pill_color(agent_id):
    colors = {
        "classifier": ("#eef2ff", "#4338ca"),
        "senior":     ("#f0f9ff", "#0369a1"),
        "techlead":   ("#f5f3ff", "#6d28d9"),
        "cto":        ("#fffbeb", "#b45309"),
        "human":      ("#f0fdf4", "#065f46"),
        "kb":         ("#ecfdf5", "#047857"),
    }
    return colors.get(agent_id, ("#f1f5f9", "#475569"))

def _render_classifier_block(cls: dict):
    if not cls:
        return ""
    risk     = cls.get("risk", "Medium")
    risk_tag = {"Low": "tag-low", "Medium": "tag-med", "High": "tag-high", "Critical": "tag-high"}.get(risk, "tag-gray")
    cat_lbl  = CATEGORY_LABELS.get(cls.get("category", ""), cls.get("category", ""))
    tags_html = f"<span class='cls-tag tag-gray'>{cat_lbl}</span>"
    tags_html += f"<span class='cls-tag {risk_tag}'>{risk} risk</span>"
    if cls.get("involves_security"):
        tags_html += "<span class='cls-tag tag-sec'>security-critical</span>"
    if cls.get("involves_external"):
        tags_html += "<span class='cls-tag tag-info'>external integration</span>"
    if cls.get("needs_ceo"):
        tags_html += "<span class='cls-tag tag-sec'>CEO-level routing</span>"
    if cls.get("auto_pass_senior"):
        tags_html += "<span class='cls-tag tag-low'>senior auto-pass</span>"
    summary = f"<div style='font-size:12px;color:#64748b;margin-top:6px;font-style:italic'>"{cls.get('summary','')}"</div>" if cls.get("summary") else ""
    return f"""
    <div class='cls-block'>
        <div style='font-size:11px;font-family:monospace;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px'>System classification</div>
        <div class='cls-tags'>{tags_html}</div>
        {summary}
    </div>"""

def _render_email_card(tl: dict, task: dict):
    body = tl.get("cto_email_body", "")
    if not body:
        return ""
    role = "CEO" if tl.get("needs_ceo") else "CTO"
    note = tl.get("technical_note", "")
    note_html = f"<div style='font-size:11px;font-family:monospace;opacity:.65;margin-top:8px'>Technical note: {note}</div>" if note else ""
    return f"""
    <div class='email-card'>
        <div class='email-meta'>
            <span>From</span><span>Tech Lead · System Notification</span>
            <span>To</span><span>{role} · Approval Required</span>
            <span>Re</span><span>{task.get('title','')}</span>
        </div>
        <div class='email-body'>{body}{note_html}</div>
    </div>"""

def _render_hierarchy(sr: dict, current_stage: str, task: dict):
    st.markdown("<div class='hier'>", unsafe_allow_html=True)
    for i, agent in enumerate(AGENTS):
        aid    = agent["id"]
        res    = sr.get(aid)
        bg, fg = _pill_color(aid)
        is_last = (i == len(AGENTS) - 1)

        # dot state
        if res:
            dec = res.get("decision", "")
            if dec == "Reject":
                dot_cls  = "fail"; dot_style = ""; res_cls = "fail"
                tick = "❌"; res_text = res.get("reason", "")
            elif res.get("skipped"):
                dot_cls  = "skip"; dot_style = f"background:{bg};border-color:{fg};"
                res_cls  = "skip"; tick = "⏭️"; res_text = res.get("reason", "")
            elif dec in ("Approve", "Approved", "Routed", "updated"):
                dot_cls  = "done"; dot_style = f"background:{bg};border-color:{fg};"
                res_cls  = "done"; tick = "✅"; res_text = res.get("reason", "") or res.get("routing_note", "") or res.get("status", "")
            elif dec == "Escalate_Human":
                dot_cls  = "done"; dot_style = f"background:{bg};border-color:{fg};"
                res_cls  = "done"; tick = "⬆️"; res_text = res.get("reason", "")
            else:
                dot_cls  = "done"; dot_style = f"background:{bg};border-color:{fg};"
                res_cls  = "done"; tick = "✅"; res_text = res.get("reason", "") or res.get("routing_note", "")
        elif aid == current_stage:
            dot_cls  = "active"; dot_style = f"background:{bg};border-color:{fg};"
            res_cls  = "active"; tick = ""; res_text = "⏳ Agent working…"
        else:
            dot_cls  = "idle"; dot_style = ""; res_cls  = ""; tick = ""; res_text = ""

        # badge
        if agent["manual"]:
            badge = "<span class='badge-manual'>MANUAL</span>"
        elif res and res.get("skipped"):
            badge = "<span class='badge-skip'>AUTO-PASS</span>"
        elif aid == current_stage and not res:
            badge = "<span class='badge-active'>● ACTIVE</span>"
        else:
            badge = "<span class='badge-auto'>AUTO</span>"

        result_html = f"<div class='hresult {res_cls}'>{tick} {res_text}</div>" if res_text else ""

        # Email card only for techlead → cto step
        email_html = ""
        if aid == "techlead" and res and res.get("cto_email_body"):
            email_html = _render_email_card(res, task)

        # Classifier block
        cls_html = ""
        if aid == "classifier" and res:
            cls_html = _render_classifier_block(res)

        # CTO role note
        extra_html = ""
        if aid == "cto" and res and res.get("role"):
            extra_html = f"<div style='font-size:11px;color:#b45309;margin-top:3px'>Acting as: <strong>{res['role']}</strong></div>"

        st.markdown(
            f"<div class='hnode'>"
            f"  <div class='hline-wrap'>"
            f"    <div class='hdot {dot_cls}' style='{dot_style}'>{agent['icon']}</div>"
            f"    {'<div class=\"harrow\">↓</div>' if not is_last else ''}"
            f"  </div>"
            f"  <div class='hbody'>"
            f"    <div class='htitle'>{agent['label']}{badge}</div>"
            f"    <div class='hdesc'>{agent['desc']}</div>"
            f"    {result_html}{cls_html}{email_html}{extra_html}"
            f"  </div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _status_pill(status):
    cfg = {
        "Classifying":       ("#ede9fe", "#5b21b6"),
        "Senior Review":     ("#dbeafe", "#1e40af"),
        "TechLead Review":   ("#ede9fe", "#5b21b6"),
        "CTO Review":        ("#fef3c7", "#92400e"),
        "CEO Review":        ("#fce7f3", "#9d174d"),
        "Awaiting Approval": ("#fef3c7", "#92400e"),
        "Approved":          ("#d1fae5", "#065f46"),
        "Rejected":          ("#fee2e2", "#991b1b"),
        "Done":              ("#d1fae5", "#065f46"),
    }
    bg, fg = cfg.get(status, ("#f1f5f9", "#475569"))
    return f"<span class='spill' style='background:{bg};color:{fg}'>{status}</span>"

def _fmt(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return ts or "—"

# ════════════════════════════════════════════════════════════════════════════
#  PAGE ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════
def page_approval_pipeline():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("# 📋 Smart Approval Pipeline")
    st.markdown(
        "<p style='color:#6b7280'>"
        "Intelligent routing: Classifier → Senior → Tech Lead → CTO/CEO (email briefing) → You → KB. "
        "Agents wake automatically. Your only action is the final approval."
        "</p>", unsafe_allow_html=True,
    )

    # ── Heartbeat ─────────────────────────────────────────────────────────────
    if "hb_last" not in st.session_state:
        st.session_state["hb_last"] = 0.0

    now       = time.time()
    since     = now - st.session_state["hb_last"]
    next_tick = max(0, HEARTBEAT_SEC - since)

    if since >= HEARTBEAT_SEC:
        st.session_state["hb_last"] = now
        n = heartbeat_tick()
        if n:
            st.toast(f"⚙️ {n} task(s) advanced by agents", icon="🤖")

    st.markdown(
        f"<div class='hbbar'>"
        f"  <div class='hbdot'></div>"
        f"  <span>Agent heartbeat active — next wake in <strong>{int(next_tick)}s</strong></span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    tab1, tab2 = st.tabs(["👩‍💻 Submit Request", "✅ Your Approval"])

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB 1 — SUBMIT + LIVE PIPELINE
    # ══════════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown("### 👩‍💻 Submit Change Request")
        st.markdown(
            "<small style='color:#6366f1'>Fill in the request — the system will classify it, "
            "assign risk, and route it through the right chain automatically.</small><br><br>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            requester  = st.text_input("👤 Your Name / ID *", placeholder="e.g. Priya K · ENG-042")
            department = st.selectbox("🏢 Department *", [
                "Select…", "Engineering", "Finance", "HR", "Legal",
                "Operations", "Security", "Executive", "Product", "Other",
            ])
            priority   = st.selectbox("🚨 Priority", ["Medium", "High", "Low"])
        with c2:
            title    = st.text_input("📌 Change Title *", placeholder="e.g. Update API login documentation")
            doc_type = st.selectbox("📂 Change Type *", [
                "Select…",
                "Documentation Update",
                "Code Change",
                "Security Patch",
                "API Change",
                "Financial Report",
                "Policy Document",
                "Employee Data",
                "Vendor Contract",
                "System Architecture",
            ])

        description = st.text_area(
            "📋 Describe the change *",
            placeholder="What are you changing, why, and any risks? "
                        "The classifier will read this to determine routing.",
            height=110,
        )

        # Routing preview
        if doc_type and doc_type != "Select…":
            info = CHANGE_TYPES.get(doc_type, {})
            risk = info.get("risk", "Medium")
            color_map = {"Low": "#dcfce7", "Medium": "#fef3c7", "High": "#fee2e2"}
            text_map  = {"Low": "#166534", "Medium": "#92400e", "High": "#991b1b"}
            bg = color_map.get(risk, "#f1f5f9")
            fg = text_map.get(risk, "#374151")
            ceo_note = " → <strong>CEO routing</strong>" if info.get("needs_ceo") else " → <strong>CTO routing</strong>"
            auto_note = " → <strong>Senior auto-pass eligible</strong>" if info.get("auto_senior") else ""
            st.markdown(
                f"<div class='route-box'>"
                f"  <strong>Routing preview:</strong> "
                f"  <span style='background:{bg};color:{fg};padding:2px 8px;border-radius:10px;font-size:12px'>{risk} risk</span>"
                f"  {ceo_note}{auto_note}"
                f"</div>",
                unsafe_allow_html=True,
            )

        if st.button("🚀 Submit to Pipeline"):
            errors = []
            if not requester.strip():   errors.append("Your name / ID required.")
            if department == "Select…": errors.append("Select department.")
            if doc_type   == "Select…": errors.append("Select change type.")
            if not title.strip():       errors.append("Title required.")
            if not description.strip(): errors.append("Description required.")
            for e in errors:
                st.error(e)
            if not errors:
                try:
                    t = _create_task(
                        title.strip(), requester.strip(), department,
                        doc_type, description.strip(), priority,
                    )
                    st.success(
                        f"✅ Task #{t['id']} created! "
                        "Classifier will pick it up on the next heartbeat.",
                        icon="🎉",
                    )
                    time.sleep(0.3)
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed: {ex}")

        # ── Pipeline dashboard ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📊 Live Pipeline")
        try:
            s  = _stats()
            mc = st.columns(5)
            for col, val, label, icon in zip(
                mc,
                [s["total"], s["progress"], s["awaiting"], s["approved"], s["rejected"]],
                ["Total", "In Pipeline", "Needs Your OK", "Approved", "Rejected"],
                ["📋", "⚙️", "🔔", "🟢", "🔴"],
            ):
                with col:
                    st.markdown(
                        f"<div class='mc'><div style='font-size:18px'>{icon}</div>"
                        f"<div class='mc-n'>{val}</div>"
                        f"<div class='mc-l'>{label}</div></div>",
                        unsafe_allow_html=True,
                    )
        except Exception:
            pass

        st.markdown("")

        # ── Tab-style filter pills ──────────────────────────────────────────
        FILTER_TABS = [
            ("All",               "⬡", "#f1f5f9", "#475569"),
            ("Classifying",       "🔍", "#ede9fe", "#5b21b6"),
            ("Senior Review",     "👨‍💼", "#dbeafe", "#1e40af"),
            ("TechLead Review",   "🧑‍🔧", "#ede9fe", "#5b21b6"),
            ("CTO Review",        "🏛️", "#fef3c7", "#92400e"),
            ("CEO Review",        "🏛️", "#fce7f3", "#9d174d"),
            ("Awaiting Approval", "🔔", "#fff3cd", "#7a5000"),
            ("Approved",          "✅", "#d1fae5", "#065f46"),
            ("Rejected",          "❌", "#fee2e2", "#991b1b"),
        ]

        if "pipeline_filter" not in st.session_state:
            st.session_state["pipeline_filter"] = "All"

        # Build pill row
        pill_html = "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px'>"
        for label, icon, bg, fg in FILTER_TABS:
            active = st.session_state["pipeline_filter"] == label
            border = f"2px solid {fg}" if active else f"1px solid #e2e8f0"
            font_w = "700" if active else "400"
            shadow = f"box-shadow:0 0 0 3px {bg};" if active else ""
            pill_html += (
                f"<span style='background:{bg if active else 'white'};color:{fg};"
                f"border:{border};border-radius:20px;padding:5px 13px;font-size:12px;"
                f"font-weight:{font_w};cursor:pointer;{shadow}white-space:nowrap'>"
                f"{icon} {label}</span>"
            )
        pill_html += "</div>"

        # Render pills as display only, use buttons underneath for interaction
        cols = st.columns(len(FILTER_TABS))
        for i, (label, icon, bg, fg) in enumerate(FILTER_TABS):
            with cols[i]:
                active = st.session_state["pipeline_filter"] == label
                btn_style = (
                    f"background:{bg};color:{fg};border:2px solid {fg};"
                    if active else
                    "background:white;color:#6b7280;border:1px solid #e2e8f0;"
                )
                if st.button(
                    f"{icon} {label}",
                    key=f"ftab_{label}",
                    use_container_width=True,
                ):
                    st.session_state["pipeline_filter"] = label
                    st.rerun()

        sf = st.session_state["pipeline_filter"]

        tasks = _get_all_tasks(sf if sf != "All" else None)
        if not tasks:
            st.info("No tasks yet.", icon="📭")
        else:
            for t in tasks:
                status = t.get("status", "")
                sr     = _load_sr(t)
                stage  = t.get("stage", "classifier")
                with st.expander(
                    f"#{t['id']} — {t.get('title','?')} | {t.get('requester','?')} | {status}"
                ):
                    st.markdown(
                        f"{_status_pill(status)} "
                        f"<span class='spill' style='background:#f1f5f9;color:#475569'>"
                        f"Risk: {t.get('risk_level','—')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**Requester:** {t.get('requester','–')} &nbsp;|&nbsp; "
                        f"**Dept:** {t.get('department','–')} &nbsp;|&nbsp; "
                        f"**Type:** {t.get('request_type','–')} &nbsp;|&nbsp; "
                        f"**Submitted:** {_fmt(t.get('created_at',''))}"
                    )
                    st.markdown(
                        f"<div style='background:#f8fafc;border-left:4px solid #6366f1;"
                        f"border-radius:10px;padding:11px;margin:10px 0;font-size:13px'>"
                        f"{t.get('description','–')}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Agent Hierarchy:**")
                    _render_hierarchy(sr, current_stage=stage, task=t)

                    rc1, rc2, _ = st.columns([1, 1, 4])
                    with rc1:
                        if st.button("🔄 Refresh", key=f"ref_{t['id']}"):
                            st.rerun()
                    with rc2:
                        if st.button("🗑️ Delete", key=f"del_dash_{t['id']}"):
                            try:
                                _delete_task(t["id"])
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))

        if st.button("⟳ Refresh now", key="manual_refresh"):
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB 2 — YOUR APPROVAL
    # ══════════════════════════════════════════════════════════════════════════
    with tab2:
        ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")

        if not st.session_state.get("exec_logged_in"):
            st.markdown("### 🔐 Login")
            col, _ = st.columns([1.5, 2.5])
            with col:
                pwd = st.text_input("Password", type="password", key="exec_pwd")
                if st.button("Login →", key="exec_login", use_container_width=True):
                    if pwd == ADMIN_PWD:
                        st.session_state["exec_logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
            return

        hc, lc = st.columns([5, 1])
        with hc:
            st.markdown("### ✅ Your Approval — Final Step")
            st.markdown(
                "<small style='color:#6b7280'>Every task here has been reviewed by the full agent chain. "
                "Approving will sync to the knowledge base automatically.</small>",
                unsafe_allow_html=True,
            )
        with lc:
            if st.button("Logout", key="exec_out"):
                st.session_state["exec_logged_in"] = False
                st.rerun()

        awaiting = _get_tasks_for_agent("Awaiting Approval")
        if not awaiting:
            st.success("✅ Nothing waiting for your approval right now.", icon="🎉")
        else:
            st.warning(f"🔔 **{len(awaiting)} task(s) need your approval.**")

        for t in awaiting:
            rid  = t["id"]
            sr   = _load_sr(t)
            risk = t.get("risk_level", "—")
            cls  = sr.get("classifier", {})
            cto  = sr.get("cto", {})

            with st.expander(
                f"#{rid} — {t.get('title','?')} | Risk: {risk}",
                expanded=True,
            ):
                st.markdown(
                    f"{_status_pill('Awaiting Approval')} "
                    f"<span class='spill' style='background:#f1f5f9;color:#475569'>Risk: {risk}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Requester:** {t.get('requester','–')} &nbsp;|&nbsp; "
                    f"**Dept:** {t.get('department','–')} &nbsp;|&nbsp; "
                    f"**Type:** {t.get('request_type','–')}"
                )
                st.markdown(
                    f"<div style='background:#f8fafc;border-left:4px solid #6366f1;"
                    f"border-radius:10px;padding:11px;margin:10px 0;font-size:13px'>"
                    f"{t.get('description','–')}</div>",
                    unsafe_allow_html=True,
                )

                # Classifier summary
                if cls:
                    st.markdown(_render_classifier_block(cls), unsafe_allow_html=True)

                # Agent chain summary
                st.markdown("**Agent chain review:**")
                for aid, label, icon in [
                    ("senior",   "Senior Agent",    "👨‍💼"),
                    ("techlead", "Tech Lead",        "🧑‍🔧"),
                    ("cto",      "CTO / CEO Agent",  "🏛️"),
                ]:
                    res = sr.get(aid)
                    if res:
                        d = res.get("decision", "")
                        color  = "#f0fdf4" if d not in ("Reject",) else "#fef2f2"
                        border = "#059669" if d not in ("Reject",) else "#dc2626"
                        role_note = f" (as {res.get('role','CTO')})" if aid == "cto" and res.get("role") else ""
                        st.markdown(
                            f"<div style='background:{color};border-left:3px solid {border};"
                            f"border-radius:8px;padding:8px 12px;margin:4px 0;font-size:12px'>"
                            f"{icon} <strong>{label}{role_note}:</strong> {res.get('reason','')}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                        # Show Tech Lead email card in approval view too
                        if aid == "techlead" and res.get("cto_email_body"):
                            st.markdown(
                                f"<details><summary style='font-size:12px;color:#6b7280;cursor:pointer;"
                                f"margin-top:4px'>View briefing email sent to {cto.get('role','CTO')}</summary>"
                                f"{_render_email_card(res, t)}</details>",
                                unsafe_allow_html=True,
                            )

                st.markdown("**Full hierarchy:**")
                _render_hierarchy(sr, current_stage="human", task=t)

                st.markdown("---")

                # Doc upload
                uploaded_key = f"doc_uploaded_{rid}"
                if not st.session_state.get(uploaded_key):
                    if st.button("📎 Attach updated document", key=f"upload_{rid}"):
                        st.session_state[uploaded_key] = True
                        st.rerun()
                else:
                    st.success(f"📄 Document attached: {t.get('title','').replace(' ','_').lower()}_approved.pdf")

                note = st.text_area(
                    "Your note (saved to KB on approval)",
                    key=f"note_{rid}", height=70,
                    placeholder="Add context or reasoning for the record…",
                )

                b1, b2, b3, _ = st.columns([1, 1, 1, 3])
                with b1:
                    if st.button("✅ Approve → KB", key=f"app_{rid}", use_container_width=True):
                        try:
                            sr["human"] = {
                                "agent":    "You",
                                "decision": "Approved",
                                "reason":   note or "Approved by authority.",
                            }
                            _update_task(rid,
                                status="Approved", stage="kb",
                                stage_results=json.dumps(sr),
                                reviewer_note=note)
                            _run_kb({**t, "stage_results": json.dumps(sr)})
                            st.success(
                                "✅ Approved! KB updated — "
                                "the next user asking a similar question will get this answer automatically."
                            )
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))
                with b2:
                    if st.button("❌ Reject", key=f"rej_{rid}", use_container_width=True):
                        try:
                            sr["human"] = {
                                "agent":    "You",
                                "decision": "Rejected",
                                "reason":   note or "Rejected by authority.",
                            }
                            _update_task(rid,
                                status="Rejected", stage="human",
                                stage_results=json.dumps(sr),
                                reviewer_note=note)
                            st.warning("❌ Rejected.")
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))
                with b3:
                    if st.button("🗑️ Delete", key=f"del_{rid}", use_container_width=True):
                        try:
                            _delete_task(rid)
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))

        # ── Decision history ───────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📋 Decision History")
        hist = [r for r in _get_all_tasks() if r.get("status") in ("Approved", "Rejected", "Done")]
        if not hist:
            st.info("No decisions yet.")
        for t in hist:
            rid    = t["id"]
            status = t.get("status", "")
            bg     = "#d1fae5" if status in ("Approved", "Done") else "#fee2e2"
            fg     = "#065f46" if status in ("Approved", "Done") else "#991b1b"
            with st.expander(f"#{rid} — {t.get('title','?')} | {status}"):
                st.markdown(
                    f"<span class='spill' style='background:{bg};color:{fg}'>{status}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Requester:** {t.get('requester','–')} | "
                    f"**Dept:** {t.get('department','–')} | "
                    f"**Submitted:** {_fmt(t.get('created_at',''))}"
                )
                if t.get("reviewer_note"):
                    st.markdown(
                        f"<div style='background:#f0fdf4;border-left:4px solid #059669;"
                        f"border-radius:8px;padding:10px;font-size:13px;margin-top:6px'>"
                        f"💬 {t['reviewer_note']}</div>",
                        unsafe_allow_html=True,
                    )
                if st.button("🗑️ Delete", key=f"hdel_{rid}"):
                    try:
                        _delete_task(rid)
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))

        with st.expander("📄 Supabase SQL — run once if columns missing"):
            st.code("""
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS stage_results TEXT;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS risk_level    TEXT DEFAULT 'Pending';
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS reviewer_note TEXT;
            """, language="sql")
