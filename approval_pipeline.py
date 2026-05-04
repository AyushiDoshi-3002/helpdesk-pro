"""
approval_pipeline.py  –  role-based tabs + Supabase persistence
Dark-theme redesign matching app.py aesthetic.
"""

import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

IST = timezone(timedelta(hours=5, minutes=30))

SUPABASE_URL = "https://jvulbphmksdebkkkhgvh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dWxicGhta3NkZWJra2toZ3ZoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxOTg4ODQsImV4cCI6MjA5Mjc3NDg4NH0.REhaZ0M8pg_9hkaIJxYNmErIsy6UARTYyzYkQbr0pT4"
TABLE = "ap_requests"

ROLE_PASSWORDS = {
    "Team Lead":    "Lead123",
    "Tech Manager": "Manager123",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

TIMEOUT_HOURS = 2

DOC_CATEGORIES = {
    "Security": {
        "label":    "🔒 Security",
        "subtypes": ["Legal","Compliance","Public API","Financial"],
        "approver": "CEO",
        "auto":     False,
    },
    "Technical": {
        "label":    "⚙️ Technical",
        "subtypes": ["Architecture","Database","Tech Stack","Infrastructure","Code Standards"],
        "approver": "CTO",
        "auto":     False,
    },
    "Operations": {
        "label":    "🔧 Operations",
        "subtypes": ["Runbooks","Deployment","Monitoring","Setup Guides"],
        "approver": "Tech Manager",
        "auto":     False,
    },
    "Team": {
        "label":    "👥 Team",
        "subtypes": ["Internal Processes","Troubleshooting","Setup Guides"],
        "approver": "Team Lead",
        "auto":     False,
    },
    "General": {
        "label":    "📄 General",
        "subtypes": ["FAQs","Onboarding","General Info"],
        "approver": "Admin",
        "auto":     True,
    },
}

_CHAINS = {
    "CEO":          ["Team Lead","Tech Manager","CTO","CEO"],
    "CTO":          ["Team Lead","Tech Manager","CTO"],
    "Tech Manager": ["Team Lead","Tech Manager"],
    "Team Lead":    ["Team Lead"],
    "Admin":        [],
}

def _build_chain(category: str) -> list:
    cfg = DOC_CATEGORIES.get(category, {})
    return list(_CHAINS.get(cfg.get("approver","Team Lead"), ["Team Lead"]))


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
            dt = datetime.fromisoformat(s.replace("Z","+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return s

def _serialize(req: dict) -> dict:
    row = dict(req)
    row["created_at"] = _dt_to_str(row.get("created_at"))
    row["expires_at"] = _dt_to_str(row.get("expires_at"))
    history = []
    for entry in row.get("history",[]):
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

def _db_insert(req: dict):
    try:
        row = _serialize(req)
        res = _get_sb().table(TABLE).insert(row).execute()
        if hasattr(res,"data") and res.data:
            st.toast(f"✅ Saved: {req['id']}", icon="🗄️")
        else:
            st.warning(f"⚠️ Insert returned no data.")
    except Exception as e:
        st.error(f"❌ DB insert error for {req.get('id')}: {type(e).__name__}: {e}")

def _db_update(req: dict):
    try:
        row = _serialize(req)
        res = _get_sb().table(TABLE).upsert(row).execute()
        if hasattr(res,"data") and res.data:
            st.toast(f"✅ Updated: {req['id']}", icon="🗄️")
        else:
            st.warning(f"⚠️ Upsert returned no data.")
    except Exception as e:
        st.error(f"❌ DB update error for {req.get('id')}: {type(e).__name__}: {e}")

def _db_delete(rid: str):
    try:
        _get_sb().table(TABLE).delete().eq("id", rid).execute()
        st.toast(f"🗑️ Deleted {rid}", icon="🗄️")
    except Exception as e:
        st.error(f"❌ DB delete error for {rid}: {type(e).__name__}: {e}")

def _db_load_all() -> list:
    try:
        res = _get_sb().table(TABLE).select("*").order("created_at", desc=False).execute()
        rows = res.data or []
        return [_deserialize(row) for row in rows]
    except Exception as e:
        st.error(f"❌ DB load error: {type(e).__name__}: {e}")
        return []


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    diff = expires_at - _now()
    secs = int(diff.total_seconds())
    if secs <= 0:
        return "Expired"
    h, rem = divmod(secs, 3600)
    m, _   = divmod(rem, 60)
    return f"{h}h {m}m left" if h else f"{m}m left"


# ── Session-state init ────────────────────────────────────────────────────────

def _init():
    defaults = {
        "ap_role_auth":      {},
        "ap_loaded":         False,
        "ap_confirm_delete": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _load_requests():
    rows = _db_load_all()
    st.session_state.ap_requests = rows
    ids = [int(r["id"].split("-")[1]) for r in rows if r.get("id","").startswith("REQ-")]
    st.session_state.ap_next_id = (max(ids)+1) if ids else 1
    st.session_state.ap_loaded  = True


# ── Core actions ──────────────────────────────────────────────────────────────

def _create(title, category, subtype, description, urgency, requester):
    rid   = f"REQ-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now   = _now()
    cfg   = DOC_CATEGORIES[category]
    chain = _build_chain(category)
    auto  = cfg["auto"]

    if auto:
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": [], "stage_idx": 0, "status": "Approved",
            "created_at": now, "expires_at": now,
            "history": [
                {"time": now, "by": "System", "action": "Submitted"},
                {"time": now, "by": "Admin",  "action": "Auto-approved (General document)"},
            ],
            "done": True,
        }
    else:
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": chain, "stage_idx": 0, "status": "Pending",
            "created_at": now, "expires_at": now + timedelta(hours=TIMEOUT_HOURS),
            "history": [{"time": now, "by": "System",
                         "action": f"Submitted → routed to {chain[0]}"}],
            "done": False,
        }

    st.session_state.ap_requests.append(req)
    _db_insert(req)
    return req

def _approve(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["history"].append({"time": _now(), "by": stage, "action": "Approved", "note": note})
    next_idx = req["stage_idx"] + 1
    if next_idx >= len(req["chain"]):
        req["status"] = "Approved"
        req["done"]   = True
        req["history"].append({"time": _now(), "by": "System", "action": "All levels approved — COMPLETE ✅"})
    else:
        req["stage_idx"]  = next_idx
        req["expires_at"] = _now() + timedelta(hours=TIMEOUT_HOURS)
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Forwarded to {req['chain'][next_idx]}"})
    _db_update(req)

def _reject(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["status"] = "Rejected"
    req["done"]   = True
    req["history"].append({"time": _now(), "by": stage, "action": "Rejected", "note": note})
    _db_update(req)

def _check_expiry(req):
    if not req["done"] and _now() > req["expires_at"]:
        stage         = req["chain"][req["stage_idx"]]
        req["status"] = "Expired"
        req["done"]   = True
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Expired — no response from {stage}"})
        _db_update(req)

def _delete_request(rid: str):
    st.session_state.ap_requests = [r for r in st.session_state.ap_requests if r["id"] != rid]
    st.session_state.ap_confirm_delete.pop(rid, None)
    _db_delete(rid)


# ── Status badge helper ───────────────────────────────────────────────────────

def _status_badge(status: str) -> str:
    mapping = {
        "Pending":  ("badge-open",       "Pending"),
        "Approved": ("badge-resolved",   "Approved"),
        "Rejected": ("badge-overdue",    "Rejected"),
        "Expired":  ("badge-inprogress", "Expired"),
    }
    cls, label = mapping.get(status, ("badge-open", status))
    return f'<span class="badge {cls}">{label}</span>'

def _urgency_badge(urgency: str) -> str:
    if urgency == "CRITICAL":
        return '<span class="badge" style="background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3);">CRITICAL</span>'
    if urgency == "URGENT":
        return '<span class="badge" style="background:rgba(251,191,36,0.15);color:#fbbf24;border:1px solid rgba(251,191,36,0.3);">URGENT</span>'
    return '<span class="badge" style="background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.4);border:1px solid rgba(255,255,255,0.1);">Normal</span>'


# ── Main entry ────────────────────────────────────────────────────────────────

def page_approval_pipeline():
    _init()

    # ── Connection check ──────────────────────────────────────────────────────
    try:
        _get_sb().table(TABLE).select("id").limit(1).execute()
    except Exception as e:
        st.error(f"🔴 Supabase connection FAILED: {type(e).__name__}: {e}")
        st.stop()

    if not st.session_state.ap_loaded:
        _load_requests()

    for r in st.session_state.ap_requests:
        _check_expiry(r)

    # ── Page header ───────────────────────────────────────────────────────────
    hcol, rcol = st.columns([5, 1])
    with hcol:
        st.markdown("""
        <div class="page-header">
            <div class="page-title">Document Approval Pipeline</div>
            <div class="page-subtitle">Submit documents for role-based approval · 2h timeout per level</div>
        </div>
        """, unsafe_allow_html=True)
    with rcol:
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True):
            _load_requests()
            st.rerun()

    def _n(role):
        return sum(
            1 for r in st.session_state.ap_requests
            if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role
        )

    tabs = st.tabs([
        "📝 Submit",
        f"👤 Team Lead ({_n('Team Lead')})",
        f"🔧 Tech Manager ({_n('Tech Manager')})",
        f"⚙️ CTO ({_n('CTO')})",
        f"👑 CEO ({_n('CEO')})",
    ])

    with tabs[0]: _view_submit()
    with tabs[1]: _view_role("Team Lead")
    with tabs[2]: _view_role("Tech Manager")
    with tabs[3]: _view_role("CTO")
    with tabs[4]: _view_role("CEO")


# ── Submit Tab ────────────────────────────────────────────────────────────────

def _view_submit():
    st.markdown("<div class='section-label'>New Request</div>", unsafe_allow_html=True)

    with st.form("ap_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            requester = st.text_input("Your Name / Employee ID", placeholder="e.g. Priya K · EMP-042")
            category  = st.selectbox("Document Category", list(DOC_CATEGORIES.keys()),
                                     format_func=lambda c: DOC_CATEGORIES[c]["label"])
        with col2:
            title   = st.text_input("Document Title", placeholder="e.g. Database Backup Procedure")
            urgency = st.selectbox("Urgency", ["Normal","URGENT","CRITICAL"])

        subtype     = st.selectbox("Document Subtype", DOC_CATEGORIES[category]["subtypes"])
        description = st.text_area("What does this document need to cover?",
                                   placeholder="Describe the purpose and scope…", height=90)

        cfg       = DOC_CATEGORIES[category]
        chain     = _build_chain(category)
        route_str = (
            "Auto-approved instantly (General)"
            if cfg["auto"]
            else "  →  ".join(chain) + f"  ·  {TIMEOUT_HOURS}h per level"
        )
        st.markdown(f"<small style='color:rgba(139,92,246,0.7)'>Approval route: {route_str}</small>", unsafe_allow_html=True)

        submitted = st.form_submit_button("Submit Request", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not requester.strip():   errors.append("Name / Employee ID required.")
        if not title.strip():       errors.append("Document title required.")
        if not description.strip(): errors.append("Description required.")
        for e in errors:
            st.error(e)
        if not errors:
            req = _create(title.strip(), category, subtype, description.strip(), urgency, requester.strip())
            if req["done"]:
                st.success(f"**{req['id']}** auto-approved instantly ✅")
            else:
                st.success(f"**{req['id']}** submitted — first stop: **{req['chain'][0]}**")

    all_reqs = list(reversed(st.session_state.ap_requests))
    if not all_reqs:
        st.markdown("""
        <div class="hd-card" style="text-align:center; padding:32px; margin-top:16px;">
            <div style="font-size:28px; margin-bottom:10px;">📭</div>
            <div style="color:rgba(255,255,255,0.4); font-size:13.5px;">No requests yet. Submit your first document above.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    # Summary metrics
    counts = {"Pending":0,"Approved":0,"Rejected":0,"Expired":0}
    for r in all_reqs:
        counts[r["status"]] = counts.get(r["status"],0) + 1

    metric_map = [
        ("Pending",  counts["Pending"],  "metric-number metric-number-amber"),
        ("Approved", counts["Approved"], "metric-number metric-number-green"),
        ("Rejected", counts["Rejected"], "metric-number metric-number-red"),
        ("Expired",  counts["Expired"],  "metric-number metric-number-blue"),
    ]
    cols = st.columns(4)
    for col, (label, val, cls) in zip(cols, metric_map):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="{cls}">{val}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Bulk delete
    st.markdown("<div class='section-label'>All Requests</div>", unsafe_allow_html=True)
    bulk1, bulk2, _ = st.columns([1.5, 1.5, 4])
    with bulk1:
        if st.button("🗑️ Delete All Rejected", use_container_width=True):
            ids = [r["id"] for r in all_reqs if r["status"] == "Rejected"]
            for rid in ids: _delete_request(rid)
            st.success(f"Deleted {len(ids)} rejected.") if ids else st.info("None to delete.")
            if ids: st.rerun()
    with bulk2:
        if st.button("🗑️ Delete All Expired", use_container_width=True):
            ids = [r["id"] for r in all_reqs if r["status"] == "Expired"]
            for rid in ids: _delete_request(rid)
            st.success(f"Deleted {len(ids)} expired.") if ids else st.info("None to delete.")
            if ids: st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    for req in all_reqs:
        _request_card_with_delete(req, ctx="sub")


# ── Request card (Submit tab, with delete) ────────────────────────────────────

def _request_card_with_delete(req: dict, ctx: str = "sub"):
    stage    = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    timer    = _time_left(req["expires_at"]) if not req["done"] else ""
    rid      = req["id"]
    k        = f"{ctx}_{rid}"

    header_parts = [f"**{rid}**  ·  {req['title']}"]
    if timer and timer != "Expired":
        header_parts.append(f"⏳ {timer}")

    with st.expander("  ".join(header_parts), expanded=False):
        # Status row
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap;">
            {_status_badge(req['status'])}
            {_urgency_badge(req['urgency'])}
            <span style="font-size:12px; color:rgba(255,255,255,0.35);">{req.get('category','—')} › {req.get('subtype','—')}</span>
            <span style="margin-left:auto; font-size:11px; color:rgba(255,255,255,0.3);">Stage: {stage}</span>
        </div>
        """, unsafe_allow_html=True)

        # Details grid
        st.markdown(f"""
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px;">
            <div class="hd-card" style="padding:10px 14px;">
                <div style="font-size:10px; text-transform:uppercase; letter-spacing:0.8px; color:rgba(255,255,255,0.3); margin-bottom:4px;">Requester</div>
                <div style="font-size:13.5px; font-weight:500; color:rgba(255,255,255,0.85);">{req['requester']}</div>
            </div>
            <div class="hd-card" style="padding:10px 14px;">
                <div style="font-size:10px; text-transform:uppercase; letter-spacing:0.8px; color:rgba(255,255,255,0.3); margin-bottom:4px;">Submitted</div>
                <div style="font-size:13px; color:rgba(255,255,255,0.7);">{_fmt(req['created_at'])}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Description
        st.markdown(f"""
        <div class="answer-box" style="margin-bottom:14px; font-size:13.5px;">{req['description']}</div>
        """, unsafe_allow_html=True)

        # Approval chain
        if req["chain"]:
            chain_parts = []
            for i, s in enumerate(req["chain"]):
                if req["status"] == "Approved" or i < req["stage_idx"]:
                    chain_parts.append(f'<span style="color:rgba(52,211,153,0.7); text-decoration:line-through;">{s} ✅</span>')
                elif i == req["stage_idx"] and not req["done"]:
                    chain_parts.append(f'<span style="color:#a78bfa; font-weight:600;">{s} ⏳</span>')
                elif req["done"] and i == req["stage_idx"]:
                    icon = "❌" if req["status"] == "Rejected" else "⏰"
                    chain_parts.append(f'<span style="color:#f87171; font-weight:600;">{s} {icon}</span>')
                else:
                    chain_parts.append(f'<span style="color:rgba(255,255,255,0.3);">{s}</span>')
            chain_html = ' <span style="color:rgba(255,255,255,0.2);">→</span> '.join(chain_parts)
            st.markdown(f'<div style="font-size:13px; margin-bottom:14px;">{chain_html}</div>', unsafe_allow_html=True)

        # History
        with st.expander("History", key=f"hist_{k}"):
            for entry in req["history"]:
                t    = _fmt(entry.get("time",""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"""
                <div style="font-size:12.5px; color:rgba(255,255,255,0.6); margin-bottom:6px; padding:6px 10px; background:rgba(255,255,255,0.025); border-radius:8px;">
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:rgba(255,255,255,0.3);">{t}</span>
                    &nbsp; <strong style="color:rgba(255,255,255,0.75);">{entry['by']}</strong>: {entry['action']}{note}
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Delete controls
        is_pending_confirm = st.session_state.ap_confirm_delete.get(rid, False)
        if not is_pending_confirm:
            del_col, _ = st.columns([1, 5])
            with del_col:
                if st.button("🗑️ Delete", key=f"del_btn_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = True
                    st.rerun()
        else:
            st.markdown(f"""
            <div class="no-answer-box" style="margin-bottom:10px;">
                ⚠️ Are you sure you want to delete <strong>{rid} — {req['title']}</strong>? This cannot be undone.
            </div>
            """, unsafe_allow_html=True)
            conf1, conf2, _ = st.columns([1, 1, 4])
            with conf1:
                if st.button("✅ Yes, Delete", key=f"confirm_yes_{k}", use_container_width=True):
                    _delete_request(rid)
                    st.success(f"🗑️ {rid} deleted.")
                    st.rerun()
            with conf2:
                if st.button("✖ Cancel", key=f"confirm_no_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = False
                    st.rerun()


# ── Role tab ──────────────────────────────────────────────────────────────────

def _view_role(role: str):
    authed = st.session_state.ap_role_auth.get(role, False)

    if not authed:
        st.markdown(f"""
        <div class="page-header" style="margin-top:8px;">
            <div class="page-title" style="font-size:22px;">🔐 {role} Login</div>
            <div class="page-subtitle">Enter your role password to access the inbox</div>
        </div>
        """, unsafe_allow_html=True)
        col, _ = st.columns([1.5, 3])
        with col:
            pwd = st.text_input("Password", type="password", key=f"pwd_{role}")
            if st.button("Log in →", type="primary", use_container_width=True, key=f"login_{role}"):
                if pwd == ROLE_PASSWORDS.get(role,""):
                    st.session_state.ap_role_auth[role] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    hcol, lcol = st.columns([6, 1])
    with hcol:
        st.markdown(f"""
        <div class="page-header" style="margin-top:8px;">
            <div class="page-title" style="font-size:22px;">Inbox — {role}</div>
        </div>
        """, unsafe_allow_html=True)
    with lcol:
        if st.button("Log out", key=f"logout_{role}"):
            st.session_state.ap_role_auth[role] = False
            st.rerun()

    ctx = role.replace(" ","_").lower()

    mine = [
        r for r in reversed(st.session_state.ap_requests)
        if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role
    ]
    handled = [
        r for r in reversed(st.session_state.ap_requests)
        if r["done"] and any(e.get("by") == role for e in r["history"])
    ]

    if not mine:
        st.markdown("""
        <div class="hd-card" style="text-align:center; padding:28px;">
            <div style="font-size:24px; margin-bottom:8px;">✅</div>
            <div style="color:rgba(52,211,153,0.8); font-size:14px; font-weight:500;">Nothing waiting for your approval right now.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='section-label'>{len(mine)} awaiting decision</div>", unsafe_allow_html=True)
        for req in mine:
            _request_card_role(req, show_actions=True, ctx=ctx)

    if handled:
        st.markdown("<hr>", unsafe_allow_html=True)
        with st.expander(f"Previously handled ({len(handled)})"):
            for req in handled:
                _request_card_role(req, show_actions=False, ctx=f"{ctx}_done")


# ── Request card (role tabs, no delete) ──────────────────────────────────────

def _request_card_role(req: dict, show_actions: bool, ctx: str = ""):
    stage = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    timer = _time_left(req["expires_at"]) if not req["done"] else ""
    rid   = req["id"]
    k     = f"{ctx}_{rid}"

    header = f"**{rid}**  ·  {req['title']}"
    if timer and timer != "Expired":
        header += f"  ·  ⏳ {timer}"

    with st.expander(header, expanded=(show_actions and not req["done"])):
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap;">
            {_status_badge(req['status'])}
            {_urgency_badge(req['urgency'])}
            <span style="font-size:12px; color:rgba(255,255,255,0.35);">{req.get('category','—')} › {req.get('subtype','—')}</span>
            <span style="margin-left:auto; font-size:11px; color:rgba(255,255,255,0.3);">Stage: {stage}</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px;">
            <div class="hd-card" style="padding:10px 14px;">
                <div style="font-size:10px; text-transform:uppercase; letter-spacing:0.8px; color:rgba(255,255,255,0.3); margin-bottom:4px;">Requester</div>
                <div style="font-size:13.5px; font-weight:500; color:rgba(255,255,255,0.85);">{req['requester']}</div>
            </div>
            <div class="hd-card" style="padding:10px 14px;">
                <div style="font-size:10px; text-transform:uppercase; letter-spacing:0.8px; color:rgba(255,255,255,0.3); margin-bottom:4px;">Submitted</div>
                <div style="font-size:13px; color:rgba(255,255,255,0.7);">{_fmt(req['created_at'])}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f'<div class="answer-box" style="margin-bottom:14px; font-size:13.5px;">{req["description"]}</div>', unsafe_allow_html=True)

        if req["chain"]:
            chain_parts = []
            for i, s in enumerate(req["chain"]):
                if req["status"] == "Approved" or i < req["stage_idx"]:
                    chain_parts.append(f'<span style="color:rgba(52,211,153,0.7); text-decoration:line-through;">{s} ✅</span>')
                elif i == req["stage_idx"] and not req["done"]:
                    chain_parts.append(f'<span style="color:#a78bfa; font-weight:600;">{s} ⏳</span>')
                elif req["done"] and i == req["stage_idx"]:
                    icon = "❌" if req["status"] == "Rejected" else "⏰"
                    chain_parts.append(f'<span style="color:#f87171; font-weight:600;">{s} {icon}</span>')
                else:
                    chain_parts.append(f'<span style="color:rgba(255,255,255,0.3);">{s}</span>')
            chain_html = ' <span style="color:rgba(255,255,255,0.2);">→</span> '.join(chain_parts)
            st.markdown(f'<div style="font-size:13px; margin-bottom:14px;">{chain_html}</div>', unsafe_allow_html=True)

        with st.expander("History", key=f"hist_{k}"):
            for entry in req["history"]:
                t    = _fmt(entry.get("time",""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"""
                <div style="font-size:12.5px; color:rgba(255,255,255,0.6); margin-bottom:6px; padding:6px 10px; background:rgba(255,255,255,0.025); border-radius:8px;">
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:rgba(255,255,255,0.3);">{t}</span>
                    &nbsp; <strong style="color:rgba(255,255,255,0.75);">{entry['by']}</strong>: {entry['action']}{note}
                </div>
                """, unsafe_allow_html=True)

        if show_actions and not req["done"]:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            note = st.text_input("Note (optional)", key=f"note_{k}", placeholder="Reason or comment…")
            ca, cr, _ = st.columns([1, 1, 4])
            with ca:
                if st.button("✅ Approve", key=f"ap_{k}", type="primary", use_container_width=True):
                    _approve(req, note)
                    st.rerun()
            with cr:
                if st.button("❌ Reject", key=f"rj_{k}", use_container_width=True):
                    _reject(req, note)
                    st.rerun()
