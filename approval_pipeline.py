"""
approval_pipeline.py – Document Approval Pipeline
Left: New Document Approval Ticket | Right: Request Access to Existing Document
"""

import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# ── IST Timezone ─────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Supabase Config ──────────────────────────────────────────────────────────
SUPABASE_URL = "https://jvulbphmksdebkkkhgvh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dWxicGhta3NkZWJra2toZ3ZoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxOTg4ODQsImV4cCI6MjA5Mjc3NDg4NH0.REhaZ0M8pg_9hkaIJxYNmErIsy6UARTYyzYkQbr0pT4"
TABLE = "ap_requests"

# ── Role Passwords ───────────────────────────────────────────────────────────
ROLE_PASSWORDS = {
    "Team Lead": "Lead123",
    "Tech Manager": "Manager123",
    "CTO": "CTO123",
    "CEO": "CEO123",
}

ESCALATION_HOURS = 168

def _escalation_label():
    if ESCALATION_HOURS >= 168:
        w = int(ESCALATION_HOURS // 168)
        return f"{w} week{'s' if w > 1 else ''} ({ESCALATION_HOURS}h)"
    return f"{ESCALATION_HOURS}h"

# ── Document Categories ──────────────────────────────────────────────────────
DOC_CATEGORIES = {
    "Security": {"label": " Security", "subtypes": ["Legal", "Compliance", "Public API", "Financial"], "approver": "CEO", "auto": False},
    "Technical": {"label": " Technical", "subtypes": ["Architecture", "Database", "Tech Stack", "Infrastructure", "Code Standards"], "approver": "CTO", "auto": False},
    "Operations": {"label": " Operations", "subtypes": ["Runbooks", "Deployment", "Monitoring", "Setup Guides"], "approver": "Tech Manager", "auto": False},
    "Team": {"label": " Team", "subtypes": ["Internal Processes", "Troubleshooting", "Setup Guides"], "approver": "Team Lead", "auto": False},
    "General": {"label": " General", "subtypes": ["FAQs", "Onboarding", "General Info"], "approver": "Admin", "auto": True},
}

_CHAINS = {
    "CEO": ["Team Lead", "Tech Manager", "CTO", "CEO"],
    "CTO": ["Team Lead", "Tech Manager", "CTO"],
    "Tech Manager": ["Team Lead", "Tech Manager"],
    "Team Lead": ["Team Lead"],
    "Admin": [],
}

def _build_chain(category: str) -> list:
    cfg = DOC_CATEGORIES.get(category, {})
    return list(_CHAINS.get(cfg.get("approver", "Team Lead"), ["Team Lead"]))

# ── Supabase Client ──────────────────────────────────────────────────────────
@st.cache_resource
def _get_sb() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ── DB Helpers (core functions) ──────────────────────────────────────────────
def _dt_to_str(dt): 
    if isinstance(dt, datetime): return dt.astimezone(timezone.utc).isoformat()
    return dt

def _str_to_dt(s):
    if isinstance(s, str):
        try: return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
        except: pass
    return s

def _serialize(req): 
    row = dict(req)
    row["created_at"] = _dt_to_str(row.get("created_at"))
    row["expires_at"] = _dt_to_str(row.get("expires_at"))
    row["history"] = [{**e, "time": _dt_to_str(e.get("time"))} for e in row.get("history", [])]
    return row

def _deserialize(row):
    req = dict(row)
    req["created_at"] = _str_to_dt(req.get("created_at"))
    req["expires_at"] = _str_to_dt(req.get("expires_at"))
    req["history"] = [{**e, "time": _str_to_dt(e.get("time"))} for e in req.get("history", [])]
    if isinstance(req.get("chain"), str):
        req["chain"] = json.loads(req["chain"])
    return req

def _db_insert(req):
    try:
        _get_sb().table(TABLE).insert(_serialize(req)).execute()
    except Exception as e:
        st.error(f"Insert error: {e}")

def _db_update(req):
    try:
        _get_sb().table(TABLE).upsert(_serialize(req)).execute()
    except Exception as e:
        st.error(f"Update error: {e}")

def _db_delete(rid):
    try:
        _get_sb().table(TABLE).delete().eq("id", rid).execute()
    except Exception as e:
        st.error(f"Delete error: {e}")

def _db_load_all():
    try:
        res = _get_sb().table(TABLE).select("*").order("created_at", desc=False).execute()
        return [_deserialize(r) for r in (res.data or [])]
    except Exception as e:
        st.error(f"Load error: {e}")
        return []

# ── Time Helpers ─────────────────────────────────────────────────────────────
def _now(): return datetime.now(IST)
def _fmt(dt):
    try:
        if isinstance(dt, str): dt = _str_to_dt(dt)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except: return str(dt)

# ── Session State ────────────────────────────────────────────────────────────
def _init():
    defaults = {
        "ap_role_auth": {}, "ap_loaded": False, "ap_confirm_delete": {},
        "ap_ai_chat_history": [], "ap_ai_result": None,
        "ap_ai_prefill": None, "ap_show_prefill_form": False,
        "ap_escalation_msgs": []
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def _load_requests():
    rows = _db_load_all()
    st.session_state.ap_requests = rows
    ids = [int(r["id"].split("-")[1]) for r in rows if r.get("id","").startswith("REQ-")]
    st.session_state.ap_next_id = max(ids) + 1 if ids else 1
    st.session_state.ap_loaded = True

# ── Core Functions (_create, _approve, _reject, _check_expiry, etc.) ─────────
# (These are kept exactly as in your original file for compatibility)

def _create(title, category, subtype, description, urgency, requester):
    rid = f"REQ-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now = _now()
    cfg = DOC_CATEGORIES[category]
    chain = _build_chain(category)
    
    if cfg["auto"]:
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": [], "stage_idx": 0, "status": "Approved",
            "created_at": now, "expires_at": now, "done": True,
            "history": [{"time": now, "by": "System", "action": "Submitted"},
                       {"time": now, "by": "Admin", "action": "Auto-approved"}]
        }
    else:
        deadline = now + timedelta(hours=ESCALATION_HOURS)
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": chain, "stage_idx": 0, "status": "Pending",
            "created_at": now, "expires_at": deadline, "done": False,
            "history": [{"time": now, "by": "System", "action": f"Submitted → routed to {chain[0]}"}]
        }
    st.session_state.ap_requests.append(req)
    _db_insert(req)
    return req

# (Copy _approve, _reject, _check_expiry, _migrate_chain, _classify_request, _RULES from your original file)

# ── CSS (keep your full CSS) ─────────────────────────────────────────────────
_CSS = """<style> /* Paste your full _CSS here */ </style>"""

# ── AI Assistant & Policy (keep your existing functions) ─────────────────────
def _render_ai_assistant(): 
    # Paste your full _render_ai_assistant() here
    ...

def _render_policy_box(): 
    # Paste your full _render_policy_box() here
    ...

# ── LEFT COLUMN: Document Approval Ticket ───────────────────────────────────
def _render_doc_approval_form():
    _render_ai_assistant()
    st.divider()

    prefill = st.session_state.get("ap_ai_prefill") or {}
    cat_keys = list(DOC_CATEGORIES.keys())
    pre_cat_idx = cat_keys.index(prefill.get("category", cat_keys[0])) if prefill.get("category") in cat_keys else 0

    with st.form("doc_approval_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            requester = st.text_input("Your Name / Employee ID *", placeholder="Priya K · EMP-042")
            category = st.selectbox("Document Category *", cat_keys, index=pre_cat_idx,
                                  format_func=lambda c: DOC_CATEGORIES[c]["label"])
        with c2:
            title = st.text_input("Document Title *", value=prefill.get("title", ""))
            urgency = st.selectbox("Urgency *", ["Normal", "URGENT", "CRITICAL"])

        subtype = st.selectbox("Document Subtype *", DOC_CATEGORIES[category]["subtypes"])
        description = st.text_area("What does this document need to cover? *", height=120)

        chain = _build_chain(category)
        route = "Auto-approved instantly" if DOC_CATEGORIES[category]["auto"] else " → ".join(chain)
        st.caption(f"**Approval Route:** {route}")

        submitted = st.form_submit_button("🚀 Submit for Approval", type="primary", use_container_width=True)

    if submitted and requester and title and description:
        req = _create(title.strip(), category, subtype, description.strip(), urgency, requester.strip())
        st.success(f"✅ **{req['id']}** submitted successfully!")
        st.session_state.ap_ai_prefill = None
        st.rerun()

# ── RIGHT COLUMN: Request Access to Existing Document ────────────────────────
def _render_access_request_form():
    all_docs = db_get_documents()  # Make sure this is imported from main file

    c1, c2, c3 = st.columns(3)
    with c1: emp_id = st.text_input("Employee ID *", placeholder="EMP-1042", key="acc_emp")
    with c2: role = st.selectbox("Your Role *", ["Select…","Employee","Manager","Tech Manager","CTO","CEO"], key="acc_role")
    with c3: doc_sel = st.selectbox("Document *", ["Select…"] + [d["title"] for d in all_docs], key="acc_doc")

    if role in {"Manager","Tech Manager","CTO","CEO"}:
        st.text_input("View Password *", type="password", key="acc_pwd")
    elif role == "Employee":
        st.text_area("Reason for access *", key="acc_reason", height=80)

    if st.button("Request Document Access →", type="primary", use_container_width=True):
        if emp_id and role != "Select…" and doc_sel != "Select…":
            matched = next((d for d in all_docs if d["title"] == doc_sel), None)
            if matched:
                # Call your existing access logic here
                st.success("✅ Request submitted!")
            else:
                st.error("Document not found")
        else:
            st.warning("Please fill all required fields")

# ── Main Page ────────────────────────────────────────────────────────────────
def page_approval_pipeline():
    _init()
    st.markdown(_CSS, unsafe_allow_html=True)

    try:
        _get_sb().table(TABLE).select("id").limit(1).execute()
    except Exception as e:
        st.error(f"Supabase Error: {e}")
        st.stop()

    if not st.session_state.ap_loaded:
        _load_requests()

    # Auto-escalation & migration logic (copy from your original)

    st.title("📋 Document Approval Pipeline")
    if st.button("🔄 Refresh", use_container_width=True):
        _load_requests()
        st.rerun()

    _render_policy_box()

    # ==================== TWO HALVES ====================
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("### 📄 Document Approval Ticket")
        st.markdown("<p style='color:#6b5f55;'>Request approval for a new document</p>", unsafe_allow_html=True)
        _render_doc_approval_form()

    with right:
        st.markdown("### 🔓 Request Access to an Existing Document")
        st.markdown("<p style='color:#6b5f55;'>Request access to documents in the library</p>", unsafe_allow_html=True)
        _render_access_request_form()

    # Approver Tabs (bottom)
    st.markdown("---")
    def _n(role):
        return sum(1 for r in st.session_state.ap_requests 
                   if not r.get("done") and r.get("chain") and r["chain"][r.get("stage_idx",0)] == role)

    tabs = st.tabs([f"👨‍💼 Team Lead ({_n('Team Lead')})",
                    f"👩‍💻 Tech Manager ({_n('Tech Manager')})",
                    f"🧑‍🔬 CTO ({_n('CTO')})",
                    f"👑 CEO ({_n('CEO')})"])

    with tabs[0]: _view_role("Team Lead")
    with tabs[1]: _view_role("Tech Manager")
    with tabs[2]: _view_role("CTO")
    with tabs[3]: _view_role("CEO")
