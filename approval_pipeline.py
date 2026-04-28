"""
approval_pipeline.py
────────────────────
Drop this file in the same folder as app.py.
Called by app.py as: page_approval_pipeline()

Flow:
  Submit → Team Lead → Tech Manager → CTO → CEO → Approved
  Single admin password. One clean page. No tab switching.
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

# These doc types go through all 4 levels; others stop at Tech Manager
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
        return "⏰ Expired"
    h, rem = divmod(secs, 3600)
    m, _   = divmod(rem, 60)
    return f"⏳ {h}h {m}m left" if h else f"⏳ {m}m left"


def _status_icon(status):
    return {"Approved": "✅", "Rejected": "❌", "Expired": "⏰"}.get(status, "🔄")


# ── Session-state init ────────────────────────────────────────────────────────

def _init():
    if "ap_requests" not in st.session_state:
        st.session_state.ap_requests = []
    if "ap_next_id" not in st.session_state:
        st.session_state.ap_next_id = 1
    if "ap_authed" not in st.session_state:
        st.session_state.ap_authed = False
    if "ap_view" not in st.session_state:
        st.session_state.ap_view = "submit"


# ── Core actions ──────────────────────────────────────────────────────────────

def _create(title, doc_type, description, urgency, requester):
    rid   = f"REQ-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now   = _now()
    chain = list(APPROVAL_CHAIN) if doc_type in NEEDS_FULL_CHAIN else ["Team Lead", "Tech Manager"]

    req = {
        "id":          rid,
        "title":       title,
        "doc_type":    doc_type,
        "description": description,
        "urgency":     urgency,
        "requester":   requester,
        "chain":       chain,
        "stage_idx":   0,
        "status":      "Pending",
        "created_at":  now,
        "expires_at":  now + timedelta(hours=TIMEOUT_HOURS),
        "history":     [{"time": now, "by": "System",
                         "action": f"Created and routed to {chain[0]}"}],
        "done":        False,
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
        req["history"].append({"time": _now(), "by": "System",
                                "action": "All levels approved — request COMPLETE ✅"})
    else:
        req["stage_idx"]  = next_idx
        req["expires_at"] = _now() + timedelta(hours=TIMEOUT_HOURS)
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Auto-forwarded to {req['chain'][next_idx]}"})


def _reject(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["status"] = "Rejected"
    req["done"]   = True
    req["history"].append({"time": _now(), "by": stage, "action": "Rejected ❌", "note": note})


def _check_expiry(req):
    if req["done"]:
        return
    if _now() > req["expires_at"]:
        stage         = req["chain"][req["stage_idx"]]
        req["status"] = "Expired"
        req["done"]   = True
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Auto-expired — no response from {stage} within {TIMEOUT_HOURS}h"})


# ── Main entry point ──────────────────────────────────────────────────────────

def page_approval_pipeline():
    _init()

    for r in st.session_state.ap_requests:
        _check_expiry(r)

    st.markdown("## 📋 Document Approval Pipeline")
    st.caption("Submit a document request and it moves through up to 4 approval levels automatically.")
    st.divider()

    # ── Two-button switcher ───────────────────────────────────────────────────
    pending_count = sum(1 for r in st.session_state.ap_requests if not r["done"])

    col_a, col_b, _ = st.columns([2, 2, 5])
    with col_a:
        if st.button(
            "📝 Submit Request",
            type="primary" if st.session_state.ap_view == "submit" else "secondary",
            use_container_width=True,
        ):
            st.session_state.ap_view = "submit"
            st.rerun()
    with col_b:
        if st.button(
            f"✅ Review  ({pending_count} pending)",
            type="primary" if st.session_state.ap_view == "review" else "secondary",
            use_container_width=True,
        ):
            st.session_state.ap_view = "review"
            st.rerun()

    st.divider()

    if st.session_state.ap_view == "submit":
        _view_submit()
    else:
        _view_review()


# ── Submit view ───────────────────────────────────────────────────────────────

def _view_submit():

    # Compact "how it works" box
    st.info(
        "**How it works:** Submit below → System auto-routes to **Team Lead** → "
        "**Tech Manager** → **CTO** → **CEO** (for technical/finance/security docs). "
        "Each level has **2 hours** to approve or reject. No response = auto-expire.",
        icon="ℹ️",
    )

    st.subheader("New Document Request")

    with st.form("ap_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            requester   = st.text_input("👤 Your Name / Employee ID *", placeholder="e.g. Priya K · EMP-042")
            doc_type    = st.selectbox("📂 Document Type *", DOC_TYPES)
        with c2:
            title       = st.text_input("📄 Document Title *", placeholder="e.g. Database Backup Procedure")
            urgency     = st.selectbox("🚨 Urgency", ["Normal", "URGENT", "CRITICAL"])

        description = st.text_area(
            "📋 What does this document need to cover? *",
            placeholder="Describe the purpose and scope of the document…",
            height=100,
        )

        chain_label = (
            "Team Lead → Tech Manager → CTO → CEO"
            if doc_type in NEEDS_FULL_CHAIN
            else "Team Lead → Tech Manager"
        )
        st.caption(f"⚡ Routing: **{chain_label}**")

        submitted = st.form_submit_button("🚀 Submit Request", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not requester.strip():   errors.append("Name / Employee ID required.")
        if not title.strip():       errors.append("Document title required.")
        if not description.strip(): errors.append("Description required.")
        for e in errors:
            st.error(e)
        if not errors:
            req = _create(title.strip(), doc_type, description.strip(), urgency, requester.strip())
            st.success(f"✅ **{req['id']}** submitted! First stop: **{req['chain'][0]}**")
            st.caption(f"⏰ Approval window: {_fmt(req['created_at'])} → {_fmt(req['expires_at'])}")

    # ── All requests list ─────────────────────────────────────────────────────
    all_reqs = list(reversed(st.session_state.ap_requests))
    if not all_reqs:
        return

    st.divider()
    st.subheader("📊 All Requests")

    # Stats row
    counts = {"Pending": 0, "Approved": 0, "Rejected": 0, "Expired": 0}
    for r in all_reqs:
        k = r["status"] if r["status"] in counts else "Pending"
        counts[k] += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔄 Pending",  counts["Pending"])
    c2.metric("✅ Approved", counts["Approved"])
    c3.metric("❌ Rejected", counts["Rejected"])
    c4.metric("⏰ Expired",  counts["Expired"])

    st.markdown("")
    for req in all_reqs:
        _request_card(req, show_actions=False)


# ── Review view ───────────────────────────────────────────────────────────────

def _view_review():
    # Auth gate
    if not st.session_state.ap_authed:
        st.subheader("🔐 Admin Login")
        st.caption("Same password as your Admin Panel.")
        col, _ = st.columns([1.5, 2.5])
        with col:
            pwd = st.text_input("Password", type="password", key="ap_pwd")
            if st.button("Login →", type="primary", use_container_width=True):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.ap_authed = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    # Header + logout
    hcol, lcol = st.columns([5, 1])
    with hcol:
        st.subheader("✅ Review & Approve")
    with lcol:
        if st.button("Logout", key="ap_logout"):
            st.session_state.ap_authed = False
            st.rerun()

    pending = [r for r in reversed(st.session_state.ap_requests) if not r["done"]]
    closed  = [r for r in reversed(st.session_state.ap_requests) if r["done"]]

    if not pending:
        st.success("🎉 No pending requests right now.")
    else:
        st.markdown(f"**{len(pending)} request(s) awaiting approval**")
        for req in pending:
            _request_card(req, show_actions=True)

    if closed:
        st.divider()
        with st.expander(f"📚 Closed requests ({len(closed)})", expanded=False):
            for req in closed:
                _request_card(req, show_actions=False)


# ── Request card (used in both views) ────────────────────────────────────────

def _request_card(req: dict, show_actions: bool):
    icon    = _status_icon(req["status"])
    urgency = {"URGENT": "🟡 URGENT", "CRITICAL": "🔴 CRITICAL"}.get(req["urgency"], "🟢 Normal")
    stage   = req["chain"][req["stage_idx"]] if not req["done"] else req["status"]
    timer   = _time_left(req["expires_at"]) if not req["done"] else ""

    header  = f"{icon} **{req['id']}** · {req['title']}  |  {urgency}  |  {req['doc_type']}"
    if timer:
        header += f"  |  {timer}"

    with st.expander(header, expanded=(show_actions and not req["done"])):

        # Details
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Requester:** {req['requester']}")
        c2.markdown(f"**Created:** {_fmt(req['created_at'])}")
        c3.markdown(f"**Stage:** {stage}")

        # Description block
        st.markdown(
            f"<div style='background:#f5f3ff;padding:12px 16px;border-radius:10px;"
            f"border-left:4px solid #7c3aed;color:#1e1b4b;font-size:14px;margin:10px 0'>"
            f"{req['description']}</div>",
            unsafe_allow_html=True,
        )

        # Pipeline progress
        _pipeline_visual(req)

        # History
        with st.expander("📜 Approval history", expanded=False):
            for entry in req["history"]:
                t    = _fmt(entry["time"]) if isinstance(entry["time"], datetime) else str(entry["time"])
                note = f" — *{entry['note']}*" if entry.get("note") else ""
                st.markdown(
                    f"<small style='color:#9ca3af'>{t}</small>&nbsp;&nbsp;"
                    f"**{entry['by']}** · {entry['action']}{note}",
                    unsafe_allow_html=True,
                )

        # Approve / Reject (only in review view for pending requests)
        if show_actions and not req["done"]:
            st.markdown("---")
            st.markdown(f"**Reviewing as: {stage}**")
            note = st.text_area(
                "Note (optional)",
                key=f"note_{req['id']}",
                placeholder="Add a reason or comment for the audit trail…",
                height=60,
            )
            ca, cr, _ = st.columns([1, 1, 4])
            with ca:
                if st.button("✅ Approve", key=f"ap_{req['id']}", type="primary", use_container_width=True):
                    _approve(req, note)
                    st.rerun()
            with cr:
                if st.button("❌ Reject", key=f"rj_{req['id']}", use_container_width=True):
                    _reject(req, note)
                    st.rerun()

        # Delete (admin only)
        if st.session_state.ap_authed:
            st.markdown("")
            if st.button("🗑️ Delete this request", key=f"del_{req['id']}"):
                st.session_state.ap_requests = [
                    r for r in st.session_state.ap_requests if r["id"] != req["id"]
                ]
                st.rerun()


# ── Pipeline progress visual ──────────────────────────────────────────────────

def _pipeline_visual(req: dict):
    chain     = req["chain"]
    stage_idx = req["stage_idx"]
    done      = req["done"]
    status    = req["status"]

    cols = st.columns(len(chain))
    for i, stage in enumerate(chain):
        with cols[i]:
            if status == "Approved":
                bg, icon, label = "#d1fae5", "✅", "Done"
            elif done and i == stage_idx:
                bg, icon, label = "#fee2e2", ("❌" if status == "Rejected" else "⏰"), status
            elif i < stage_idx:
                bg, icon, label = "#d1fae5", "✅", "Done"
            elif i == stage_idx and not done:
                bg, icon, label = "#fef3c7", "⏳", "Current"
            else:
                bg, icon, label = "#f1f5f9", "⬜", "Waiting"

            st.markdown(
                f"<div style='text-align:center;background:{bg};border-radius:10px;"
                f"padding:10px 4px;font-size:12px'>"
                f"<div style='font-size:22px'>{icon}</div>"
                f"<strong style='font-size:11px'>{stage}</strong><br>"
                f"<small style='color:#6b7280'>{label}</small>"
                f"</div>",
                unsafe_allow_html=True,
            )
