"""
doc_request.py  –  Document Request Portal
──────────────────────────────────────────
Employees raise a request to get a document written / uploaded / added to KB.
The request is automatically routed through the same approval chain as
approval_pipeline.py (based on document category).

Run this SQL ONCE in Supabase SQL Editor before using:
──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doc_requests (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    job_role    TEXT NOT NULL,
    doc_title   TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    category    TEXT NOT NULL,
    subtype     TEXT NOT NULL,
    description TEXT NOT NULL,
    urgency     TEXT NOT NULL DEFAULT 'Normal',
    priority    TEXT NOT NULL DEFAULT 'Medium',
    chain       JSONB,
    stage_idx   INTEGER DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'Pending',
    admin_note  TEXT,
    history     JSONB,
    done        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE doc_requests DISABLE ROW LEVEL SECURITY;
"""

import json
import streamlit as st
from datetime import datetime, timezone, timedelta

# ── IST Timezone ──────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Same category + chain config as approval_pipeline.py ─────────────────────
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

ROLE_PASSWORDS = {
    "Team Lead":    "Lead123",
    "Tech Manager": "Manager123",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

TIMEOUT_HOURS = 2

JOB_ROLES = [
    "Select…", "Software Engineer", "Data Analyst", "QA Engineer",
    "DevOps Engineer", "Product Manager", "HR / Operations", "Other",
]

DOC_REQUEST_TYPES = [
    "📝 Write a new document",
    "📤 Upload an existing document",
    "📚 Add to Knowledge Base (Q&A)",
    "🔄 Update an outdated document",
    "❓ Document a process / workflow",
    "🗂️ Other",
]

STATUS_BADGE = {
    "Pending":  "badge-open",
    "Approved": "badge-resolved",
    "Rejected": "badge-overdue",
    "Expired":  "badge-overdue",
}

STATUS_ICON = {
    "Pending":  "🟡",
    "Approved": "🟢",
    "Rejected": "🔴",
    "Expired":  "⏰",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_chain(category: str) -> list:
    cfg = DOC_CATEGORIES.get(category, {})
    return list(_CHAINS.get(cfg.get("approver", "Team Lead"), ["Team Lead"]))


def _now():
    return datetime.now(IST)


def _to_ist(dt_str) -> str:
    try:
        if isinstance(dt_str, datetime):
            return dt_str.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
        normalised = str(dt_str).strip().replace(" ", "T").replace("Z", "+00:00")
        if "+" not in normalised[10:]:
            normalised += "+00:00"
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return str(dt_str)


def _serialize_history(history: list) -> list:
    out = []
    for entry in history:
        e = dict(entry)
        if isinstance(e.get("time"), datetime):
            e["time"] = e["time"].isoformat()
        out.append(e)
    return out


def _deserialize_history(history) -> list:
    if not history:
        return []
    if isinstance(history, str):
        history = json.loads(history)
    out = []
    for entry in history:
        e = dict(entry)
        t = e.get("time")
        if isinstance(t, str):
            try:
                dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                e["time"] = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        out.append(e)
    return out


# ── Supabase client ───────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _get_db():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


# ── DB helpers ────────────────────────────────────────────────────────────────

def db_submit(user_id, job_role, doc_title, doc_type, category,
              subtype, description, urgency, priority) -> dict:
    db = _get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")

    now   = _now()
    cfg   = DOC_CATEGORIES[category]
    chain = _build_chain(category)
    auto  = cfg["auto"]

    if auto:
        history = [
            {"time": now.isoformat(), "by": "System", "action": "Submitted"},
            {"time": now.isoformat(), "by": "Admin",
             "action": "Auto-approved (General document)"},
        ]
        row = {
            "user_id": user_id, "job_role": job_role,
            "doc_title": doc_title, "doc_type": doc_type,
            "category": category, "subtype": subtype,
            "description": description, "urgency": urgency,
            "priority": priority,
            "chain": json.dumps([]), "stage_idx": 0,
            "status": "Approved",
            "history": json.dumps(history),
            "done": True,
        }
    else:
        history = [
            {"time": now.isoformat(), "by": "System",
             "action": f"Submitted → routed to {chain[0]}"},
        ]
        row = {
            "user_id": user_id, "job_role": job_role,
            "doc_title": doc_title, "doc_type": doc_type,
            "category": category, "subtype": subtype,
            "description": description, "urgency": urgency,
            "priority": priority,
            "chain": json.dumps(chain), "stage_idx": 0,
            "status": "Pending",
            "history": json.dumps(history),
            "done": False,
            "created_at": now.isoformat(),
        }

    result = db.table("doc_requests").insert(row).execute()
    if result.data:
        req = result.data[0]
        st.toast(f"📄 Doc Request #{req['id']} saved to Supabase!", icon="☁️")
        return req
    raise Exception("Insert returned no data.")


def db_load_all() -> list:
    db = _get_db()
    if db is None:
        return []
    try:
        rows = (
            db.table("doc_requests")
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data or []
        )
        for r in rows:
            if isinstance(r.get("chain"), str):
                r["chain"] = json.loads(r["chain"])
            elif r.get("chain") is None:
                r["chain"] = []
            r["history"] = _deserialize_history(r.get("history"))
        return rows
    except Exception as e:
        st.error(f"Load error: {e}")
        return []


def db_update(rid, status, admin_note, stage_idx=None, done=None, history=None):
    db = _get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    payload = {"status": status, "admin_note": admin_note}
    if stage_idx is not None:
        payload["stage_idx"] = stage_idx
    if done is not None:
        payload["done"] = done
    if history is not None:
        payload["history"] = json.dumps(_serialize_history(history))
    db.table("doc_requests").update(payload).eq("id", rid).execute()
    st.toast(f"✏️ Doc Request #{rid} → {status}", icon="☁️")


def db_delete(rid):
    db = _get_db()
    if db:
        db.table("doc_requests").delete().eq("id", rid).execute()
        st.toast(f"🗑️ Doc Request #{rid} deleted", icon="☁️")


# ── Approval actions ──────────────────────────────────────────────────────────

def _do_approve(req: dict, note: str):
    chain     = req["chain"]
    stage_idx = req["stage_idx"]
    role      = chain[stage_idx]
    history   = list(req["history"])
    history.append({"time": _now(), "by": role, "action": "Approved", "note": note})

    next_idx = stage_idx + 1
    if next_idx >= len(chain):
        history.append({"time": _now(), "by": "System",
                        "action": "All levels approved — FULFILLED ✅"})
        db_update(req["id"], "Approved", req.get("admin_note", ""),
                  stage_idx=stage_idx, done=True, history=history)
    else:
        history.append({"time": _now(), "by": "System",
                        "action": f"Forwarded to {chain[next_idx]}"})
        db_update(req["id"], "Pending", req.get("admin_note", ""),
                  stage_idx=next_idx, done=False, history=history)


def _do_reject(req: dict, note: str):
    chain     = req["chain"]
    stage_idx = req["stage_idx"]
    role      = chain[stage_idx]
    history   = list(req["history"])
    history.append({"time": _now(), "by": role, "action": "Rejected", "note": note})
    db_update(req["id"], "Rejected", req.get("admin_note", ""),
              done=True, history=history)


def _check_expiry(req: dict):
    if req.get("done"):
        return
    try:
        created_at = req.get("created_at", "")
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = created_at
        if (_now() - dt.astimezone(IST)) > timedelta(hours=TIMEOUT_HOURS):
            stage   = req["chain"][req["stage_idx"]] if req.get("chain") else "Unknown"
            history = list(req.get("history", []))
            history.append({"time": _now(), "by": "System",
                            "action": f"Expired — no response from {stage}"})
            db_update(req["id"], "Expired", req.get("admin_note", ""),
                      done=True, history=history)
            req["status"] = "Expired"
            req["done"]   = True
    except Exception:
        pass


def _stats(reqs):
    return {
        "total":    len(reqs),
        "pending":  sum(1 for r in reqs if r["status"] == "Pending"),
        "approved": sum(1 for r in reqs if r["status"] == "Approved"),
        "rejected": sum(1 for r in reqs if r["status"] == "Rejected"),
        "expired":  sum(1 for r in reqs if r["status"] == "Expired"),
    }


# ════════════════════════════════════════════════════════
#  MAIN PAGE
# ════════════════════════════════════════════════════════

def page_doc_request():
    st.markdown("# 📄 Document Request Portal")
    st.markdown(
        "<p style='color:#6b7280'>Need a document written, uploaded, or added to the "
        "knowledge base? Submit a request — it will be routed through the approval "
        "chain automatically based on the document category.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    all_reqs = db_load_all()
    for r in all_reqs:
        _check_expiry(r)

    def _n(role):
        return sum(
            1 for r in all_reqs
            if not r.get("done") and r.get("chain") and
            r["chain"][r["stage_idx"]] == role
        )

    tabs = st.tabs([
        "📝 Submit Request",
        "🔍 Track My Request",
        f"👤 Team Lead ({_n('Team Lead')})",
        f"🔧 Tech Manager ({_n('Tech Manager')})",
        f"⚙️ CTO ({_n('CTO')})",
        f"👑 CEO ({_n('CEO')})",
    ])

    with tabs[0]: _tab_submit(all_reqs)
    with tabs[1]: _tab_track(all_reqs)
    with tabs[2]: _tab_role("Team Lead", all_reqs)
    with tabs[3]: _tab_role("Tech Manager", all_reqs)
    with tabs[4]: _tab_role("CTO", all_reqs)
    with tabs[5]: _tab_role("CEO", all_reqs)


# ════════════════════════════════════════════════════════
#  TAB: SUBMIT
# ════════════════════════════════════════════════════════

def _tab_submit(all_reqs):
    st.markdown("### 💬 Raise a Document Request")
    st.markdown(
        "<p style='color:#6b7280;font-size:14px'>"
        "Fill in the details below. Your request will be routed for approval "
        "based on the document category you choose.</p>",
        unsafe_allow_html=True,
    )

    # Use session state to track selected category for live subtype update
    if "dr_selected_category" not in st.session_state:
        st.session_state["dr_selected_category"] = list(DOC_CATEGORIES.keys())[0]

    with st.form("doc_req_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            user_id  = st.text_input("👤 Employee ID *", placeholder="e.g. EMP-1042")
            job_role = st.selectbox("💼 Job Role *", JOB_ROLES)
            priority = st.selectbox("🚨 Priority", ["Medium", "High", "Low"])
        with c2:
            doc_title = st.text_input(
                "📌 Document Title / Topic *",
                placeholder="e.g. AWS Deployment Runbook",
            )
            doc_type = st.selectbox("📂 Request Type *", DOC_REQUEST_TYPES)
            urgency  = st.selectbox("⚡ Urgency", ["Normal", "URGENT", "CRITICAL"])

        category = st.selectbox(
            "🗂️ Document Category *",
            list(DOC_CATEGORIES.keys()),
            format_func=lambda c: DOC_CATEGORIES[c]["label"],
        )
        subtype = st.selectbox(
            "📑 Subtype",
            DOC_CATEGORIES[category]["subtypes"],
        )

        description = st.text_area(
            "📋 Describe what you need *",
            placeholder=(
                "e.g. We need a step-by-step runbook for deploying to AWS. "
                "It should cover Docker setup, environment variables, and rollback steps."
            ),
            height=120,
        )

        cfg       = DOC_CATEGORIES[category]
        chain     = _build_chain(category)
        route_str = (
            "Auto-approved instantly (General category)"
            if cfg["auto"]
            else "  →  ".join(chain) + f"  ·  {TIMEOUT_HOURS}h per level"
        )
        st.caption(f"📋 Approval route: {route_str}")

        submitted = st.form_submit_button(
            "🚀 Submit Document Request", type="primary", use_container_width=True
        )

    if submitted:
        errors = []
        if not user_id.strip():     errors.append("Employee ID is required.")
        if job_role == "Select…":   errors.append("Please select your job role.")
        if not doc_title.strip():   errors.append("Document title is required.")
        if not description.strip(): errors.append("Description is required.")
        for e in errors:
            st.error(e)
        if not errors:
            try:
                req = db_submit(
                    user_id.strip(), job_role, doc_title.strip(),
                    doc_type, category, subtype,
                    description.strip(), urgency, priority,
                )
                if req.get("status") == "Approved":
                    st.success(
                        f"✅ Request #{req['id']} auto-approved instantly! (General category)",
                        icon="🎉",
                    )
                else:
                    raw_chain = req.get("chain", [])
                    if isinstance(raw_chain, str):
                        raw_chain = json.loads(raw_chain)
                    first = raw_chain[0] if raw_chain else "?"
                    st.success(
                        f"✅ Request #{req['id']} submitted! First stop: **{first}**",
                        icon="🎉",
                    )
                st.balloons()
            except Exception as ex:
                st.error(f"Submission failed: {ex}")

    # Summary metrics
    if all_reqs:
        st.divider()
        st.markdown("### 📊 Overview")
        stats = _stats(all_reqs)
        c1, c2, c3, c4, c5 = st.columns(5)
        for col, val, label, icon in zip(
            [c1, c2, c3, c4, c5],
            [stats["total"], stats["pending"], stats["approved"],
             stats["rejected"], stats["expired"]],
            ["Total", "Pending", "Approved", "Rejected", "Expired"],
            ["📋", "🟡", "🟢", "🔴", "⏰"],
        ):
            with col:
                st.markdown(
                    f"<div class='metric-card'>"
                    f"<div style='font-size:22px'>{icon}</div>"
                    f"<div class='metric-number' style='font-size:28px'>{val}</div>"
                    f"<div class='metric-label'>{label}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )


# ════════════════════════════════════════════════════════
#  TAB: TRACK
# ════════════════════════════════════════════════════════

def _tab_track(all_reqs):
    st.markdown("### 🔍 Track Your Document Requests")
    st.markdown(
        "<p style='color:#6b7280;font-size:14px'>"
        "Enter your Employee ID to see the current status and approval history "
        "of your document requests.</p>",
        unsafe_allow_html=True,
    )

    track_id = st.text_input(
        "👤 Employee ID", placeholder="e.g. EMP-1042", key="dr_track_id"
    )
    if st.button("🔎 Search", key="dr_track_search") and track_id.strip():
        my_reqs = [
            r for r in all_reqs
            if r.get("user_id", "").lower() == track_id.strip().lower()
        ]
        if not my_reqs:
            st.info(f"No requests found for Employee ID: **{track_id.strip()}**")
        else:
            st.success(f"Found **{len(my_reqs)}** request(s).")
            for r in my_reqs:
                _card_readonly(r)


def _card_readonly(r):
    status    = r.get("status", "Pending")
    icon      = STATUS_ICON.get(status, "🟡")
    badge_cls = STATUS_BADGE.get(status, "badge-open")
    created   = _to_ist(r.get("created_at", ""))
    chain     = r.get("chain", [])
    stage_idx = r.get("stage_idx", 0)
    current   = chain[stage_idx] if chain and not r.get("done") else "—"

    with st.expander(
        f"{icon} #{r['id']} — {r.get('doc_title','?')} | {status} | {created}"
    ):
        st.markdown(
            f"<span class='{badge_cls}'>{status}</span>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Category:** {r.get('category','—')} › {r.get('subtype','—')}")
            st.markdown(f"**Request Type:** {r.get('doc_type','—')}")
        with c2:
            st.markdown(f"**Submitted:** {created}")
            st.markdown(f"**Currently with:** {current}")

        if chain:
            parts = []
            for i, s in enumerate(chain):
                if status == "Approved" or i < stage_idx:
                    parts.append(f"~~{s}~~ ✅")
                elif i == stage_idx and not r.get("done"):
                    parts.append(f"**{s} ⏳**")
                else:
                    parts.append(s)
            st.markdown("**Approval Chain:**  " + "  →  ".join(parts))

        st.markdown("**Your Description:**")
        st.markdown(
            f"<div class='answer-box'>{r.get('description','—')}</div>",
            unsafe_allow_html=True,
        )

        if r.get("admin_note"):
            st.markdown("**Admin Note:**")
            st.markdown(
                f"<div class='learned-box'>{r['admin_note']}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("No admin note yet. Please check back later.", icon="⏳")

        with st.expander("📅 Full Approval History"):
            for entry in r.get("history", []):
                t    = _to_ist(entry.get("time", ""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"`{t}`  **{entry['by']}**: {entry['action']}{note}")


# ════════════════════════════════════════════════════════
#  TAB: ROLE
# ════════════════════════════════════════════════════════

def _tab_role(role: str, all_reqs: list):
    auth_key = f"dr_role_auth_{role}"
    authed   = st.session_state.get(auth_key, False)

    if not authed:
        st.subheader(f"🔐 {role} Login")
        col, _ = st.columns([1.5, 3])
        with col:
            pwd = st.text_input("Password", type="password", key=f"dr_pwd_{role}")
            if st.button("Log in", type="primary", use_container_width=True,
                         key=f"dr_login_{role}"):
                if pwd == ROLE_PASSWORDS.get(role, ""):
                    st.session_state[auth_key] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    hcol, lcol = st.columns([6, 1])
    with hcol:
        st.subheader(f"📥 Inbox — {role}")
    with lcol:
        if st.button("Log out", key=f"dr_logout_{role}"):
            st.session_state[auth_key] = False
            st.rerun()

    ctx = role.replace(" ", "_").lower()

    mine = [
        r for r in all_reqs
        if not r.get("done") and r.get("chain") and
        r["chain"][r["stage_idx"]] == role
    ]
    handled = [
        r for r in all_reqs
        if r.get("done") and
        any(e.get("by") == role for e in r.get("history", []))
    ]

    if not mine:
        st.success("✅ Nothing waiting for your approval right now.")
    else:
        st.markdown(f"**{len(mine)} request(s) awaiting your decision**")
        for req in mine:
            _card_role(req, role, ctx, show_actions=True)

    if handled:
        st.divider()
        with st.expander(f"Previously handled ({len(handled)})"):
            for req in handled:
                _card_role(req, role, f"{ctx}_done", show_actions=False)


def _card_role(req: dict, role: str, ctx: str, show_actions: bool):
    rid       = req["id"]
    status    = req.get("status", "Pending")
    chain     = req.get("chain", [])
    stage_idx = req.get("stage_idx", 0)
    icon      = STATUS_ICON.get(status, "🟡")
    urg_icon  = {"URGENT": "🟡", "CRITICAL": "🔴"}.get(req.get("urgency", ""), "")
    k         = f"{ctx}_{rid}"

    label = (
        f"{icon} #{rid}  ·  {req.get('doc_title','?')}  {urg_icon}"
        f"  ·  {req.get('category','?')}  ·  {req.get('priority','?')}"
    )

    with st.expander(label, expanded=show_actions and not req.get("done")):
        c1, c2, c3 = st.columns(3)
        c1.markdown(
            f"**Requester**  \n{req.get('user_id','—')} ({req.get('job_role','—')})"
        )
        c2.markdown(
            f"**Category**  \n{req.get('category','—')} › {req.get('subtype','—')}"
        )
        c3.markdown(f"**Request Type**  \n{req.get('doc_type','—')}")

        st.markdown(f"> {req.get('description','')}")

        # Chain progress
        if chain:
            parts = []
            for i, s in enumerate(chain):
                if status == "Approved" or i < stage_idx:
                    parts.append(f"~~{s}~~ ✅")
                elif i == stage_idx and not req.get("done"):
                    parts.append(f"**{s} ⏳**")
                elif req.get("done") and i == stage_idx:
                    icon_end = "❌" if status == "Rejected" else "⏰"
                    parts.append(f"**{s} {icon_end}**")
                else:
                    parts.append(s)
            st.markdown("  →  ".join(parts))
        else:
            st.caption("Auto-approved — no chain required.")

        with st.expander("📅 History", key=f"dr_hist_{k}"):
            for entry in req.get("history", []):
                t    = _to_ist(entry.get("time", ""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"`{t}`  **{entry['by']}**: {entry['action']}{note}")

        if show_actions and not req.get("done"):
            note = st.text_input(
                "Note / Reason (optional)", key=f"dr_note_{k}",
                placeholder="Add a comment or reason for your decision…",
            )
            ca, cr, _ = st.columns([1, 1, 4])
            with ca:
                if st.button("✅ Approve", key=f"dr_ap_{k}",
                             type="primary", use_container_width=True):
                    _do_approve(req, note)
                    st.rerun()
            with cr:
                if st.button("❌ Reject", key=f"dr_rj_{k}",
                             use_container_width=True):
                    _do_reject(req, note)
                    st.rerun()
