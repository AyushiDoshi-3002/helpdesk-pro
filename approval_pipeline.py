"""
approval_pipeline.py  –  role-based tabs + Supabase persistence
────────────────────────────────────────────────────────────────
Install dependency:  pip install supabase

Run this SQL once in your Supabase SQL editor to create the table:
──────────────────────────────────────────────────────────────────
create table if not exists ap_requests (
    id          text primary key,
    title       text,
    category    text,
    subtype     text,
    description text,
    urgency     text,
    requester   text,
    chain       jsonb,
    stage_idx   integer default 0,
    status      text,
    created_at  timestamptz,
    expires_at  timestamptz,
    history     jsonb,
    done        boolean default false
);
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
    "Team Lead":    "Lead123",
    "Tech Manager": "Manager123",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

TIMEOUT_HOURS = 2

# ── Document taxonomy ─────────────────────────────────────────────────────────
DOC_CATEGORIES = {
    "Security": {
        "label":    "🔒 Security",
        "subtypes": ["Legal", "Compliance", "Public API", "Financial"],
        "approver": "CEO",
        "auto":     False,
    },
    "Technical": {
        "label":    "⚙️ Technical",
        "subtypes": ["Architecture", "Database", "Tech Stack", "Infrastructure", "Code Standards"],
        "approver": "CTO",
        "auto":     False,
    },
    "Operations": {
        "label":    "🔧 Operations",
        "subtypes": ["Runbooks", "Deployment", "Monitoring", "Setup Guides"],
        "approver": "Tech Manager",
        "auto":     False,
    },
    "Team": {
        "label":    "👥 Team",
        "subtypes": ["Internal Processes", "Troubleshooting", "Setup Guides"],
        "approver": "Team Lead",
        "auto":     False,
    },
    "General": {
        "label":    "📄 General",
        "subtypes": ["FAQs", "Onboarding", "General Info"],
        "approver": "Admin",
        "auto":     True,
    },
}

_CHAINS = {
    "CEO":          ["Team Lead", "Tech Manager", "CTO", "CEO"],
    "CTO":          ["Team Lead", "Tech Manager", "CTO"],
    "Tech Manager": ["Team Lead", "Tech Manager"],
    "Team Lead":    ["Team Lead"],
    "Admin":        [],
}

def _build_chain(category: str) -> list:
    cfg = DOC_CATEGORIES.get(category, {})
    return list(_CHAINS.get(cfg.get("approver", "Team Lead"), ["Team Lead"]))


# ── Supabase client (cached) ──────────────────────────────────────────────────

@st.cache_resource
def _get_sb() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _dt_to_str(dt):
    if isinstance(dt, datetime):
        # Always store as UTC in DB for consistency
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

def _db_insert(req: dict):
    try:
        row = _serialize(req)
        res = _get_sb().table(TABLE).insert(row).execute()
        if hasattr(res, "data") and res.data:
            st.toast(f"✅ Saved to Supabase: {req['id']}", icon="🗄️")
        else:
            st.warning(f"⚠️ Insert returned no data. Response: {res}")
    except Exception as e:
        st.error(f"❌ DB insert error for {req.get('id')}: {type(e).__name__}: {e}")

def _db_update(req: dict):
    try:
        row = _serialize(req)
        res = _get_sb().table(TABLE).upsert(row).execute()
        if hasattr(res, "data") and res.data:
            st.toast(f"✅ Updated in Supabase: {req['id']}", icon="🗄️")
        else:
            st.warning(f"⚠️ Upsert returned no data. Response: {res}")
    except Exception as e:
        st.error(f"❌ DB update error for {req.get('id')}: {type(e).__name__}: {e}")

# ── ✅ NEW: Delete from Supabase ──────────────────────────────────────────────
def _db_delete(rid: str):
    """Delete a request row from Supabase by id."""
    try:
        _get_sb().table(TABLE).delete().eq("id", rid).execute()
        st.toast(f"🗑️ Deleted {rid} from Supabase", icon="🗄️")
    except Exception as e:
        st.error(f"❌ DB delete error for {rid}: {type(e).__name__}: {e}")

def _db_load_all() -> list:
    try:
        res = _get_sb().table(TABLE).select("*").order("created_at", desc=False).execute()
        rows = res.data or []
        st.caption(f"🗄️ Loaded {len(rows)} record(s) from Supabase.")
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
        # Convert to IST for display
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%d %b %Y, %I:%M %p IST")
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
        "ap_role_auth":         {},
        "ap_loaded":            False,
        "ap_confirm_delete":    {},   # ✅ NEW: tracks which request IDs have delete confirmation pending
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _load_requests():
    rows = _db_load_all()
    st.session_state.ap_requests = rows
    ids = [int(r["id"].split("-")[1]) for r in rows if r.get("id", "").startswith("REQ-")]
    st.session_state.ap_next_id = (max(ids) + 1) if ids else 1
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
        req["history"].append({"time": _now(), "by": "System",
                                "action": "All levels approved — COMPLETE ✅"})
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

# ── ✅ NEW: Delete action ─────────────────────────────────────────────────────
def _delete_request(rid: str):
    """Remove request from session state and Supabase."""
    st.session_state.ap_requests = [
        r for r in st.session_state.ap_requests if r["id"] != rid
    ]
    # Clear any pending confirm state
    st.session_state.ap_confirm_delete.pop(rid, None)
    _db_delete(rid)


# ── Main entry ────────────────────────────────────────────────────────────────

def page_approval_pipeline():
    _init()

    try:
        test = _get_sb().table(TABLE).select("id").limit(1).execute()
        st.success(f"🟢 Supabase connected — table `{TABLE}` is reachable.")
    except Exception as e:
        st.error(f"🔴 Supabase connection FAILED: {type(e).__name__}: {e}")
        st.stop()

    if not st.session_state.ap_loaded:
        _load_requests()

    for r in st.session_state.ap_requests:
        _check_expiry(r)

    hcol, rcol = st.columns([5, 1])
    with hcol:
        st.title("Document Approval Pipeline")
    with rcol:
        st.markdown("<br>", unsafe_allow_html=True)
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


# ── Submit + tracker (public) ─────────────────────────────────────────────────

def _view_submit():
    with st.form("ap_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            requester = st.text_input("Your Name / Employee ID",
                                      placeholder="e.g. Priya K · EMP-042")
            category  = st.selectbox(
                "Document Category",
                list(DOC_CATEGORIES.keys()),
                format_func=lambda c: DOC_CATEGORIES[c]["label"],
            )
        with col2:
            title   = st.text_input("Document Title",
                                    placeholder="e.g. Database Backup Procedure")
            urgency = st.selectbox("Urgency", ["Normal", "URGENT", "CRITICAL"])

        subtype = st.selectbox("Document Subtype", DOC_CATEGORIES[category]["subtypes"])

        description = st.text_area("What does this document need to cover?",
                                   placeholder="Describe the purpose and scope…", height=90)

        cfg       = DOC_CATEGORIES[category]
        chain     = _build_chain(category)
        route_str = (
            "Auto-approved instantly"
            if cfg["auto"]
            else "  →  ".join(chain) + f"  ·  {TIMEOUT_HOURS}h per level"
        )
        st.caption(f"Approval route: {route_str}")

        submitted = st.form_submit_button("Submit Request", type="primary",
                                          use_container_width=True)

    if submitted:
        errors = []
        if not requester.strip():   errors.append("Name / Employee ID required.")
        if not title.strip():       errors.append("Document title required.")
        if not description.strip(): errors.append("Description required.")
        for e in errors:
            st.error(e)
        if not errors:
            req = _create(title.strip(), category, subtype,
                          description.strip(), urgency, requester.strip())
            if req["done"]:
                st.success(f"**{req['id']}** auto-approved instantly. ✅")
            else:
                st.success(f"**{req['id']}** submitted — first stop: **{req['chain'][0]}**")

    all_reqs = list(reversed(st.session_state.ap_requests))
    if not all_reqs:
        st.info("No requests yet.")
        return

    st.divider()

    # ── Summary metrics ───────────────────────────────────────────────────────
    counts = {"Pending": 0, "Approved": 0, "Rejected": 0, "Expired": 0}
    for r in all_reqs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending",  counts["Pending"])
    c2.metric("Approved", counts["Approved"])
    c3.metric("Rejected", counts["Rejected"])
    c4.metric("Expired",  counts["Expired"])

    # ── ✅ NEW: Bulk delete controls ──────────────────────────────────────────
    st.divider()
    st.markdown("### 📋 All Requests")

    bulk_col1, bulk_col2, bulk_col3 = st.columns([2, 2, 4])
    with bulk_col1:
        if st.button("🗑️ Delete All Rejected", use_container_width=True):
            rejected_ids = [r["id"] for r in all_reqs if r["status"] == "Rejected"]
            for rid in rejected_ids:
                _delete_request(rid)
            if rejected_ids:
                st.success(f"Deleted {len(rejected_ids)} rejected request(s).")
                st.rerun()
            else:
                st.info("No rejected requests to delete.")
    with bulk_col2:
        if st.button("🗑️ Delete All Expired", use_container_width=True):
            expired_ids = [r["id"] for r in all_reqs if r["status"] == "Expired"]
            for rid in expired_ids:
                _delete_request(rid)
            if expired_ids:
                st.success(f"Deleted {len(expired_ids)} expired request(s).")
                st.rerun()
            else:
                st.info("No expired requests to delete.")

    st.divider()

    # ── Request cards with individual delete ──────────────────────────────────
    for req in all_reqs:
        _request_card_with_delete(req, ctx="sub")


# ── ✅ NEW: Request card with delete button (for Submit tab only) ─────────────
def _request_card_with_delete(req: dict, ctx: str = "sub"):
    """Same as _request_card but with a delete button added."""
    stage    = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    timer    = _time_left(req["expires_at"]) if not req["done"] else ""
    urg_icon = {"URGENT": "🟡", "CRITICAL": "🔴"}.get(req["urgency"], "")
    rid = req["id"]
    k   = f"{ctx}_{rid}"

    # Status colour indicator
    status_icon = {
        "Pending":  "🟡",
        "Approved": "🟢",
        "Rejected": "🔴",
        "Expired":  "⏰",
    }.get(req["status"], "⚪")

    label = f"{status_icon} {rid}  ·  {req['title']}  {urg_icon}"
    if timer:
        label += f"  ·  ⏳ {timer}"

    with st.expander(label, expanded=False):

        # ── Request details ───────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Requester**  \n{req['requester']}")
        c2.markdown(f"**Category**  \n{req.get('category','—')} › {req.get('subtype','—')}")
        c3.markdown(f"**Stage**  \n{stage}")
        c4.markdown(f"**Status**  \n{req['status']}")

        st.markdown(f"> {req['description']}")

        # Approval chain progress
        if req["chain"]:
            parts = []
            for i, s in enumerate(req["chain"]):
                if req["status"] == "Approved" or i < req["stage_idx"]:
                    parts.append(f"~~{s}~~ ✅")
                elif i == req["stage_idx"] and not req["done"]:
                    parts.append(f"**{s} ⏳**")
                elif req["done"] and i == req["stage_idx"]:
                    parts.append(f"**{s} {'❌' if req['status'] == 'Rejected' else '⏰'}**")
                else:
                    parts.append(s)
            st.markdown("  →  ".join(parts))
        else:
            st.caption("Auto-approved — no chain required.")

        # History
        with st.expander("History", key=f"hist_{k}"):
            for entry in req["history"]:
                t    = _fmt(entry.get("time", ""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"`{t}`  **{entry['by']}**: {entry['action']}{note}")

        st.divider()

        # ── ✅ NEW: Delete section ─────────────────────────────────────────────
        confirm_key = f"confirm_del_{rid}"
        is_pending_confirm = st.session_state.ap_confirm_delete.get(rid, False)

        if not is_pending_confirm:
            # First click — show delete button
            del_col, _ = st.columns([1, 5])
            with del_col:
                if st.button("🗑️ Delete", key=f"del_btn_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = True
                    st.rerun()
        else:
            # Second click — show confirmation row
            st.warning(f"⚠️ Are you sure you want to delete **{rid} — {req['title']}**? This cannot be undone.")
            conf_col1, conf_col2, _ = st.columns([1, 1, 4])
            with conf_col1:
                if st.button("✅ Yes, Delete", key=f"confirm_yes_{k}", use_container_width=True):
                    _delete_request(rid)
                    st.success(f"🗑️ {rid} deleted.")
                    st.rerun()
            with conf_col2:
                if st.button("✖ Cancel", key=f"confirm_no_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = False
                    st.rerun()


# ── Role tab ──────────────────────────────────────────────────────────────────

def _view_role(role: str):
    authed = st.session_state.ap_role_auth.get(role, False)

    if not authed:
        st.subheader(f"🔐 {role} Login")
        col, _ = st.columns([1.5, 3])
        with col:
            pwd = st.text_input("Password", type="password", key=f"pwd_{role}")
            if st.button("Log in", type="primary", use_container_width=True,
                         key=f"login_{role}"):
                if pwd == ROLE_PASSWORDS.get(role, ""):
                    st.session_state.ap_role_auth[role] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    hcol, lcol = st.columns([6, 1])
    with hcol:
        st.subheader(f"Inbox — {role}")
    with lcol:
        if st.button("Log out", key=f"logout_{role}"):
            st.session_state.ap_role_auth[role] = False
            st.rerun()

    ctx = role.replace(" ", "_").lower()

    mine = [
        r for r in reversed(st.session_state.ap_requests)
        if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role
    ]
    handled = [
        r for r in reversed(st.session_state.ap_requests)
        if r["done"] and any(e.get("by") == role for e in r["history"])
    ]

    if not mine:
        st.success("Nothing waiting for your approval right now.")
    else:
        st.markdown(f"**{len(mine)} request(s) awaiting your decision**")
        for req in mine:
            _request_card(req, show_actions=True, ctx=ctx)

    if handled:
        st.divider()
        with st.expander(f"Previously handled ({len(handled)})"):
            for req in handled:
                _request_card(req, show_actions=False, ctx=f"{ctx}_done")


# ── Original request card (used in role tabs — no delete) ─────────────────────

def _request_card(req: dict, show_actions: bool, ctx: str = ""):
    stage    = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    timer    = _time_left(req["expires_at"]) if not req["done"] else ""
    urg_icon = {"URGENT": "🟡", "CRITICAL": "🔴"}.get(req["urgency"], "")
    rid = req["id"]
    k   = f"{ctx}_{rid}"

    label = f"{rid}  ·  {req['title']}  {urg_icon}"
    if timer:
        label += f"  ·  ⏳ {timer}"

    with st.expander(label, expanded=(show_actions and not req["done"])):

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Requester**  \n{req['requester']}")
        c2.markdown(f"**Category**  \n{req.get('category','—')} › {req.get('subtype','—')}")
        c3.markdown(f"**Stage**  \n{stage}")
        c4.markdown(f"**Status**  \n{req['status']}")

        st.markdown(f"> {req['description']}")

        if req["chain"]:
            parts = []
            for i, s in enumerate(req["chain"]):
                if req["status"] == "Approved" or i < req["stage_idx"]:
                    parts.append(f"~~{s}~~ ✅")
                elif i == req["stage_idx"] and not req["done"]:
                    parts.append(f"**{s} ⏳**")
                elif req["done"] and i == req["stage_idx"]:
                    parts.append(f"**{s} {'❌' if req['status'] == 'Rejected' else '⏰'}**")
                else:
                    parts.append(s)
            st.markdown("  →  ".join(parts))
        else:
            st.caption("Auto-approved — no chain required.")

        with st.expander("History", key=f"hist_{k}"):
            for entry in req["history"]:
                t    = _fmt(entry.get("time", ""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"`{t}`  **{entry['by']}**: {entry['action']}{note}")

        if show_actions and not req["done"]:
            note = st.text_input("Note (optional)", key=f"note_{k}",
                                 placeholder="Reason or comment…")
            ca, cr, _ = st.columns([1, 1, 4])
            with ca:
                if st.button("✅ Approve", key=f"ap_{k}", type="primary",
                             use_container_width=True):
                    _approve(req, note)
                    st.rerun()
            with cr:
                if st.button("❌ Reject", key=f"rj_{k}", use_container_width=True):
                    _reject(req, note)
                    st.rerun()
