"""
approval_pipeline.py  –  simplified UI
"""

import streamlit as st
from datetime import datetime, timedelta, timezone

# ── Config ────────────────────────────────────────────────────────────────────
ADMIN_PASSWORD = "admin123"
TIMEOUT_HOURS  = 2

APPROVAL_CHAIN = ["Team Lead", "Tech Manager", "CTO", "CEO"]

DOC_TYPES = [
    "Technical - Database",
    "Technical - Infrastructure",
    "Technical - API / Code",
    "Policy / HR",
    "Finance / Legal",
    "Security / Compliance",
    "General / Internal",
]

NEEDS_FULL_CHAIN = {
    "Technical - Database", "Technical - Infrastructure",
    "Technical - API / Code", "Finance / Legal", "Security / Compliance",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)

def _fmt(dt):
    try:
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return str(dt)

def _time_left(expires_at):
    diff = expires_at - _now()
    secs = int(diff.total_seconds())
    if secs <= 0:
        return "Expired"
    h, rem = divmod(secs, 3600)
    m, _   = divmod(rem, 60)
    return f"{h}h {m}m left" if h else f"{m}m left"

def _status_badge(status):
    colors = {
        "Pending":  ("#fef3c7", "#92400e"),
        "Approved": ("#d1fae5", "#065f46"),
        "Rejected": ("#fee2e2", "#991b1b"),
        "Expired":  ("#f1f5f9", "#475569"),
    }
    bg, fg = colors.get(status, ("#f1f5f9", "#475569"))
    return f"<span style='background:{bg};color:{fg};padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600'>{status}</span>"


# ── Session-state init ────────────────────────────────────────────────────────

def _init():
    defaults = {
        "ap_requests": [],
        "ap_next_id":  1,
        "ap_authed":   False,
        "ap_view":     "submit",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Core actions ──────────────────────────────────────────────────────────────

def _create(title, doc_type, description, urgency, requester):
    rid   = f"REQ-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now   = _now()
    chain = list(APPROVAL_CHAIN) if doc_type in NEEDS_FULL_CHAIN else ["Team Lead", "Tech Manager"]

    req = {
        "id": rid, "title": title, "doc_type": doc_type,
        "description": description, "urgency": urgency, "requester": requester,
        "chain": chain, "stage_idx": 0, "status": "Pending",
        "created_at": now, "expires_at": now + timedelta(hours=TIMEOUT_HOURS),
        "history": [{"time": now, "by": "System", "action": f"Submitted → routed to {chain[0]}"}],
        "done": False,
    }
    st.session_state.ap_requests.append(req)
    return req

def _approve(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["history"].append({"time": _now(), "by": stage, "action": "Approved", "note": note})
    next_idx = req["stage_idx"] + 1
    if next_idx >= len(req["chain"]):
        req["status"] = "Approved"
        req["done"]   = True
    else:
        req["stage_idx"]  = next_idx
        req["expires_at"] = _now() + timedelta(hours=TIMEOUT_HOURS)
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Forwarded to {req['chain'][next_idx]}"})

def _reject(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["status"] = "Rejected"
    req["done"]   = True
    req["history"].append({"time": _now(), "by": stage, "action": "Rejected", "note": note})

def _check_expiry(req):
    if not req["done"] and _now() > req["expires_at"]:
        stage         = req["chain"][req["stage_idx"]]
        req["status"] = "Expired"
        req["done"]   = True
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Expired — no response from {stage}"})


# ── Main entry ────────────────────────────────────────────────────────────────

def page_approval_pipeline():
    _init()
    for r in st.session_state.ap_requests:
        _check_expiry(r)

    st.title("Document Approval Pipeline")
    st.caption("Submit requests · track status · approve or reject — all in one place.")

    pending_count = sum(1 for r in st.session_state.ap_requests if not r["done"])

    tab_submit, tab_review = st.tabs([
        "📝 Submit a Request",
        f"✅ Review ({pending_count} pending)",
    ])

    with tab_submit:
        _view_submit()

    with tab_review:
        _view_review()


# ── Submit view ───────────────────────────────────────────────────────────────

def _view_submit():
    with st.form("ap_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            requester = st.text_input("Your Name / Employee ID", placeholder="e.g. Priya K · EMP-042")
            doc_type  = st.selectbox("Document Type", DOC_TYPES)
        with col2:
            title   = st.text_input("Document Title", placeholder="e.g. Database Backup Procedure")
            urgency = st.selectbox("Urgency", ["Normal", "URGENT", "CRITICAL"])

        description = st.text_area("What does this document need to cover?",
                                   placeholder="Describe the purpose and scope…", height=90)

        route = ("Team Lead → Tech Manager → CTO → CEO"
                 if doc_type in NEEDS_FULL_CHAIN else "Team Lead → Tech Manager")
        st.caption(f"Approval route: {route}  ·  {TIMEOUT_HOURS}h per level")

        submitted = st.form_submit_button("Submit Request", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not requester.strip():   errors.append("Name / Employee ID is required.")
        if not title.strip():       errors.append("Document title is required.")
        if not description.strip(): errors.append("Description is required.")
        for e in errors:
            st.error(e)
        if not errors:
            req = _create(title.strip(), doc_type, description.strip(), urgency, requester.strip())
            st.success(f"**{req['id']}** submitted — first stop: **{req['chain'][0]}**")

    # ── All requests ──────────────────────────────────────────────────────────
    all_reqs = list(reversed(st.session_state.ap_requests))
    if not all_reqs:
        st.info("No requests yet.")
        return

    st.divider()

    # Stats
    counts = {"Pending": 0, "Approved": 0, "Rejected": 0, "Expired": 0}
    for r in all_reqs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending",  counts["Pending"])
    c2.metric("Approved", counts["Approved"])
    c3.metric("Rejected", counts["Rejected"])
    c4.metric("Expired",  counts["Expired"])

    st.divider()
    for req in all_reqs:
        _request_row(req, show_actions=False)


# ── Review view ───────────────────────────────────────────────────────────────

def _view_review():
    if not st.session_state.ap_authed:
        st.subheader("Admin Login")
        col, _ = st.columns([1.5, 3])
        with col:
            pwd = st.text_input("Password", type="password", key="ap_pwd")
            if st.button("Log in", type="primary", use_container_width=True):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.ap_authed = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    col_h, col_l = st.columns([6, 1])
    with col_l:
        if st.button("Log out", key="ap_logout"):
            st.session_state.ap_authed = False
            st.rerun()

    pending = [r for r in reversed(st.session_state.ap_requests) if not r["done"]]
    closed  = [r for r in reversed(st.session_state.ap_requests) if r["done"]]

    if not pending:
        st.success("No pending requests.")
    else:
        st.subheader(f"{len(pending)} pending")
        for req in pending:
            _request_row(req, show_actions=True)

    if closed:
        st.divider()
        with st.expander(f"Closed ({len(closed)})"):
            for req in closed:
                _request_row(req, show_actions=False)


# ── Request row ───────────────────────────────────────────────────────────────

def _request_row(req: dict, show_actions: bool):
    stage  = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    timer  = _time_left(req["expires_at"]) if not req["done"] else ""
    urg_icon = {"URGENT": "🟡", "CRITICAL": "🔴"}.get(req["urgency"], "")

    label = f"{req['id']}  ·  {req['title']}  {urg_icon}"
    if timer:
        label += f"  ·  ⏳ {timer}"

    with st.expander(label, expanded=(show_actions and not req["done"])):

        # One-line meta
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"**Requester**  \n{req['requester']}")
        col2.markdown(f"**Type**  \n{req['doc_type']}")
        col3.markdown(f"**Stage**  \n{stage if not req['done'] else '—'}")
        col4.markdown(f"**Status**  \n{req['status']}")

        # Description
        st.markdown(f"> {req['description']}")

        # Pipeline steps — simple text row
        step_parts = []
        for i, s in enumerate(req["chain"]):
            if req["status"] == "Approved" or i < req["stage_idx"]:
                step_parts.append(f"~~{s}~~ ✅")
            elif i == req["stage_idx"] and not req["done"]:
                step_parts.append(f"**{s} ⏳**")
            elif req["done"] and i == req["stage_idx"]:
                icon = "❌" if req["status"] == "Rejected" else "⏰"
                step_parts.append(f"**{s} {icon}**")
            else:
                step_parts.append(s)
        st.markdown("  →  ".join(step_parts))

        # History (compact)
        with st.expander("History"):
            for entry in req["history"]:
                t    = _fmt(entry["time"]) if isinstance(entry["time"], datetime) else str(entry["time"])
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"`{t}`  **{entry['by']}**: {entry['action']}{note}")

        # Approve / Reject
        if show_actions and not req["done"]:
            note = st.text_input("Note (optional)", key=f"note_{req['id']}",
                                 placeholder="Reason or comment…")
            ca, cr, _ = st.columns([1, 1, 4])
            with ca:
                if st.button("Approve", key=f"ap_{req['id']}", type="primary", use_container_width=True):
                    _approve(req, note)
                    st.rerun()
            with cr:
                if st.button("Reject", key=f"rj_{req['id']}", use_container_width=True):
                    _reject(req, note)
                    st.rerun()

        # Delete (admin only)
        if st.session_state.ap_authed:
            if st.button("Delete", key=f"del_{req['id']}"):
                st.session_state.ap_requests = [
                    r for r in st.session_state.ap_requests if r["id"] != req["id"]
                ]
                st.rerun()
