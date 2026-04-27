import streamlit as st
from datetime import datetime

# ════════════════════════════════════════════════════════
#  APPROVAL PIPELINE PAGE
#  Drop this file alongside app.py and restart the app.
# ════════════════════════════════════════════════════════

# ── Inline CSS (mirrors app.py palette) ─────────────────
_CSS = """
<style>
.pipeline-card {
    background: white;
    border-radius: 14px;
    padding: 18px 22px;
    margin-bottom: 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    border-left: 5px solid #7c3aed;
}
.pipeline-card.approved  { border-left-color: #059669; }
.pipeline-card.rejected  { border-left-color: #dc2626; }
.pipeline-card.pending   { border-left-color: #d97706; }

.stage-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    margin-right: 6px;
}
.stage-pending  { background:#fef3c7; color:#92400e; }
.stage-approved { background:#d1fae5; color:#065f46; }
.stage-rejected { background:#fee2e2; color:#991b1b; }
.stage-review   { background:#dbeafe; color:#1e40af; }

.step-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid #f3f4f6;
    font-size: 14px;
}
.step-icon { font-size: 18px; width: 28px; text-align: center; }
.step-label { flex: 1; color: #374151; font-weight: 500; }
.step-status { font-size: 12px; font-weight: 600; }

.metric-card {
    background: white;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.metric-number { font-family:'Syne',sans-serif; font-size:32px; font-weight:800; color:#7c3aed; }
.metric-label  { font-size:13px; color:#6b7280; margin-top:4px; }
</style>
"""

# ── Supabase helper (reuse app.py connection) ────────────
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

# ── Ensure the pipeline table exists (best-effort) ──────
_PIPELINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    requester    TEXT NOT NULL,
    department   TEXT NOT NULL,
    request_type TEXT NOT NULL,
    description  TEXT NOT NULL,
    priority     TEXT NOT NULL DEFAULT 'Medium',
    stage        TEXT NOT NULL DEFAULT 'Submitted',
    status       TEXT NOT NULL DEFAULT 'Pending',
    reviewer     TEXT,
    reviewer_note TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE approval_requests DISABLE ROW LEVEL SECURITY;
"""

# ── Pipeline stages ──────────────────────────────────────
STAGES = ["Submitted", "Manager Review", "HR Review", "Finance Review", "Approved / Rejected"]

STAGE_ICONS = {
    "Submitted":        "📥",
    "Manager Review":   "👔",
    "HR Review":        "👥",
    "Finance Review":   "💰",
    "Approved / Rejected": "✅",
}

# ── DB helpers ───────────────────────────────────────────
def _fetch_requests(status_filter=None, stage_filter=None):
    db = _get_db()
    if db is None:
        return []
    try:
        q = db.table("approval_requests").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        if stage_filter and stage_filter != "All":
            q = q.eq("stage", stage_filter)
        return q.execute().data or []
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return []

def _create_request(title, requester, department, request_type, description, priority):
    db = _get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    row = {
        "title": title,
        "requester": requester,
        "department": department,
        "request_type": request_type,
        "description": description,
        "priority": priority,
        "stage": "Submitted",
        "status": "Pending",
    }
    result = db.table("approval_requests").insert(row).execute()
    if result.data:
        return result.data[0]
    raise Exception("Insert returned no data.")

def _advance_stage(rid, current_stage, action, reviewer, note):
    db = _get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")

    if action == "Reject":
        new_stage  = "Approved / Rejected"
        new_status = "Rejected"
    elif action == "Approve":
        idx = STAGES.index(current_stage) if current_stage in STAGES else 0
        if idx < len(STAGES) - 2:           # more stages to go
            new_stage  = STAGES[idx + 1]
            new_status = "Pending"
        else:                                # final stage
            new_stage  = "Approved / Rejected"
            new_status = "Approved"
    else:
        return

    db.table("approval_requests").update({
        "stage":        new_stage,
        "status":       new_status,
        "reviewer":     reviewer,
        "reviewer_note": note,
        "updated_at":   datetime.utcnow().isoformat(),
    }).eq("id", rid).execute()

def _delete_request(rid):
    db = _get_db()
    if db:
        db.table("approval_requests").delete().eq("id", rid).execute()

def _stats():
    rows = _fetch_requests()
    return {
        "total":    len(rows),
        "pending":  sum(1 for r in rows if r["status"] == "Pending"),
        "approved": sum(1 for r in rows if r["status"] == "Approved"),
        "rejected": sum(1 for r in rows if r["status"] == "Rejected"),
    }

# ── Progress bar renderer ────────────────────────────────
def _render_pipeline_progress(current_stage, status):
    total = len(STAGES)
    current_idx = STAGES.index(current_stage) if current_stage in STAGES else 0

    st.markdown("<div style='margin:8px 0 4px'>", unsafe_allow_html=True)
    cols = st.columns(total)
    for i, (stage, col) in enumerate(zip(STAGES, cols)):
        icon = STAGE_ICONS.get(stage, "🔲")
        if status == "Rejected" and stage == "Approved / Rejected":
            dot_color = "#dc2626"
            label_color = "#dc2626"
        elif i < current_idx:
            dot_color = "#059669"
            label_color = "#059669"
        elif i == current_idx:
            dot_color = "#7c3aed"
            label_color = "#7c3aed"
        else:
            dot_color = "#d1d5db"
            label_color = "#9ca3af"

        with col:
            st.markdown(
                f"""
                <div style='text-align:center'>
                  <div style='font-size:22px'>{icon}</div>
                  <div style='width:12px;height:12px;border-radius:50%;
                              background:{dot_color};margin:4px auto;'></div>
                  <div style='font-size:10px;color:{label_color};font-weight:600;
                              line-height:1.2'>{stage}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  MAIN PAGE FUNCTION (called by app.py)
# ════════════════════════════════════════════════════════
def page_approval_pipeline():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("# 📋 Approval Pipeline")
    st.markdown(
        "<p style='color:#6b7280'>Submit, track, and manage multi-stage approval requests "
        "across departments.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Tabs ─────────────────────────────────────────────
    tab_submit, tab_track, tab_admin = st.tabs([
        "➕ New Request", "🔍 Track Requests", "🛠️ Admin Review"
    ])

    # ── TAB 1 : Submit ────────────────────────────────────
    with tab_submit:
        st.markdown("### 📝 Submit an Approval Request")
        c1, c2 = st.columns(2)
        with c1:
            requester  = st.text_input("👤 Your Name / Employee ID *", placeholder="e.g. EMP-1042")
            department = st.selectbox("🏢 Department *", [
                "Select…", "Engineering", "HR", "Finance",
                "Product", "Operations", "Marketing", "Legal", "Other"
            ])
            priority = st.selectbox("🚨 Priority", ["Medium", "High", "Low"])
        with c2:
            title = st.text_input("📌 Request Title *", placeholder="e.g. Budget approval for Q3 tooling")
            request_type = st.selectbox("📂 Request Type *", [
                "Select…", "Budget / Expense", "Hiring / Headcount",
                "Policy Change", "Vendor Contract", "IT / Access",
                "Leave / Time-Off", "Other"
            ])

        description = st.text_area(
            "📋 Description *",
            placeholder="Describe what you need approved, why it is needed, and any relevant context…",
            height=130,
        )

        if st.button("🚀 Submit Request", use_container_width=False):
            errors = []
            if not requester.strip():          errors.append("Name / Employee ID required.")
            if department == "Select…":        errors.append("Select your department.")
            if request_type == "Select…":      errors.append("Select a request type.")
            if not title.strip():              errors.append("Request title required.")
            if not description.strip():        errors.append("Description required.")
            for err in errors:
                st.error(err)
            if not errors:
                try:
                    rec = _create_request(
                        title.strip(), requester.strip(), department,
                        request_type, description.strip(), priority
                    )
                    st.success(
                        f"✅ Request #{rec.get('id', '–')} submitted! "
                        "Use the **Track Requests** tab to monitor progress.",
                        icon="🎉",
                    )
                except Exception as ex:
                    st.error(f"Submission failed: {ex}")

    # ── TAB 2 : Track ─────────────────────────────────────
    with tab_track:
        st.markdown("### 🔍 Track Your Requests")

        search_id  = st.text_input("Search by Name / Employee ID", placeholder="e.g. EMP-1042")
        sf_col, pf_col = st.columns(2)
        with sf_col:
            status_f = st.selectbox("Filter by Status", ["All", "Pending", "Approved", "Rejected"], key="track_sf")
        with pf_col:
            stage_f  = st.selectbox("Filter by Stage",  ["All"] + STAGES, key="track_stage")

        rows = _fetch_requests(
            status_filter=status_f if status_f != "All" else None,
            stage_filter =stage_f  if stage_f  != "All" else None,
        )
        if search_id.strip():
            rows = [r for r in rows if search_id.strip().lower() in r.get("requester", "").lower()]

        if not rows:
            st.info("No requests found.", icon="📭")
        else:
            st.markdown(f"**{len(rows)} request(s) found**")
            for r in rows:
                status  = r.get("status", "Pending")
                stage   = r.get("stage",  "Submitted")
                card_cls = {"Approved": "approved", "Rejected": "rejected"}.get(status, "pending")
                s_badge  = {"Pending": "stage-pending", "Approved": "stage-approved",
                            "Rejected": "stage-rejected"}.get(status, "stage-review")
                try:
                    dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                    created_fmt = dt.strftime("%d %b %Y, %I:%M %p")
                except Exception:
                    created_fmt = r.get("created_at", "")

                with st.expander(
                    f"#{r['id']} — {r['title']} | {r['requester']} | {status} | {stage}"
                ):
                    st.markdown(
                        f"<span class='stage-badge {s_badge}'>{status}</span>"
                        f"<span class='stage-badge stage-review'>{r.get('request_type','')}</span>"
                        f"<span class='stage-badge stage-review'>{r.get('priority','')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**Requester:** {r.get('requester','–')} &nbsp;|&nbsp; "
                        f"**Dept:** {r.get('department','–')} &nbsp;|&nbsp; "
                        f"**Submitted:** {created_fmt}"
                    )
                    st.markdown("**Description:**")
                    st.markdown(
                        f"<div class='answer-box' style='background:#f5f3ff;border-left-color:#7c3aed'>"
                        f"{r.get('description','–')}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Pipeline Progress:**")
                    _render_pipeline_progress(stage, status)

                    if r.get("reviewer_note"):
                        st.markdown(
                            f"<div style='background:#f0fdf4;border-left:4px solid #059669;"
                            f"border-radius:10px;padding:12px 16px;margin-top:10px;font-size:14px'>"
                            f"💬 <strong>Reviewer note:</strong> {r['reviewer_note']}</div>",
                            unsafe_allow_html=True,
                        )

    # ── TAB 3 : Admin Review ──────────────────────────────
    with tab_admin:
        ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")
        if not st.session_state.get("pipeline_admin_logged_in"):
            st.markdown("### 🔐 Admin Login")
            col, _ = st.columns([1.5, 2.5])
            with col:
                pwd = st.text_input("Password", type="password", key="pipeline_pwd")
                if st.button("Login →", use_container_width=True, key="pipeline_login"):
                    if pwd == ADMIN_PWD:
                        st.session_state["pipeline_admin_logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        else:
            hdr, logout_col = st.columns([5, 1])
            with hdr:
                st.markdown("### 🛠️ Admin — Review Requests")
            with logout_col:
                if st.button("Logout", key="pipeline_logout"):
                    st.session_state["pipeline_admin_logged_in"] = False
                    st.rerun()

            # Metrics
            try:
                s = _stats()
                mc = st.columns(4)
                for col, val, label, icon in zip(
                    mc,
                    [s["total"], s["pending"], s["approved"], s["rejected"]],
                    ["Total", "Pending", "Approved", "Rejected"],
                    ["📋", "🟡", "🟢", "🔴"],
                ):
                    with col:
                        st.markdown(
                            f"<div class='metric-card'><div style='font-size:24px'>{icon}</div>"
                            f"<div class='metric-number'>{val}</div>"
                            f"<div class='metric-label'>{label}</div></div>",
                            unsafe_allow_html=True,
                        )
            except Exception as e:
                st.error(f"Stats error: {e}")

            st.markdown("---")

            af_col, pf2_col = st.columns(2)
            with af_col:
                adm_status = st.selectbox("Filter Status", ["All", "Pending", "Approved", "Rejected"], key="adm_sf")
            with pf2_col:
                adm_stage  = st.selectbox("Filter Stage",  ["All"] + STAGES, key="adm_stage")

            adm_rows = _fetch_requests(
                status_filter=adm_status if adm_status != "All" else None,
                stage_filter =adm_stage  if adm_stage  != "All" else None,
            )

            if not adm_rows:
                st.info("No requests found.", icon="📭")
            else:
                st.markdown(f"**{len(adm_rows)} request(s)**")
                for r in adm_rows:
                    rid    = r["id"]
                    status = r.get("status", "Pending")
                    stage  = r.get("stage",  "Submitted")

                    with st.expander(
                        f"#{rid} — {r['title']} | {r['requester']} | {status} | {stage}"
                    ):
                        st.markdown(
                            f"**Requester:** {r.get('requester','–')} &nbsp;|&nbsp; "
                            f"**Dept:** {r.get('department','–')} &nbsp;|&nbsp; "
                            f"**Type:** {r.get('request_type','–')} &nbsp;|&nbsp; "
                            f"**Priority:** {r.get('priority','–')}"
                        )
                        st.markdown("**Description:**")
                        st.markdown(
                            f"<div class='answer-box' style='background:#f5f3ff;"
                            f"border-left-color:#7c3aed'>{r.get('description','–')}</div>",
                            unsafe_allow_html=True,
                        )

                        st.markdown("**Pipeline Progress:**")
                        _render_pipeline_progress(stage, status)
                        st.markdown("---")

                        if status not in ("Approved", "Rejected"):
                            rev_col, note_col = st.columns(2)
                            with rev_col:
                                reviewer = st.text_input(
                                    "Your Name / ID", key=f"rev_{rid}",
                                    placeholder="e.g. Jane (HR Manager)"
                                )
                            with note_col:
                                rev_note = st.text_area(
                                    "Review Note", key=f"rnote_{rid}",
                                    height=90,
                                    placeholder="Optional comment or condition…"
                                )

                            btn_col1, btn_col2, btn_col3, _ = st.columns([1, 1, 1, 3])
                            with btn_col1:
                                if st.button("✅ Approve", key=f"approve_{rid}", use_container_width=True):
                                    try:
                                        _advance_stage(rid, stage, "Approve", reviewer, rev_note)
                                        st.success("Advanced to next stage!")
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(str(ex))
                            with btn_col2:
                                if st.button("❌ Reject", key=f"reject_{rid}", use_container_width=True):
                                    try:
                                        _advance_stage(rid, stage, "Reject", reviewer, rev_note)
                                        st.warning("Request rejected.")
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(str(ex))
                            with btn_col3:
                                if st.button("🗑️ Delete", key=f"del_{rid}", use_container_width=True):
                                    try:
                                        _delete_request(rid)
                                        st.warning("Deleted.")
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(str(ex))
                        else:
                            st.markdown(
                                f"<div style='color:#6b7280;font-size:13px'>"
                                f"This request is <strong>{status}</strong> — no further action needed.</div>",
                                unsafe_allow_html=True,
                            )
                            if st.button("🗑️ Delete", key=f"del2_{rid}"):
                                try:
                                    _delete_request(rid)
                                    st.rerun()
                                except Exception as ex:
                                    st.error(str(ex))

        # ── Schema hint ──────────────────────────────────
        with st.expander("📄 Required Supabase Table (run once in SQL Editor)"):
            st.code(_PIPELINE_SCHEMA, language="sql")
