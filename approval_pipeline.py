"""
approval_pipeline.py – role-based tabs + Supabase persistence + AI Assistant
                          + Auto-escalation: 1 week (168h) per level
"""
import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# ── IST Timezone (UTC+5:30) ───────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Supabase config ───────────────────────────────────────────────────────────
SUPABASE_URL = "https://jvulbphmksdebkkkhgvh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dWxicGhta3NkZWJra2toZ3ZoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxOTg4ODQsImV4cCI6MjA5Mjc3NDg4NH0.REhaZ0M8pg_9hkaIJxYNmErIsy6UARTYyzYkQbr0pT4"
TABLE = "ap_requests"

# ── Role passwords ────────────────────────────────────────────────────────────
ROLE_PASSWORDS = {
    "Team Lead": "Lead123",
    "Tech Manager": "Manager123",
    "CTO": "CTO123",
    "CEO": "CEO123",
}

# ── Escalation timer ──────────────────────────────────────────────────────────
ESCALATION_HOURS = 168  # Change to 0.05 for testing (≈3 minutes)

def _escalation_label():
    if ESCALATION_HOURS >= 168 and ESCALATION_HOURS % 168 == 0:
        w = int(ESCALATION_HOURS // 168)
        return f"{w} week{'s' if w > 1 else ''} ({int(ESCALATION_HOURS)}h)"
    elif ESCALATION_HOURS >= 24:
        d = int(ESCALATION_HOURS // 24)
        return f"{d} day{'s' if d > 1 else ''} ({int(ESCALATION_HOURS)}h)"
    else:
        return f"{ESCALATION_HOURS}h"

# ── Document taxonomy ─────────────────────────────────────────────────────────
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

# ── Supabase client ───────────────────────────────────────────────────────────
@st.cache_resource
def _get_sb() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ── DB helpers (same as before) ───────────────────────────────────────────────
def _dt_to_str(dt):
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return dt

def _str_to_dt(s):
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    if isinstance(s, str):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return s

def _serialize(req: dict) -> dict:
    row = dict(req)
    row["created_at"] = _dt_to_str(row.get("created_at"))
    row["expires_at"] = _dt_to_str(row.get("expires_at"))
    history = []
    for entry in row.get("history", []):
        e = dict(entry)
        e["time"] = _dt_to_str(e.get("time"))
        history.append(e)
    row["history"] = history
    return row

def _deserialize(row: dict) -> dict:
    req = dict(row)
    req["created_at"] = _str_to_dt(req.get("created_at"))
    req["expires_at"] = _str_to_dt(req.get("expires_at"))
    history = []
    for entry in (req.get("history") or []):
        e = dict(entry)
        e["time"] = _str_to_dt(e.get("time"))
        history.append(e)
    req["history"] = history
    if not isinstance(req.get("chain"), list):
        req["chain"] = json.loads(req["chain"]) if req.get("chain") else []
    return req

# ... (keeping all other DB functions, _migrate_chain, _db_insert, etc. unchanged for brevity - they remain the same as your original)

def _db_insert(req):
    try:
        res = _get_sb().table(TABLE).insert(_serialize(req)).execute()
        if res.data:
            st.toast(f"✅ Saved: {req['id']}", icon="🗄️")
    except Exception as e:
        st.error(f"DB insert error: {e}")

def _db_update(req):
    try:
        res = _get_sb().table(TABLE).upsert(_serialize(req)).execute()
        if res.data:
            st.toast(f"✅ Updated: {req['id']}", icon="🗄️")
    except Exception as e:
        st.error(f"DB update error: {e}")

def _db_delete(rid):
    try:
        _get_sb().table(TABLE).delete().eq("id", rid).execute()
        st.toast(f"🗑️ Deleted {rid}", icon="🗄️")
    except Exception as e:
        st.error(f"DB delete error: {e}")

def _db_load_all():
    try:
        res = _get_sb().table(TABLE).select("*").order("created_at", desc=False).execute()
        rows = res.data or []
        st.caption(f" Loaded {len(rows)} record(s) from Supabase.")
        return [_deserialize(r) for r in rows]
    except Exception as e:
        st.error(f"DB load error: {e}")
        return []

# ── Time helpers ──────────────────────────────────────────────────────────────
def _now():
    return datetime.now(IST)

def _fmt(dt):
    try:
        if isinstance(dt, str):
            dt = _str_to_dt(dt)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return str(dt)

def _time_left(expires_at):
    if isinstance(expires_at, str):
        expires_at = _str_to_dt(expires_at)
    secs = int((expires_at - _now()).total_seconds())
    if secs <= 0:
        return " Escalating now…"
    h, rem = divmod(secs, 3600)
    m = rem // 60
    if h >= 24:
        d = h // 24; hr = h % 24
        return f" {d}d {hr}h before auto-escalation"
    return f" {h}h {m}m before auto-escalation" if h else f"⏳ {m}m before auto-escalation"

# ── Session state ─────────────────────────────────────────────────────────────
def _init():
    for k, v in {
        "ap_role_auth": {}, "ap_loaded": False, "ap_confirm_delete": {},
        "ap_ai_chat_history": [], "ap_ai_result": None,
        "ap_ai_prefill": None, "ap_show_prefill_form": False,
        "ap_escalation_msgs": [],
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _load_requests():
    rows = _db_load_all()
    st.session_state.ap_requests = rows
    ids = [int(r["id"].split("-")[1]) for r in rows if r.get("id","").startswith("REQ-")]
    st.session_state.ap_next_id = (max(ids) + 1) if ids else 1
    st.session_state.ap_loaded = True

# ── Core actions (_create, _approve, _reject, _check_expiry, _delete_request) remain the same as your original ──
# (I'm keeping them unchanged to avoid errors)

def _create(title, category, subtype, description, urgency, requester):
    rid = f"REQ-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now = _now()
    cfg = DOC_CATEGORIES[category]
    chain = _build_chain(category)
    if cfg["auto"]:
        req = {"id": rid, "title": title, "category": category, "subtype": subtype,
               "description": description, "urgency": urgency, "requester": requester,
               "chain": [], "stage_idx": 0, "status": "Approved",
               "created_at": now, "expires_at": now, "done": True,
               "history": [
                   {"time": now, "by": "System", "action": "Submitted"},
                   {"time": now, "by": "Admin", "action": "Auto-approved (General document)"},
               ]}
    else:
        deadline = now + timedelta(hours=ESCALATION_HOURS)
        req = {"id": rid, "title": title, "category": category, "subtype": subtype,
               "description": description, "urgency": urgency, "requester": requester,
               "chain": chain, "stage_idx": 0, "status": "Pending",
               "created_at": now, "expires_at": deadline, "done": False,
               "history": [{"time": now, "by": "System", "action": f"Submitted → routed to {chain[0]}. Auto-escalates within {_escalation_label()}."}]}
    st.session_state.ap_requests.append(req)
    _db_insert(req)
    return req

# ... (_approve, _reject, _check_expiry, _delete_request, _migrate_chain, _classify_request, _RULES etc. are unchanged - copy from your original if needed)

# ── CSS (unchanged) ───────────────────────────────────────────────────────────
_CSS = """<style> ... (your full CSS here) ... </style>"""   # Keep your existing _CSS

# ── AI Assistant & Policy Box (unchanged) ─────────────────────────────────────
def _render_ai_assistant():
    # Your existing _render_ai_assistant function
    ...

def _render_policy_box():
    # Your existing _render_policy_box
    ...

# ── NEW: Document Approval Form (Left Column) ────────────────────────────────
def _render_doc_approval_form():
    _render_ai_assistant()
    st.divider()

    prefill = st.session_state.get("ap_ai_prefill") or {}
    show_prefill = st.session_state.get("ap_show_prefill_form", False)

    cat_keys = list(DOC_CATEGORIES.keys())
    pre_cat = prefill.get("category", cat_keys[0])
    if pre_cat not in cat_keys: pre_cat = cat_keys[0]
    pre_cat_idx = cat_keys.index(pre_cat)

    with st.form("ap_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            requester = st.text_input("Your Name / Employee ID *", placeholder="e.g. Priya K · EMP-042")
            category = st.selectbox("Document Category *", cat_keys, index=pre_cat_idx,
                                    format_func=lambda c: DOC_CATEGORIES[c]["label"])
        with c2:
            title = st.text_input("Document Title *", value=prefill.get("title",""), placeholder="e.g. Database Backup Procedure")
            urgency = st.selectbox("Urgency *", ["Normal","URGENT","CRITICAL"])

        avail_sub = DOC_CATEGORIES[category]["subtypes"]
        subtype = st.selectbox("Document Subtype *", avail_sub)

        description = st.text_area("What does this document need to cover? *", placeholder="Describe the purpose...", height=120)

        cfg = DOC_CATEGORIES[category]
        chain = _build_chain(category)
        route_str = "Auto-approved instantly" if cfg["auto"] else " → ".join(chain) + f" · {_escalation_label()} per level"
        st.caption(f"**Approval route:** {route_str}")

        bc1, bc2, _ = st.columns([2,1,3])
        with bc1:
            submitted = st.form_submit_button("🚀 Submit for Approval", type="primary", use_container_width=True)
        with bc2:
            if show_prefill and st.form_submit_button("✖ Clear Prefill", use_container_width=True):
                st.session_state.ap_ai_prefill = None
                st.session_state.ap_show_prefill_form = False
                st.rerun()

    if submitted:
        # validation and _create logic (same as before)
        if not requester.strip() or not title.strip() or not description.strip():
            st.error("All fields are required.")
        else:
            req = _create(title.strip(), category, subtype, description.strip(), urgency, requester.strip())
            st.session_state.ap_ai_prefill = None
            st.session_state.ap_show_prefill_form = False
            st.success(f"✅ Request **{req['id']}** submitted successfully!")

# ── NEW: Access Request Form (Right Column) ───────────────────────────────────
def _render_access_request_form():
    all_docs = db_get_documents()  # from main script

    c1, c2, c3 = st.columns(3)
    with c1:
        emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP-1042", key="acc_emp_id")
    with c2:
        role = st.selectbox("Your Role *", ["Select…","Employee","Manager","Tech Manager","CTO","CEO"], key="acc_role")
    with c3:
        doc_title = st.selectbox("Document *", ["Select…"] + [d["title"] for d in all_docs], key="acc_doc")

    if role in {"Manager","Tech Manager","CTO","CEO"}:
        st.text_input("View Password *", type="password", key="acc_pwd")
    elif role == "Employee":
        st.text_area("Reason for access *", key="acc_reason", height=80)

    if st.button("Request Document Access →", type="primary", use_container_width=True):
        # validation + logic (same as your original)
        ...

# ── Main Page Function ────────────────────────────────────────────────────────
def page_approval_pipeline():
    _init()
    st.markdown(_CSS, unsafe_allow_html=True)

    # Supabase check, load, migrate, escalation logic (unchanged)
    # ... (copy your original logic here)

    st.title("📋 Document Approval Pipeline")
    if st.button("🔄 Refresh"):
        _load_requests()
        st.rerun()

    _render_policy_box()

    # ==================== TWO HALVES LAYOUT ====================
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("### 📄 Document Approval Ticket")
        _render_doc_approval_form()

    with right:
        st.markdown("### 🔓 Request Access to an Existing Document")
        _render_access_request_form()

    # Approver Review Tabs
    st.markdown("---")
    def _n(role):
        return sum(1 for r in st.session_state.ap_requests
                   if not r["done"] and r["chain"] and r["chain"][r.get("stage_idx",0)] == role)

    tabs = st.tabs([
        f"👨‍💼 Team Lead ({_n('Team Lead')})",
        f"👩‍💻 Tech Manager ({_n('Tech Manager')})",
        f"🧑‍🔬 CTO ({_n('CTO')})",
        f"👑 CEO ({_n('CEO')})",
    ])

    with tabs[0]: _view_role("Team Lead")
    with tabs[1]: _view_role("Tech Manager")
    with tabs[2]: _view_role("CTO")
    with tabs[3]: _view_role("CEO")
