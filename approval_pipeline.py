import streamlit as st
import time
import json
import requests
from datetime import datetime

# ════════════════════════════════════════════════════════
#  APPROVAL PIPELINE  —  Agentic Multi-Stage Document Flow
#  Two tabs: Submit Request | Executive Review
# ════════════════════════════════════════════════════════

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

.pipe-header {
    font-family: 'Syne', sans-serif;
    font-size: 28px; font-weight: 800; color: #1e1b4b; margin-bottom: 4px;
}
.flow-wrap { display:flex; flex-direction:column; gap:0; margin:16px 0; }
.flow-node { display:flex; align-items:flex-start; gap:16px; position:relative; }
.flow-node:not(:last-child)::after {
    content:''; position:absolute; left:19px; top:44px;
    width:2px; height:calc(100% - 8px);
    background:linear-gradient(180deg,#7c3aed44,#7c3aed11);
}
.flow-icon {
    width:40px; height:40px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:18px; flex-shrink:0; z-index:1; border:2px solid transparent;
}
.flow-icon.waiting   { background:#f3f4f6; border-color:#d1d5db; }
.flow-icon.running   { background:#ede9fe; border-color:#7c3aed; animation:pulse 1s infinite; }
.flow-icon.approved  { background:#d1fae5; border-color:#059669; }
.flow-icon.rejected  { background:#fee2e2; border-color:#dc2626; }
.flow-icon.skipped   { background:#f9fafb; border-color:#e5e7eb; opacity:0.4; }
.flow-icon.manual    { background:#fef3c7; border-color:#d97706; }
@keyframes pulse {
    0%,100% { box-shadow:0 0 0 0 rgba(124,58,237,0.3); }
    50%      { box-shadow:0 0 0 6px rgba(124,58,237,0); }
}
.flow-body { flex:1; padding:10px 0 18px; }
.flow-title { font-family:'Syne',sans-serif; font-size:14px; font-weight:700; color:#1e1b4b; }
.flow-auto-badge {
    display:inline-block; font-size:10px; font-weight:700;
    padding:2px 8px; border-radius:20px; margin-left:6px;
    background:#ede9fe; color:#7c3aed; vertical-align:middle;
}
.flow-manual-badge {
    display:inline-block; font-size:10px; font-weight:700;
    padding:2px 8px; border-radius:20px; margin-left:6px;
    background:#fef3c7; color:#92400e; vertical-align:middle;
}
.flow-desc  { font-size:12px; color:#6b7280; margin-top:2px; }
.flow-result {
    font-size:12px; margin-top:4px; padding:6px 10px;
    border-radius:8px; line-height:1.5;
}
.flow-result.approved { background:#f0fdf4; color:#166534; border-left:3px solid #059669; }
.flow-result.rejected { background:#fef2f2; color:#991b1b; border-left:3px solid #dc2626; }
.flow-result.running  { background:#f5f3ff; color:#5b21b6; border-left:3px solid #7c3aed; }
.flow-result.manual   { background:#fffbeb; color:#92400e; border-left:3px solid #d97706; }

.status-pill {
    display:inline-block; padding:3px 12px; border-radius:20px;
    font-size:11px; font-weight:700;
}
.pill-escalated { background:#fef3c7; color:#92400e; }
.pill-approved  { background:#d1fae5; color:#065f46; }
.pill-rejected  { background:#fee2e2; color:#991b1b; }

.metric-card {
    background:white; border-radius:14px; padding:18px;
    text-align:center; box-shadow:0 2px 10px rgba(0,0,0,0.06);
}
.metric-number { font-family:'Syne',sans-serif; font-size:30px; font-weight:800; color:#7c3aed; }
.metric-label  { font-size:12px; color:#6b7280; margin-top:3px; }
</style>
"""

# ── Pipeline stage definitions ────────────────────────────────────────────────
PIPELINE_STAGES = [
    {"key":"intent",     "label":"Intent Agent",          "icon":"🧠", "auto":True,
     "desc":"Classifies request type, urgency, and sensitivity level"},
    {"key":"functional", "label":"Functional Agent",      "icon":"🟢", "auto":True,
     "desc":"Validates business relevance — is this request valid for the department?"},
    {"key":"technical",  "label":"Technical Agent",       "icon":"🔵", "auto":True,
     "desc":"Checks system/data access safety and technical feasibility"},
    {"key":"compliance", "label":"Compliance Agent",      "icon":"🔴", "auto":True,
     "desc":"Validates confidentiality, privacy laws, and company policies"},
    {"key":"executive",  "label":"Executive Authority",   "icon":"🟣", "auto":False,
     "desc":"Final human approval — triggered only for high-risk documents"},
    {"key":"fetch",      "label":"Document Fetch Agent",  "icon":"📄", "auto":True,
     "desc":"Retrieves the document from the source system"},
    {"key":"storage",    "label":"Storage Agent",         "icon":"💾", "auto":True,
     "desc":"Stores document securely in Drive / DB"},
    {"key":"delivery",   "label":"Delivery Agent",        "icon":"📬", "auto":True,
     "desc":"Shares document with the requesting admin"},
]

# ── Supabase helpers ──────────────────────────────────────────────────────────
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

def _fetch_requests(status_filter=None):
    db = _get_db()
    if db is None: return []
    try:
        q = db.table("approval_requests").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        return q.execute().data or []
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return []

def _create_request(title, requester, department, doc_type, description, priority, risk_level, stage_results):
    db = _get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    is_escalated = risk_level == "High"
    row = {
        "title":         title,
        "requester":     requester,
        "department":    department,
        "request_type":  doc_type,
        "description":   description,
        "priority":      priority,
        "stage":         "Escalated to Executive" if is_escalated else "Document Released",
        "status":        "Escalated"              if is_escalated else "Approved",
        "reviewer":      None,
        "reviewer_note": None,
        "stage_results": json.dumps(stage_results),
        "risk_level":    risk_level,
        "created_at":    datetime.utcnow().isoformat(),
        "updated_at":    datetime.utcnow().isoformat(),
    }
    result = db.table("approval_requests").insert(row).execute()
    if result.data: return result.data[0]
    raise Exception("Insert returned no data.")

def _executive_decision(rid, decision, note, reviewer):
    db = _get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    new_status = "Approved" if decision == "Approve" else "Rejected"
    db.table("approval_requests").update({
        "status":        new_status,
        "stage":         "Document Released" if new_status == "Approved" else "Rejected by Executive",
        "reviewer":      reviewer,
        "reviewer_note": note,
        "updated_at":    datetime.utcnow().isoformat(),
    }).eq("id", rid).execute()

def _delete_request(rid):
    db = _get_db()
    if db:
        db.table("approval_requests").delete().eq("id", rid).execute()

def _stats():
    rows = _fetch_requests()
    return {
        "total":     len(rows),
        "escalated": sum(1 for r in rows if r["status"] == "Escalated"),
        "approved":  sum(1 for r in rows if r["status"] == "Approved"),
        "rejected":  sum(1 for r in rows if r["status"] == "Rejected"),
    }

# ── Claude API agent decision ─────────────────────────────────────────────────
def _call_agent(agent_name: str, ctx: dict) -> dict:
    system = (
        f"You are the {agent_name} in an automated document approval pipeline. "
        "Evaluate the document request. Reply ONLY with a valid JSON object "
        "(no markdown, no extra text) with keys: "
        "'decision' (Approved or Rejected), "
        "'reason' (1-2 sentences), "
        "'risk' (Low, Medium, or High)."
    )
    user_msg = (
        f"Document request:\n"
        f"- Title: {ctx.get('title')}\n"
        f"- Type: {ctx.get('doc_type')}\n"
        f"- Department: {ctx.get('department')}\n"
        f"- Requester: {ctx.get('requester')}\n"
        f"- Description: {ctx.get('description')}\n"
        f"- Priority: {ctx.get('priority')}\n\n"
        f"Make your autonomous decision as {agent_name}."
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "system":     system,
                "messages":   [{"role": "user", "content": user_msg}],
            },
            timeout=30,
        )
        text = ""
        for block in resp.json().get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(text)
    except Exception as e:
        return {"decision": "Approved", "reason": f"Auto-approved (fallback). {e}", "risk": "Low"}

# ── Flow renderer ─────────────────────────────────────────────────────────────
def _render_flow(stage_results: dict, current_key: str = None, high_risk: bool = False):
    st.markdown("<div class='flow-wrap'>", unsafe_allow_html=True)
    for stage in PIPELINE_STAGES:
        key, auto = stage["key"], stage["auto"]

        if key == "executive" and not high_risk and key not in stage_results and key != current_key:
            icon_cls, result_html = "skipped", ""
        elif key in stage_results:
            res = stage_results[key]
            d   = res.get("decision", "Approved")
            if d == "Pending":
                icon_cls, result_html = "manual", (
                    "<div class='flow-result manual'>🟣 Awaiting Executive decision…</div>"
                )
            else:
                icon_cls    = "approved" if d == "Approved" else "rejected"
                tick        = "✅" if d == "Approved" else "❌"
                result_html = (
                    f"<div class='flow-result {icon_cls}'>{tick} {res.get('reason','')}</div>"
                )
        elif key == current_key:
            icon_cls    = "running"
            result_html = "<div class='flow-result running'>⏳ Processing…</div>"
        else:
            icon_cls, result_html = "waiting", ""

        badge = (
            "<span class='flow-auto-badge'>AUTO</span>" if auto
            else "<span class='flow-manual-badge'>MANUAL</span>"
        )
        st.markdown(
            f"<div class='flow-node'>"
            f"  <div class='flow-icon {icon_cls}'>{stage['icon']}</div>"
            f"  <div class='flow-body'>"
            f"    <div class='flow-title'>{stage['label']}{badge}</div>"
            f"    <div class='flow-desc'>{stage['desc']}</div>"
            f"    {result_html}"
            f"  </div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════
def page_approval_pipeline():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("<div class='pipe-header'>📋 Approval Pipeline</div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#6b7280;margin-bottom:20px'>"
        "Agentic multi-stage document approval — AI agents decide automatically. "
        "Executive review triggered only for high-risk documents.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    tab_submit, tab_exec = st.tabs(["➕ Submit Request", "🟣 Executive Review"])

    # ══════════════════════════════════════════════════
    #  TAB 1 — SUBMIT
    # ══════════════════════════════════════════════════
    with tab_submit:
        st.markdown("### 📝 New Document Request")
        st.markdown(
            "<small style='color:#7c3aed'>Submit your request — AI agents will automatically "
            "evaluate it through each stage. Executive review is triggered only for high-risk documents.</small><br><br>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            requester  = st.text_input("👤 Admin Name / Employee ID *", placeholder="e.g. EMP-1042")
            department = st.selectbox("🏢 Department *", [
                "Select…","Finance","HR","Engineering",
                "Legal","Operations","Marketing","Executive","Other"
            ])
            priority = st.selectbox("🚨 Priority", ["Medium","High","Low"])
        with c2:
            title    = st.text_input("📌 Document Title *", placeholder="e.g. Q3 Financial Report")
            doc_type = st.selectbox("📂 Document Type *", [
                "Select…","Financial Report","Employee Data",
                "System Design","Vendor Contract","Policy Document",
                "Audit Report","Strategic Plan","Other"
            ])

        description = st.text_area(
            "📋 Why do you need this document? *",
            placeholder="Explain the business reason, who will use it, and any urgency…",
            height=100,
        )

        run_clicked = st.button("🚀 Submit & Run Agents", use_container_width=False)

        if run_clicked:
            errors = []
            if not requester.strip():   errors.append("Admin Name / ID required.")
            if department == "Select…": errors.append("Select department.")
            if doc_type == "Select…":   errors.append("Select document type.")
            if not title.strip():       errors.append("Document title required.")
            if not description.strip(): errors.append("Description required.")
            for e in errors: st.error(e)

            if not errors:
                ctx = {
                    "title":       title.strip(),
                    "doc_type":    doc_type,
                    "department":  department,
                    "requester":   requester.strip(),
                    "description": description.strip(),
                    "priority":    priority,
                }
                st.markdown("---")
                st.markdown("### ⚙️ Agent Pipeline Running…")

                flow_ph       = st.empty()
                stage_results = {}
                overall_risk  = "Low"
                passed        = True

                pre_exec  = ["intent","functional","technical","compliance"]
                post_exec = ["fetch","storage","delivery"]

                def refresh(cur=None):
                    with flow_ph.container():
                        _render_flow(stage_results, current_key=cur,
                                     high_risk=(overall_risk == "High"))

                # ── Auto agents 1-4 ──────────────────────────────
                for key in pre_exec:
                    refresh(key)
                    time.sleep(0.4)
                    stage = next(s for s in PIPELINE_STAGES if s["key"] == key)
                    result = _call_agent(stage["label"], ctx)
                    stage_results[key] = result
                    if result.get("risk") == "High":
                        overall_risk = "High"
                    if result.get("decision") == "Rejected":
                        passed = False
                        refresh()
                        st.error(
                            f"❌ **{stage['label']}** rejected this request: {result.get('reason','')}"
                        )
                        break

                # ── Executive gate ───────────────────────────────
                if passed and overall_risk == "High":
                    stage_results["executive"] = {
                        "decision": "Pending",
                        "reason":   "Escalated to Executive Authority for manual review — high-risk document.",
                        "risk":     "High",
                    }
                    refresh()
                    try:
                        _create_request(
                            ctx["title"], ctx["requester"], ctx["department"],
                            ctx["doc_type"], ctx["description"], ctx["priority"],
                            overall_risk, stage_results,
                        )
                    except Exception as ex:
                        st.warning(f"Could not save: {ex}")
                    st.warning(
                        "🟣 **Escalated to Executive Authority.** "
                        "This document is high-risk. An executive must approve it "
                        "in the **Executive Review** tab before release."
                    )

                elif passed:
                    # ── Auto agents 6-8 ──────────────────────────
                    for key in post_exec:
                        refresh(key)
                        time.sleep(0.5)
                        stage  = next(s for s in PIPELINE_STAGES if s["key"] == key)
                        result = _call_agent(stage["label"], ctx)
                        stage_results[key] = result
                    refresh()
                    try:
                        _create_request(
                            ctx["title"], ctx["requester"], ctx["department"],
                            ctx["doc_type"], ctx["description"], ctx["priority"],
                            overall_risk, stage_results,
                        )
                    except Exception as ex:
                        st.warning(f"Could not save: {ex}")
                    st.success(
                        "✅ **All agents approved.** Document has been fetched, stored, and delivered!"
                    )

    # ══════════════════════════════════════════════════
    #  TAB 2 — EXECUTIVE REVIEW
    # ══════════════════════════════════════════════════
    with tab_exec:
        ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")
        if not st.session_state.get("exec_pipeline_logged_in"):
            st.markdown("### 🔐 Executive Login")
            col, _ = st.columns([1.5, 2.5])
            with col:
                pwd = st.text_input("Password", type="password", key="exec_pwd")
                if st.button("Login →", use_container_width=True, key="exec_login"):
                    if pwd == ADMIN_PWD:
                        st.session_state["exec_pipeline_logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        else:
            hcol, lcol = st.columns([5,1])
            with hcol: st.markdown("### 🟣 Executive Authority — Escalated Requests")
            with lcol:
                if st.button("Logout", key="exec_logout"):
                    st.session_state["exec_pipeline_logged_in"] = False
                    st.rerun()

            try:
                s  = _stats()
                mc = st.columns(4)
                for col, val, label, icon in zip(
                    mc,
                    [s["total"], s["escalated"], s["approved"], s["rejected"]],
                    ["Total","Needs Review","Approved","Rejected"],
                    ["📋","🟡","🟢","🔴"],
                ):
                    with col:
                        st.markdown(
                            f"<div class='metric-card'>"
                            f"<div style='font-size:22px'>{icon}</div>"
                            f"<div class='metric-number'>{val}</div>"
                            f"<div class='metric-label'>{label}</div></div>",
                            unsafe_allow_html=True,
                        )
            except Exception as e:
                st.error(f"Stats error: {e}")

            st.markdown("---")
            sf   = st.selectbox("Show", ["All","Escalated","Approved","Rejected"], key="exec_sf")
            rows = _fetch_requests(sf if sf != "All" else None)

            if not rows:
                st.info("No requests found.", icon="📭")
            else:
                st.markdown(f"**{len(rows)} request(s)**")
                for r in rows:
                    rid    = r["id"]
                    status = r.get("status","Escalated")
                    risk   = r.get("risk_level","High")
                    pill   = {"Escalated":"pill-escalated","Approved":"pill-approved",
                              "Rejected":"pill-rejected"}.get(status,"pill-escalated")
                    try:
                        dt  = datetime.fromisoformat(r["created_at"].replace("Z","+00:00"))
                        fmt = dt.strftime("%d %b %Y, %I:%M %p")
                    except Exception:
                        fmt = r.get("created_at","")

                    with st.expander(
                        f"#{rid} — {r.get('title','?')} | {r.get('requester','?')} | {status} | Risk: {risk}"
                    ):
                        st.markdown(
                            f"<span class='status-pill {pill}'>{status}</span>&nbsp;"
                            f"<span class='status-pill' style='background:#f3f4f6;color:#374151'>Risk: {risk}</span>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"**Requester:** {r.get('requester','–')} &nbsp;|&nbsp; "
                            f"**Dept:** {r.get('department','–')} &nbsp;|&nbsp; "
                            f"**Type:** {r.get('request_type','–')} &nbsp;|&nbsp; "
                            f"**Submitted:** {fmt}"
                        )
                        st.markdown(
                            f"<div style='background:#f5f3ff;border-left:4px solid #7c3aed;"
                            f"border-radius:10px;padding:12px 16px;margin:10px 0;font-size:14px'>"
                            f"{r.get('description','–')}</div>",
                            unsafe_allow_html=True,
                        )

                        # Agent decisions replay
                        try:
                            sr = json.loads(r.get("stage_results") or "{}")
                            if sr:
                                st.markdown("**🤖 Agent Decisions:**")
                                _render_flow(sr, high_risk=(risk=="High"))
                        except Exception:
                            pass

                        if status == "Escalated":
                            st.markdown("---")
                            rc1, rc2 = st.columns(2)
                            with rc1:
                                reviewer = st.text_input("Your Name", key=f"rev_{rid}",
                                                         placeholder="Executive name")
                            with rc2:
                                rev_note = st.text_area("Decision Note", key=f"rnote_{rid}",
                                                        height=80,
                                                        placeholder="Reason for approval or rejection…")
                            bc1, bc2, bc3, _ = st.columns([1,1,1,3])
                            with bc1:
                                if st.button("✅ Approve", key=f"app_{rid}", use_container_width=True):
                                    try:
                                        _executive_decision(rid,"Approve",rev_note,reviewer)
                                        st.success("✅ Approved — document released.")
                                        st.rerun()
                                    except Exception as ex: st.error(str(ex))
                            with bc2:
                                if st.button("❌ Reject", key=f"rej_{rid}", use_container_width=True):
                                    try:
                                        _executive_decision(rid,"Reject",rev_note,reviewer)
                                        st.warning("❌ Rejected.")
                                        st.rerun()
                                    except Exception as ex: st.error(str(ex))
                            with bc3:
                                if st.button("🗑️ Delete", key=f"del_{rid}", use_container_width=True):
                                    try:
                                        _delete_request(rid); st.rerun()
                                    except Exception as ex: st.error(str(ex))
                        else:
                            st.markdown(
                                f"<div style='color:#6b7280;font-size:13px;margin-top:8px'>"
                                f"This request is <strong>{status}</strong>."
                                + (f" Reviewed by: {r.get('reviewer','–')}" if r.get("reviewer") else "")
                                + "</div>",
                                unsafe_allow_html=True,
                            )
                            if r.get("reviewer_note"):
                                st.markdown(
                                    f"<div style='background:#f0fdf4;border-left:4px solid #059669;"
                                    f"border-radius:8px;padding:10px 14px;font-size:13px;margin-top:6px'>"
                                    f"💬 {r['reviewer_note']}</div>",
                                    unsafe_allow_html=True,
                                )
                            if st.button("🗑️ Delete", key=f"del2_{rid}"):
                                try:
                                    _delete_request(rid); st.rerun()
                                except Exception as ex: st.error(str(ex))

        with st.expander("📄 Required Supabase Table SQL (run once if not done)"):
            st.code("""
CREATE TABLE IF NOT EXISTS approval_requests (
    id            BIGSERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    requester     TEXT NOT NULL,
    department    TEXT NOT NULL,
    request_type  TEXT NOT NULL,
    description   TEXT NOT NULL,
    priority      TEXT NOT NULL DEFAULT 'Medium',
    stage         TEXT NOT NULL DEFAULT 'Submitted',
    status        TEXT NOT NULL DEFAULT 'Pending',
    reviewer      TEXT,
    reviewer_note TEXT,
    stage_results TEXT,
    risk_level    TEXT DEFAULT 'Low',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE approval_requests DISABLE ROW LEVEL SECURITY;
            """, language="sql")
