"""
doc_request.py  –  Document Request Portal
──────────────────────────────────────────
Allows employees to raise requests for:
  • A new document to be written
  • An existing document to be uploaded
  • A specific topic they need documented

Admin can view, respond to, and resolve all requests
directly from this tab (no separate admin login needed
if already logged in via Admin Panel session state).

Run this SQL once in Supabase SQL Editor:
─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doc_requests (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    job_role    TEXT NOT NULL,
    doc_title   TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    description TEXT NOT NULL,
    priority    TEXT NOT NULL DEFAULT 'Medium',
    status      TEXT NOT NULL DEFAULT 'Pending',
    admin_note  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE doc_requests DISABLE ROW LEVEL SECURITY;
"""

import streamlit as st
from datetime import datetime, timezone, timedelta

# ── IST Timezone ──────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Doc request types ─────────────────────────────────────────────────────────
DOC_TYPES = [
    "📝 Write a new document",
    "📤 Upload an existing document",
    "📚 Add to knowledge base (Q&A)",
    "🔄 Update an outdated document",
    "❓ Document a process / workflow",
    "🗂️ Other",
]

JOB_ROLES = [
    "Select…",
    "Software Engineer",
    "Data Analyst",
    "QA Engineer",
    "DevOps Engineer",
    "Product Manager",
    "HR / Operations",
    "Other",
]

STATUS_COLORS = {
    "Pending":     ("badge-open",       "🟡"),
    "In Review":   ("badge-inprogress", "🔵"),
    "Fulfilled":   ("badge-resolved",   "🟢"),
    "Rejected":    ("badge-overdue",    "🔴"),
}

PRIO_COLORS = {
    "High":   "prio-high",
    "Medium": "prio-medium",
    "Low":    "prio-low",
}


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _get_db():
    """Reuse the same Supabase client pattern as the rest of the app."""
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _to_ist(dt_str: str) -> str:
    try:
        normalised = dt_str.strip().replace(" ", "T").replace("Z", "+00:00")
        if "+" not in normalised[10:]:
            normalised += "+00:00"
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return dt_str


def db_submit_doc_request(user_id, job_role, doc_title, doc_type, description, priority):
    db = _get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    row = {
        "user_id":     user_id,
        "job_role":    job_role,
        "doc_title":   doc_title,
        "doc_type":    doc_type,
        "description": description,
        "priority":    priority,
        "status":      "Pending",
    }
    result = db.table("doc_requests").insert(row).execute()
    if result.data:
        req = result.data[0]
        st.toast(f"📄 Doc Request #{req['id']} saved to `doc_requests` table!", icon="☁️")
        return req
    raise Exception("Insert returned no data.")


def db_get_doc_requests(status_filter=None):
    db = _get_db()
    if db is None:
        return []
    try:
        q = db.table("doc_requests").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        return q.execute().data or []
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return []


def db_update_doc_request(rid, status, note):
    db = _get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    db.table("doc_requests").update({
        "status":     status,
        "admin_note": note,
    }).eq("id", rid).execute()
    st.toast(f"✏️ Doc Request #{rid} updated → {status}", icon="☁️")


def db_delete_doc_request(rid):
    db = _get_db()
    if db:
        db.table("doc_requests").delete().eq("id", rid).execute()
        st.toast(f"🗑️ Doc Request #{rid} deleted from Supabase", icon="☁️")


def db_doc_request_stats():
    reqs = db_get_doc_requests()
    return {
        "total":     len(reqs),
        "pending":   sum(1 for r in reqs if r["status"] == "Pending"),
        "in_review": sum(1 for r in reqs if r["status"] == "In Review"),
        "fulfilled": sum(1 for r in reqs if r["status"] == "Fulfilled"),
        "rejected":  sum(1 for r in reqs if r["status"] == "Rejected"),
    }


# ── Main page ─────────────────────────────────────────────────────────────────

def page_doc_request():
    st.markdown("# 📄 Document Request Portal")
    st.markdown(
        "<p style='color:#6b7280'>Need a document written, uploaded, or added to the "
        "knowledge base? Raise a request here and the admin team will handle it.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    tab_employee, tab_admin = st.tabs(["📝 Raise a Request", "🛡️ Admin — Manage Requests"])

    with tab_employee:
        _employee_section()

    with tab_admin:
        _admin_section()


# ── Employee: submit a doc request ────────────────────────────────────────────

def _employee_section():
    st.markdown("### 💬 What document do you need?")
    st.markdown(
        "<p style='color:#6b7280;font-size:14px'>Fill in the details below. "
        "The admin team will review your request and either write, upload, "
        "or add the document to the knowledge base.</p>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        user_id  = st.text_input("👤 Employee ID *", placeholder="e.g. EMP-1042", key="dr_user_id")
        job_role = st.selectbox("💼 Job Role *", JOB_ROLES, key="dr_job_role")
        priority = st.selectbox("🚨 Priority", ["Medium", "High", "Low"], key="dr_priority")

    with c2:
        doc_title = st.text_input(
            "📌 Document Title / Topic *",
            placeholder="e.g. How to set up CI/CD pipeline",
            key="dr_doc_title",
        )
        doc_type = st.selectbox("📂 Request Type *", DOC_TYPES, key="dr_doc_type")

    description = st.text_area(
        "📋 Describe what you need *",
        placeholder=(
            "e.g. I need a step-by-step guide on how to deploy our app to AWS. "
            "It should cover environment setup, Docker, and rollback steps."
        ),
        height=130,
        key="dr_description",
    )

    st.markdown(
        "<small style='color:#6b7280'>💡 The more detail you provide, "
        "the faster the admin team can fulfil your request.</small>",
        unsafe_allow_html=True,
    )

    if st.button("🚀 Submit Document Request", use_container_width=True, key="dr_submit"):
        errors = []
        if not user_id.strip():           errors.append("Employee ID is required.")
        if job_role == "Select…":         errors.append("Please select your job role.")
        if not doc_title.strip():         errors.append("Document title / topic is required.")
        if not description.strip():       errors.append("Description is required.")

        for e in errors:
            st.error(e)

        if not errors:
            try:
                req = db_submit_doc_request(
                    user_id.strip(), job_role, doc_title.strip(),
                    doc_type, description.strip(), priority,
                )
                st.success(
                    f"✅ Request #{req.get('id', '–')} submitted! "
                    "The admin team will review it and get back to you.",
                    icon="🎉",
                )
                st.balloons()
            except Exception as ex:
                st.error(f"Submission failed: {ex}")

    # ── Show employee's own requests (by Employee ID) ─────────────────────────
    st.markdown("---")
    st.markdown("### 🔍 Track Your Requests")
    track_id = st.text_input(
        "Enter your Employee ID to see your requests",
        placeholder="e.g. EMP-1042",
        key="dr_track_id",
    )
    if st.button("🔎 Search", key="dr_track_search") and track_id.strip():
        all_reqs = db_get_doc_requests()
        my_reqs  = [r for r in all_reqs if r.get("user_id", "").lower() == track_id.strip().lower()]
        if not my_reqs:
            st.info(f"No requests found for Employee ID: {track_id.strip()}")
        else:
            st.success(f"Found {len(my_reqs)} request(s).")
            for r in my_reqs:
                _request_card_readonly(r)


def _request_card_readonly(r):
    status     = r.get("status", "Pending")
    badge_cls, status_icon = STATUS_COLORS.get(status, ("badge-open", "🟡"))
    created    = _to_ist(r.get("created_at", ""))
    admin_note = r.get("admin_note", "")

    with st.expander(
        f"{status_icon} #{r['id']} — {r['doc_title']} | {status} | {r['priority']} | {created}"
    ):
        st.markdown(
            f"<span class='{badge_cls}'>{status}</span>&nbsp;"
            f"<span class='{PRIO_COLORS.get(r['priority'], 'prio-medium')}'>{r['priority']}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**Request Type:** {r.get('doc_type', '—')}")
        st.markdown(f"**Submitted:** {created}")
        st.markdown("**Your Description:**")
        st.markdown(f"<div class='answer-box'>{r.get('description', '—')}</div>", unsafe_allow_html=True)

        if admin_note:
            st.markdown("**Admin Response:**")
            st.markdown(f"<div class='learned-box'>{admin_note}</div>", unsafe_allow_html=True)
        else:
            st.info("No admin response yet. Please check back later.", icon="⏳")


# ── Admin: manage all doc requests ────────────────────────────────────────────

def _admin_section():
    # Reuse admin login from main app session state
    ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")

    if not st.session_state.get("admin_logged_in"):
        st.markdown("### 🔐 Admin Login Required")
        col, _ = st.columns([1.5, 2.5])
        with col:
            pwd = st.text_input("Password", type="password", key="dr_admin_pwd")
            if st.button("Login →", use_container_width=True, key="dr_admin_login"):
                if pwd == ADMIN_PWD:
                    st.session_state["admin_logged_in"] = True
                    st.toast("🛡️ Admin logged in", icon="✅")
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    # ── Stats row ─────────────────────────────────────────────────────────────
    try:
        stats = db_doc_request_stats()
        cols  = st.columns(5)
        for col, val, label, icon in zip(
            cols,
            [stats["total"], stats["pending"], stats["in_review"], stats["fulfilled"], stats["rejected"]],
            ["Total", "Pending", "In Review", "Fulfilled", "Rejected"],
            ["📋", "🟡", "🔵", "🟢", "🔴"],
        ):
            with col:
                st.markdown(
                    f"<div class='metric-card'>"
                    f"<div style='font-size:24px'>{icon}</div>"
                    f"<div class='metric-number'>{val}</div>"
                    f"<div class='metric-label'>{label}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
    except Exception as e:
        st.error(f"Stats error: {e}")

    st.markdown("---")

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([1.5, 1.5, 2])
    with fc1:
        sf = st.selectbox(
            "Filter by Status",
            ["All", "Pending", "In Review", "Fulfilled", "Rejected"],
            key="dr_admin_sf",
        )
    with fc2:
        pf = st.selectbox(
            "Filter by Priority",
            ["All", "High", "Medium", "Low"],
            key="dr_admin_pf",
        )
    with fc3:
        search = st.text_input("🔍 Search", placeholder="keyword or employee ID", key="dr_admin_search")

    # ── Load & filter ─────────────────────────────────────────────────────────
    reqs = db_get_doc_requests(sf if sf != "All" else None)
    if pf != "All":
        reqs = [r for r in reqs if r.get("priority") == pf]
    if search.strip():
        kw   = search.strip().lower()
        reqs = [
            r for r in reqs
            if kw in r.get("doc_title", "").lower()
            or kw in r.get("description", "").lower()
            or kw in r.get("user_id", "").lower()
        ]

    if not reqs:
        st.info("No document requests found.", icon="📭")
        return

    st.markdown(f"**{len(reqs)} request(s)**")

    for r in reqs:
        _admin_request_card(r)


def _admin_request_card(r):
    rid        = r.get("id")
    status     = r.get("status", "Pending")
    priority   = r.get("priority", "Medium")
    created    = _to_ist(r.get("created_at", ""))
    badge_cls, status_icon = STATUS_COLORS.get(status, ("badge-open", "🟡"))
    prio_cls   = PRIO_COLORS.get(priority, "prio-medium")

    with st.expander(
        f"{status_icon} #{rid} — {r.get('user_id','?')} | {r.get('doc_title','?')} "
        f"| {status} | {priority} | {created}"
    ):
        st.markdown(
            f"<span class='{badge_cls}'>{status}</span>&nbsp;"
            f"<span class='{prio_cls}'>{priority}</span>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Employee:** {r.get('user_id','—')}")
            st.markdown(f"**Job Role:** {r.get('job_role','—')}")
            st.markdown(f"**Submitted:** {created}")
        with c2:
            st.markdown(f"**Request Type:** {r.get('doc_type','—')}")
            st.markdown(f"**Priority:** {priority}")

        st.markdown("**What they need:**")
        st.markdown(
            f"<div class='answer-box'>{r.get('description','—')}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        nc1, nc2 = st.columns(2)
        with nc1:
            new_status = st.selectbox(
                "Update Status",
                ["Pending", "In Review", "Fulfilled", "Rejected"],
                index=["Pending", "In Review", "Fulfilled", "Rejected"].index(status),
                key=f"dr_status_{rid}",
            )
        with nc2:
            note = st.text_area(
                "Admin Response / Note",
                value=r.get("admin_note") or "",
                placeholder="e.g. Document has been uploaded to the knowledge base. Link: ...",
                height=100,
                key=f"dr_note_{rid}",
            )

        bc1, bc2, _ = st.columns([1, 1, 3])
        with bc1:
            if st.button("💾 Save", key=f"dr_save_{rid}", use_container_width=True):
                try:
                    db_update_doc_request(rid, new_status, note)
                    st.success("✅ Request updated!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with bc2:
            if st.button("🗑️ Delete", key=f"dr_del_{rid}", use_container_width=True):
                try:
                    db_delete_doc_request(rid)
                    st.warning("Deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
