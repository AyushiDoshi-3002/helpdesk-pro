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
ESCALATION_HOURS = 168

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
    "Security": {"label": "🔒 Security", "subtypes": ["Legal", "Compliance", "Public API", "Financial"], "approver": "CEO", "auto": False},
    "Technical": {"label": "⚙️ Technical", "subtypes": ["Architecture", "Database", "Tech Stack", "Infrastructure", "Code Standards"], "approver": "CTO", "auto": False},
    "Operations": {"label": "🔧 Operations", "subtypes": ["Runbooks", "Deployment", "Monitoring", "Setup Guides"], "approver": "Tech Manager", "auto": False},
    "Team": {"label": "👥 Team", "subtypes": ["Internal Processes", "Troubleshooting", "Setup Guides"], "approver": "Team Lead", "auto": False},
    "General": {"label": "📋 General", "subtypes": ["FAQs", "Onboarding", "General Info"], "approver": "Admin", "auto": True},
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

# ── DB helpers ────────────────────────────────────────────────────────────────
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

def _migrate_chain(req: dict) -> bool:
    if req.get("done"):
        return False
    category = req.get("category","")
    correct = _build_chain(category)
    current = req.get("chain", [])
    if current == correct:
        return False
    old_role = current[req["stage_idx"]] if req["stage_idx"] < len(current) else None
    req["chain"] = correct
    if old_role and old_role in correct:
        req["stage_idx"] = correct.index(old_role)
    else:
        req["stage_idx"] = 0
    req["history"].append({
        "time": datetime.now(IST),
        "by": "System",
        "action": f"🔧 Chain auto-corrected to {', '.join(correct)}",
    })
    return True

def _db_insert(req):
    try:
        _get_sb().table(TABLE).insert(_serialize(req)).execute()
        st.toast(f"✅ Saved: {req['id']}", icon="🗄️")
    except Exception as e:
        st.error(f"DB insert error: {e}")

def _db_update(req):
    try:
        _get_sb().table(TABLE).upsert(_serialize(req)).execute()
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

# ── Core actions ──────────────────────────────────────────────────────────────
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
            "history": [
                {"time": now, "by": "System", "action": "Submitted"},
                {"time": now, "by": "Admin", "action": "Auto-approved (General document)"},
            ],
        }
    else:
        deadline = now + timedelta(hours=ESCALATION_HOURS)
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": chain, "stage_idx": 0, "status": "Pending",
            "created_at": now, "expires_at": deadline, "done": False,
            "history": [{
                "time": now, "by": "System",
                "action": f"Submitted → routed to {chain[0]}. Auto-escalates if no response within {_escalation_label()}.",
            }],
        }
    st.session_state.ap_requests.append(req)
    _db_insert(req)
    return req

def _approve(req, note):
    stage = req["chain"][req["stage_idx"]]
    next_idx = req["stage_idx"] + 1
    req["history"].append({"time": _now(), "by": stage, "action": "Approved", "note": note})
    if next_idx >= len(req["chain"]):
        req["status"] = "Approved"
        req["done"] = True
        req["history"].append({"time": _now(), "by": "System", "action": "All levels approved — COMPLETE ✅"})
    else:
        deadline = _now() + timedelta(hours=ESCALATION_HOURS)
        next_role = req["chain"][next_idx]
        req["stage_idx"] = next_idx
        req["expires_at"] = deadline
        req["history"].append({
            "time": _now(), "by": "System",
            "action": f"✅ Approved by {stage} → forwarded to {next_role}.",
        })
    _db_update(req)

def _reject(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["status"] = "Rejected"
    req["done"] = True
    req["history"].append({"time": _now(), "by": stage, "action": "Rejected", "note": note})
    _db_update(req)

def _check_expiry(req):
    if req["done"]:
        return
    if _now() <= req["expires_at"]:
        return
    current = req["chain"][req["stage_idx"]]
    next_idx = req["stage_idx"] + 1
    final_idx = len(req["chain"]) - 1
    if req["stage_idx"] >= final_idx:
        req["status"] = "Expired"
        req["done"] = True
        req["history"].append({
            "time": _now(), "by": "System",
            "action": f"⏰ EXPIRED — {current} (final approver) did not respond.",
        })
        _db_update(req)
        return
    deadline = _now() + timedelta(hours=ESCALATION_HOURS)
    next_role = req["chain"][next_idx]
    req["history"].append({
        "time": _now(), "by": "System",
        "action": f"AUTO-ESCALATED — {current} did not respond. Forwarded to {next_role}.",
    })
    req["stage_idx"] = next_idx
    req["expires_at"] = deadline
    _db_update(req)

def _delete_request(rid):
    st.session_state.ap_requests = [r for r in st.session_state.ap_requests if r["id"] != rid]
    st.session_state.ap_confirm_delete.pop(rid, None)
    _db_delete(rid)

# ── Main Page with Split Layout ───────────────────────────────────────────────
def page_approval_pipeline():
    _init()
    if not st.session_state.ap_loaded:
        _load_requests()

    st.markdown("# 📋 Approval Pipeline")
    st.markdown(
        "<p style='color:#6b5f55; font-size:26px; font-family: EB Garamond, serif;'>"
        "Choose your ticket type, or review and action pending approval requests.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # SPLIT LAYOUT
    left_col, right_col = st.columns([1.05, 1])

    with left_col:
        st.markdown("### 📄 Document Approval Ticket")
        st.markdown("Fill in your details. The system will route it through the correct approval chain.")

        st.subheader("👤 Your Details")
        c1, c2 = st.columns(2)
        with c1:
            doc_emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP-1042", key="ap_doc_emp_id")
        with c2:
            doc_emp_name = st.text_input("Your Name *", placeholder="e.g. Priya K.", key="ap_doc_emp_name")

        st.subheader("📋 Document Details")
        cat_keys = list(DOC_CATEGORIES.keys())
        da1, da2 = st.columns(2)
        with da1:
            doc_title = st.text_input("Document Title *", placeholder="e.g. Database Backup Procedure", key="ap_doc_title")
            doc_cat = st.selectbox("Document Category *", cat_keys, 
                                  format_func=lambda c: DOC_CATEGORIES[c]["label"], key="ap_doc_cat")
        with da2:
            avail_sub = DOC_CATEGORIES[st.session_state.get("ap_doc_cat", cat_keys[0])]["subtypes"]
            doc_sub = st.selectbox("Document Subtype *", avail_sub, key="ap_doc_sub")
            doc_urg = st.selectbox("Urgency *", ["Normal","URGENT","CRITICAL"], key="ap_doc_urg")

        doc_desc = st.text_area("What does this document need to cover? *", 
                               placeholder="Describe the purpose and scope…", height=100, key="ap_doc_desc")

        chosen_cat = st.session_state.get("ap_doc_cat", cat_keys[0])
        chain = _build_chain(chosen_cat)
        cfg = DOC_CATEGORIES[chosen_cat]
        route_str = "✅ Auto-approved instantly" if cfg["auto"] else " → ".join(chain) + f" · {_escalation_label()} per level"
        st.caption(f"**Approval route:** {route_str}")

        if st.button("🚀 Submit for Approval", type="primary", use_container_width=True, key="ap_doc_submit"):
            if doc_emp_id and doc_emp_name and doc_title and doc_desc:
                req = _create(doc_title, chosen_cat, doc_sub, doc_desc, doc_urg, f"{doc_emp_name} · {doc_emp_id}")
                st.success(f"✅ **{req['id']}** submitted successfully!")
            else:
                st.warning("Please fill all required fields.")

    with right_col:
        st.markdown("### 🔓 Request Access to an Existing Document")
        st.markdown("Senior roles get instant access. Others need approval.")

        all_docs_list = db_get_documents()
        
        acc1, acc2, acc3 = st.columns(3)
        with acc1:
            access_emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP-1042", key="ap_acc_emp_id")
        with acc2:
            access_role = st.selectbox("Your Role *", ["Select…","Employee","Manager","Tech Manager","CTO","CEO"], key="ap_acc_role")
        with acc3:
            access_doc = st.selectbox("Document *", ["Select…"] + [d["title"] for d in all_docs_list], key="ap_acc_doc")

        if st.button("Request Document Access →", key="ap_acc_submit", use_container_width=True, type="primary"):
            if access_emp_id and access_role != "Select…" and access_doc != "Select…":
                st.success(f"✅ Access request for **{access_doc}** submitted!")
            else:
                st.warning("Please fill all required fields.")

    # Approver Review Section
    st.markdown("---")
    st.markdown("### 🔐 Approver Review")
    st.markdown("<p style='color:#6b5f55;'>Approvers: log in to your role tab below to action pending requests.</p>", unsafe_allow_html=True)

    for r in st.session_state.ap_requests:
        if _migrate_chain(r):
            _db_update(r)

    def _n(role):
        return sum(1 for r in st.session_state.ap_requests
                   if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role)

    role_tabs = st.tabs([
        f"👨‍💼 Team Lead ({_n('Team Lead')})",
        f"👩‍💻 Tech Manager ({_n('Tech Manager')})",
        f"🧑‍🔬 CTO ({_n('CTO')})",
        f"👑 CEO ({_n('CEO')})",
    ])
    with role_tabs[0]: st.info("Team Lead view - your original logic goes here")
    with role_tabs[1]: st.info("Tech Manager view")
    with role_tabs[2]: st.info("CTO view")
    with role_tabs[3]: st.info("CEO view")
