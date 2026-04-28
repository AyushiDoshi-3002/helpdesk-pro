"""
approval_pipeline.py  –  role-based tabs
─────────────────────────────────────────
Tabs: Submit (public) | Team Lead | Tech Manager | CTO | CEO
Each approver tab is password-protected and shows only the
requests currently sitting at that person's stage.
"""

import streamlit as st
from datetime import datetime, timedelta, timezone

# ── Passwords (one per role) ──────────────────────────────────────────────────
ROLE_PASSWORDS = {
    "Team Lead":    "lead123",
    "Tech Manager": "mgr123",
    "CTO":          "cto123",
    "CEO":          "ceo123",
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

# Chain always walks bottom-up to the category's top approver
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


# ── Session-state init ────────────────────────────────────────────────────────

def _init():
    defaults = {
        "ap_requests":  [],
        "ap_next_id":   1,
        "ap_role_auth": {},   # { "Team Lead": True/False, ... }
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


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

        cfg   = DOC_CATEGORIES[category]
        chain = _build_chain(category)
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
        _request_card(req, show_actions=False, ctx="sub")


# ── Role tab (password-gated, approve/reject only) ────────────────────────────

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

    # Requests sitting at this role right now
    mine = [
        r for r in reversed(st.session_state.ap_requests)
        if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role
    ]
    # Requests this role already acted on
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


# ── Request card (shared) ─────────────────────────────────────────────────────

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

        # Pipeline progress
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
                t    = _fmt(entry["time"]) if isinstance(entry["time"], datetime) else str(entry["time"])
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
