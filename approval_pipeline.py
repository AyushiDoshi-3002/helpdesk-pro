"""
approval_pipeline.py
────────────────────
Drop this file in the same folder as app.py.
Your existing app.py already has:

    from approval_pipeline import page_approval_pipeline

and calls  page_approval_pipeline()  when the user picks
"📋 Approval Pipeline" in the sidebar. That's all it needs.

Flow implemented (fully in session_state — no extra DB table needed):
  1. Admin submits document request form
  2. System auto-creates request with 2-hour expiry timer
  3. Auto-routes to Team Lead
  4. Team Lead: Approve / Reject / Forward
  5. If no response in 2h → auto-expire
  6. Tech Manager: Approve / Reject / Escalate
  7. Auto-forward to CTO (for technical docs)
  8. CTO: Approve / Reject / Forward to CEO
  9. System completes → KB-ready
"""

import streamlit as st
from datetime import datetime, timedelta, timezone

# ── Constants ─────────────────────────────────────────────────────────────────
TIMEOUT_HOURS = 2          # hours before a stage auto-expires
ADMIN_PASSWORD = "admin123"  # shared with your existing app

DOC_TYPES = {
    "Technical - Database":      {"needs_cto": True,  "label": "🗄️ Database"},
    "Technical - Infrastructure": {"needs_cto": True,  "label": "🏗️ Infrastructure"},
    "Technical - API / Code":     {"needs_cto": True,  "label": "💻 API / Code"},
    "Policy / HR":               {"needs_cto": False, "label": "📜 Policy / HR"},
    "Finance / Legal":           {"needs_cto": True,  "label": "💼 Finance / Legal"},
    "Security / Compliance":     {"needs_cto": True,  "label": "🔒 Security"},
    "General / Internal":        {"needs_cto": False, "label": "📄 General"},
}

URGENCY_LEVELS = ["Normal", "URGENT", "CRITICAL"]

# Stage order
STAGES = ["Team Lead", "Tech Manager", "CTO", "CEO", "Completed"]

# ── Session-state DB ──────────────────────────────────────────────────────────

def _init():
    if "ap_requests" not in st.session_state:
        st.session_state.ap_requests = []
    if "ap_next_id" not in st.session_state:
        st.session_state.ap_next_id = 1
    if "ap_role" not in st.session_state:
        st.session_state.ap_role = None          # None | "Team Lead" | "Tech Manager" | "CTO" | "CEO"
    if "ap_admin_authed" not in st.session_state:
        st.session_state.ap_admin_authed = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    try:
        return dt.strftime("%d %b %Y, %I:%M %p UTC")
    except Exception:
        return str(dt)


def _time_left(expires_at: datetime) -> str:
    delta = expires_at - _now()
    if delta.total_seconds() <= 0:
        return "⏰ EXPIRED"
    m, s = divmod(int(delta.total_seconds()), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"⏳ {h}h {m}m left"
    return f"⏳ {m}m {s}s left"


def _create_request(title, description, urgency, role, doc_type, requester_id) -> dict:
    rid = f"REQ-2026-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now = _now()
    req = {
        "id":           rid,
        "title":        title,
        "description":  description,
        "urgency":      urgency,
        "requester_role": role,
        "requester_id": requester_id,
        "doc_type":     doc_type,
        "needs_cto":    DOC_TYPES.get(doc_type, {}).get("needs_cto", False),
        "status":       "Pending Team Lead",
        "current_stage": "Team Lead",
        "created_at":   now,
        "expires_at":   now + timedelta(hours=TIMEOUT_HOURS),
        "audit": [
            {
                "time":   now,
                "actor":  "System",
                "action": "Request created & routed to Team Lead",
                "note":   f"Auto-routed based on doc type: {doc_type}",
            }
        ],
        "approved_by":  [],   # list of stages approved
        "rejected_by":  None,
        "forward_to":   None,
        "completed":    False,
    }
    st.session_state.ap_requests.append(req)
    return req


def _add_audit(req: dict, actor: str, action: str, note: str = ""):
    req["audit"].append({
        "time":   _now(),
        "actor":  actor,
        "action": action,
        "note":   note,
    })


def _check_expiry(req: dict):
    """Auto-expire if current stage timed out."""
    if req["completed"] or req["status"] in ("Approved", "Rejected", "Expired"):
        return
    if _now() > req["expires_at"]:
        req["status"]    = "Expired"
        req["completed"] = True
        _add_audit(req, "System", "Auto-expired due to timeout",
                   f"No response from {req['current_stage']} within {TIMEOUT_HOURS}h.")


def _advance_stage(req: dict, current_actor: str, note: str):
    """Move request to the next stage in the chain."""
    req["approved_by"].append(current_actor)
    _add_audit(req, current_actor, "Approved — forwarding to next stage", note)

    needs_cto = req.get("needs_cto", False)
    cur = req["current_stage"]

    if cur == "Team Lead":
        req["current_stage"] = "Tech Manager"
        req["status"]        = "Pending Tech Manager"
    elif cur == "Tech Manager":
        if needs_cto:
            req["current_stage"] = "CTO"
            req["status"]        = "Pending CTO"
        else:
            _complete(req, current_actor, note)
            return
    elif cur in ("CTO", "CEO"):
        _complete(req, current_actor, note)
        return

    req["expires_at"] = _now() + timedelta(hours=TIMEOUT_HOURS)


def _reject(req: dict, actor: str, note: str):
    req["rejected_by"] = actor
    req["status"]      = "Rejected"
    req["completed"]   = True
    _add_audit(req, actor, "Rejected", note)


def _escalate_to_ceo(req: dict, actor: str, note: str):
    req["current_stage"] = "CEO"
    req["status"]        = "Pending CEO"
    req["expires_at"]    = _now() + timedelta(hours=TIMEOUT_HOURS)
    _add_audit(req, actor, "Escalated to CEO", note)


def _forward(req: dict, actor: str, forward_to: str, note: str):
    req["forward_to"] = forward_to
    _add_audit(req, actor, f"Forwarded to {forward_to}", note)


def _complete(req: dict, actor: str, note: str):
    req["status"]    = "Approved"
    req["completed"] = True
    _add_audit(req, actor, "✅ Final approval — document request APPROVED", note)


# ── Main entry point called by app.py ─────────────────────────────────────────

def page_approval_pipeline():
    _init()

    # Auto-expire stale requests on every render
    for r in st.session_state.ap_requests:
        _check_expiry(r)

    st.markdown("# 📋 Document Approval Pipeline")
    st.markdown(
        "<p style='color:#6b7280'>Request documents through a structured multi-level approval chain "
        "with automatic routing and 2-hour stage timers.</p>",
        unsafe_allow_html=True,
    )

    # Role selector + admin login in a top bar
    _role_bar()

    st.markdown("---")

    # Three columns of tabs
    tab_submit, tab_review, tab_all, tab_audit = st.tabs([
        "📝 Submit Request",
        "✅ Review / Approve",
        "📊 All Requests",
        "📜 Audit Trail",
    ])

    with tab_submit:
        _tab_submit()

    with tab_review:
        _tab_review()

    with tab_all:
        _tab_all()

    with tab_audit:
        _tab_audit()


# ── Role bar ──────────────────────────────────────────────────────────────────

def _role_bar():
    col1, col2, col3 = st.columns([3, 2, 2])

    with col1:
        role_options = ["— I am viewing only —", "Team Lead", "Tech Manager", "CTO", "CEO"]
        current_idx  = role_options.index(st.session_state.ap_role) if st.session_state.ap_role in role_options else 0
        chosen = st.selectbox(
            "👤 Your Role (for reviewing requests)",
            role_options,
            index=current_idx,
            label_visibility="visible",
        )
        st.session_state.ap_role = None if chosen == role_options[0] else chosen

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        stats = _stats()
        st.markdown(
            f"🟡 **{stats['pending']}** pending &nbsp;|&nbsp; "
            f"✅ **{stats['approved']}** approved &nbsp;|&nbsp; "
            f"❌ **{stats['rejected']}** rejected",
            unsafe_allow_html=True,
        )

    with col3:
        if not st.session_state.ap_admin_authed:
            with st.expander("🔐 Admin Login"):
                pwd = st.text_input("Password", type="password", key="ap_admin_pwd")
                if st.button("Login", key="ap_admin_login"):
                    if pwd == ADMIN_PASSWORD:
                        st.session_state.ap_admin_authed = True
                        st.rerun()
                    else:
                        st.error("Wrong password.")
        else:
            st.markdown("<br>", unsafe_allow_html=True)
            st.success("🔓 Admin logged in")
            if st.button("Logout", key="ap_logout"):
                st.session_state.ap_admin_authed = False
                st.rerun()


def _stats() -> dict:
    reqs = st.session_state.ap_requests
    return {
        "total":    len(reqs),
        "pending":  sum(1 for r in reqs if not r["completed"]),
        "approved": sum(1 for r in reqs if r["status"] == "Approved"),
        "rejected": sum(1 for r in reqs if r["status"] == "Rejected"),
        "expired":  sum(1 for r in reqs if r["status"] == "Expired"),
    }


# ── Tab: Submit ───────────────────────────────────────────────────────────────

def _tab_submit():
    st.subheader("📝 New Document Request")
    st.markdown(
        "Fill in the form below. The system will automatically route your request "
        "through the approval chain based on document type."
    )

    # Flow diagram
    with st.expander("ℹ️ How the approval flow works", expanded=False):
        st.markdown("""
| Step | Who | What happens |
|------|-----|--------------|
| 1 | **You** | Fill & submit this form |
| 2 | 🤖 System | Creates request + starts 2-hour timer |
| 3 | 🤖 System | Auto-routes to **Team Lead** |
| 4 | 👤 Team Lead | Approve / Reject / Forward |
| 5 | 🤖 System | If no reply in 2h → **auto-expire** |
| 6 | 👤 Tech Manager | Approve / Reject / Escalate |
| 7 | 🤖 System | Auto-forward to **CTO** (for technical docs) |
| 8 | 👤 CTO | Approve / Reject / Forward to CEO |
| 9 | 🤖 System | Mark **APPROVED** → document can be created |
        """)

    st.markdown("---")

    with st.form("ap_submit_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            requester_id = st.text_input("👤 Your Employee ID *", placeholder="e.g. EMP-1042")
            requester_role = st.text_input("💼 Your Role / Team *", placeholder="e.g. Admin - Infrastructure Team")
            urgency = st.selectbox("🚨 Urgency *", URGENCY_LEVELS)

        with c2:
            title = st.text_input("📄 Document Title *", placeholder="e.g. New Database Backup Procedure")
            doc_type = st.selectbox("📂 Document Type *", list(DOC_TYPES.keys()))
            st.markdown("<br>", unsafe_allow_html=True)
            cto_note = "→ Requires CTO approval" if DOC_TYPES[doc_type]["needs_cto"] else "→ Team Lead + Tech Manager only"
            st.caption(f"Routing preview: {cto_note}")

        description = st.text_area(
            "📋 Description *",
            placeholder="Describe what this document needs to cover and why it's needed…",
            height=120,
        )

        submitted = st.form_submit_button("🚀 Submit Request", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not requester_id.strip():   errors.append("Employee ID required.")
        if not requester_role.strip(): errors.append("Your role/team required.")
        if not title.strip():          errors.append("Document title required.")
        if not description.strip():    errors.append("Description required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            req = _create_request(
                title=title.strip(),
                description=description.strip(),
                urgency=urgency,
                role=requester_role.strip(),
                doc_type=doc_type,
                requester_id=requester_id.strip(),
            )
            st.success(f"✅ **{req['id']}** created! Routed to Team Lead — 2-hour approval timer started.")
            st.info(f"⏰ Expires at: {_fmt(req['expires_at'])}")
            st.balloons()


# ── Tab: Review / Approve ─────────────────────────────────────────────────────

def _tab_review():
    role = st.session_state.ap_role

    if not role:
        st.info("👆 Select your role in the **Your Role** dropdown above to see requests awaiting your approval.")
        return

    # Which requests need this role?
    stage_map = {
        "Team Lead":    "Team Lead",
        "Tech Manager": "Tech Manager",
        "CTO":          "CTO",
        "CEO":          "CEO",
    }
    my_stage = stage_map.get(role, "")
    pending = [
        r for r in st.session_state.ap_requests
        if not r["completed"] and r["current_stage"] == my_stage
    ]

    st.subheader(f"✅ Requests Awaiting Your Approval — {role}")

    # Also show forwarded-to-you requests
    forwarded = [
        r for r in st.session_state.ap_requests
        if not r["completed"] and r.get("forward_to") == role
    ]
    if forwarded:
        st.warning(f"📨 {len(forwarded)} request(s) forwarded directly to you.")
        for r in forwarded:
            _review_card(r, role, forwarded=True)
        st.markdown("---")

    if not pending and not forwarded:
        st.success("🎉 No requests waiting for your approval right now.")
        return

    for req in pending:
        _review_card(req, role)


def _review_card(req: dict, role: str, forwarded: bool = False):
    urgency_color = {"Normal": "🟢", "URGENT": "🟡", "CRITICAL": "🔴"}.get(req["urgency"], "⚪")
    label = (
        f"{urgency_color} **{req['id']}** · {req['title']} "
        f"| {req['doc_type']} | {req['urgency']} | {_time_left(req['expires_at'])}"
    )
    with st.expander(label, expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Requester:** {req['requester_id']}")
        c2.markdown(f"**Role:** {req['requester_role']}")
        c3.markdown(f"**Submitted:** {_fmt(req['created_at'])}")
        c1.markdown(f"**Doc Type:** {req['doc_type']}")
        c2.markdown(f"**Urgency:** {req['urgency']}")
        c3.markdown(f"**Needs CTO:** {'Yes' if req['needs_cto'] else 'No'}")

        st.markdown("**Description:**")
        st.markdown(
            f"<div style='background:#ede9fe;padding:14px;border-radius:10px;"
            f"border-left:4px solid #7c3aed;color:#1e1b4b;font-size:14px'>"
            f"{req['description']}</div>",
            unsafe_allow_html=True,
        )

        # Previous approvals
        if req["approved_by"]:
            st.markdown(f"**✅ Already approved by:** {', '.join(req['approved_by'])}")

        st.markdown("---")
        note = st.text_area(
            "📝 Your note / reason (optional)",
            key=f"note_{req['id']}_{role}",
            placeholder="Add context for the audit trail…",
            height=70,
        )

        # Build action buttons based on role
        cols = st.columns(4)
        note_val = note  # capture before button click

        with cols[0]:
            if st.button("✅ Approve", key=f"ap_{req['id']}_{role}", use_container_width=True, type="primary"):
                _advance_stage(req, role, note_val or "Approved.")
                st.success("Approved & forwarded!")
                st.rerun()

        with cols[1]:
            if st.button("❌ Reject", key=f"rj_{req['id']}_{role}", use_container_width=True):
                _reject(req, role, note_val or "Rejected.")
                st.error("Request rejected.")
                st.rerun()

        with cols[2]:
            # Forward option
            forward_targets = [s for s in STAGES[:-1] if s != role]
            fwd_to = st.selectbox(
                "Forward to",
                ["— select —"] + forward_targets,
                key=f"fwd_sel_{req['id']}_{role}",
                label_visibility="collapsed",
            )
            if st.button("🔄 Forward", key=f"fwd_{req['id']}_{role}", use_container_width=True):
                if fwd_to == "— select —":
                    st.warning("Select a person to forward to.")
                else:
                    _forward(req, role, fwd_to, note_val or f"Forwarded to {fwd_to}.")
                    req["current_stage"] = fwd_to
                    req["status"] = f"Pending {fwd_to}"
                    req["expires_at"] = _now() + timedelta(hours=TIMEOUT_HOURS)
                    st.info(f"Forwarded to {fwd_to}.")
                    st.rerun()

        with cols[3]:
            # CTO can escalate to CEO
            if role == "CTO":
                if st.button("⬆️ → CEO", key=f"ceo_{req['id']}", use_container_width=True):
                    _escalate_to_ceo(req, role, note_val or "Escalated to CEO for final decision.")
                    st.warning("Escalated to CEO.")
                    st.rerun()


# ── Tab: All Requests ─────────────────────────────────────────────────────────

def _tab_all():
    st.subheader("📊 All Requests")

    reqs = list(reversed(st.session_state.ap_requests))
    if not reqs:
        st.info("No requests yet. Use the **Submit Request** tab to create one.")
        return

    # Filter
    c1, c2, c3 = st.columns(3)
    with c1:
        sf = st.selectbox("Filter by Status", [
            "All", "Pending Team Lead", "Pending Tech Manager",
            "Pending CTO", "Pending CEO", "Approved", "Rejected", "Expired"
        ], key="ap_status_filter")
    with c2:
        uf = st.selectbox("Filter by Urgency", ["All"] + URGENCY_LEVELS, key="ap_urgency_filter")
    with c3:
        # Admin can delete
        if st.session_state.ap_admin_authed:
            if st.button("🗑️ Clear ALL requests", key="ap_clear_all"):
                st.session_state.ap_requests = []
                st.rerun()

    if sf != "All":
        reqs = [r for r in reqs if r["status"] == sf]
    if uf != "All":
        reqs = [r for r in reqs if r["urgency"] == uf]

    st.markdown(f"**{len(reqs)} request(s) shown**")
    st.markdown("---")

    if not reqs:
        st.info("No requests match the selected filters.")
        return

    for req in reqs:
        _summary_card(req)


def _summary_card(req: dict):
    status_icon = {
        "Approved": "✅",
        "Rejected": "❌",
        "Expired":  "⏰",
    }.get(req["status"], "⏳")

    urgency_color = {"Normal": "🟢", "URGENT": "🟡", "CRITICAL": "🔴"}.get(req["urgency"], "⚪")
    timer_str = "" if req["completed"] else f" | {_time_left(req['expires_at'])}"

    with st.expander(
        f"{status_icon} {req['id']} — {req['title']} | {urgency_color} {req['urgency']} | "
        f"{req['status']}{timer_str}",
        expanded=False,
    ):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Requester:** {req['requester_id']}")
        c2.markdown(f"**Role:** {req['requester_role']}")
        c3.markdown(f"**Doc Type:** {req['doc_type']}")
        c1.markdown(f"**Status:** {req['status']}")
        c2.markdown(f"**Stage:** {req['current_stage']}")
        c3.markdown(f"**Created:** {_fmt(req['created_at'])}")

        if req["approved_by"]:
            st.success(f"✅ Approved by: {' → '.join(req['approved_by'])}")
        if req["rejected_by"]:
            st.error(f"❌ Rejected by: {req['rejected_by']}")
        if req["status"] == "Expired":
            st.warning(f"⏰ Expired at stage: {req['current_stage']}")

        # Progress bar
        stage_idx = STAGES.index(req["current_stage"]) if req["current_stage"] in STAGES else 0
        progress = stage_idx / (len(STAGES) - 1) if not req["completed"] else 1.0
        if req["status"] == "Approved":
            progress = 1.0
        st.progress(progress, text=f"Pipeline progress: {req['current_stage']}")

        # Admin delete
        if st.session_state.ap_admin_authed:
            if st.button(f"🗑️ Delete {req['id']}", key=f"del_{req['id']}"):
                st.session_state.ap_requests = [
                    r for r in st.session_state.ap_requests if r["id"] != req["id"]
                ]
                st.rerun()


# ── Tab: Audit Trail ──────────────────────────────────────────────────────────

def _tab_audit():
    st.subheader("📜 Full Audit Trail")

    reqs = list(reversed(st.session_state.ap_requests))
    if not reqs:
        st.info("No requests yet.")
        return

    # Filter to one request or show all
    req_ids = ["All requests"] + [r["id"] for r in reqs]
    chosen = st.selectbox("Select Request", req_ids, key="ap_audit_filter")

    if chosen != "All requests":
        reqs = [r for r in reqs if r["id"] == chosen]

    for req in reqs:
        st.markdown(f"#### {req['id']} — {req['title']}")
        st.caption(f"Status: **{req['status']}** | Doc type: {req['doc_type']} | Urgency: {req['urgency']}")

        for entry in req["audit"]:
            t     = entry["time"]
            actor = entry["actor"]
            action = entry["action"]
            note  = entry.get("note", "")

            icon = "🤖" if actor == "System" else "👤"
            time_str = _fmt(t) if isinstance(t, datetime) else str(t)

            cols = st.columns([1.5, 1.5, 4])
            cols[0].markdown(f"<small style='color:#6b7280'>{time_str}</small>", unsafe_allow_html=True)
            cols[1].markdown(f"{icon} **{actor}**")
            cols[2].markdown(f"{action}" + (f" — *{note}*" if note else ""))

        st.markdown("---")
