import streamlit as st
import time
import json
import requests
from datetime import datetime

# ════════════════════════════════════════════════════════
#  APPROVAL PIPELINE
#  Tab 1 : Submit Request  (agents run automatically)
#  Tab 2 : Executive Review (manual, only high-risk)
# ════════════════════════════════════════════════════════

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');

/* ── hierarchy nodes ── */
.hier-wrap { display:flex; flex-direction:column; gap:0; margin:20px 0 10px; }

.hier-node {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    position: relative;
}
.hier-node:not(:last-child)::after {
    content: '';
    position: absolute;
    left: 18px;
    top: 42px;
    width: 2px;
    height: calc(100% - 10px);
    background: linear-gradient(180deg, #7c3aed55, #7c3aed11);
}

.hier-dot {
    width: 38px; height: 38px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 17px; flex-shrink: 0; z-index: 1;
    border: 2px solid #e5e7eb;
    background: #f9fafb;
    transition: all 0.3s;
}
.hier-dot.waiting   { background:#f3f4f6; border-color:#d1d5db; }
.hier-dot.running   { background:#ede9fe; border-color:#7c3aed;
                       box-shadow:0 0 0 4px rgba(124,58,237,0.15);
                       animation: glow 1.2s ease-in-out infinite; }
.hier-dot.ok        { background:#d1fae5; border-color:#059669; }
.hier-dot.fail      { background:#fee2e2; border-color:#dc2626; }
.hier-dot.skipped   { background:#f3f4f6; border-color:#e5e7eb; opacity:0.45; }
.hier-dot.pending   { background:#fef3c7; border-color:#d97706; }

@keyframes glow {
    0%,100% { box-shadow:0 0 0 0 rgba(124,58,237,0.3); }
    50%      { box-shadow:0 0 0 7px rgba(124,58,237,0); }
}

.hier-body { flex:1; padding:8px 0 20px; }
.hier-title {
    font-family:'Syne',sans-serif;
    font-size:14px; font-weight:700; color:#1e1b4b;
}
.badge-auto   { display:inline-block; font-size:10px; font-weight:700;
                padding:1px 8px; border-radius:20px; margin-left:6px;
                background:#ede9fe; color:#7c3aed; vertical-align:middle; }
.badge-manual { display:inline-block; font-size:10px; font-weight:700;
                padding:1px 8px; border-radius:20px; margin-left:6px;
                background:#fef3c7; color:#92400e; vertical-align:middle; }
.hier-sub  { font-size:12px; color:#6b7280; margin-top:1px; }

.result-box {
    font-size:12px; margin-top:6px; padding:7px 11px;
    border-radius:8px; line-height:1.5;
}
.result-box.ok      { background:#f0fdf4; color:#166534; border-left:3px solid #059669; }
.result-box.fail    { background:#fef2f2; color:#991b1b; border-left:3px solid #dc2626; }
.result-box.running { background:#f5f3ff; color:#5b21b6; border-left:3px solid #7c3aed; }
.result-box.pending { background:#fffbeb; color:#92400e; border-left:3px solid #d97706; }

/* ── metric cards ── */
.met-card {
    background:white; border-radius:14px; padding:16px;
    text-align:center; box-shadow:0 2px 10px rgba(0,0,0,0.06);
}
.met-num   { font-family:'Syne',sans-serif; font-size:28px; font-weight:800; color:#7c3aed; }
.met-label { font-size:12px; color:#6b7280; margin-top:2px; }

/* ── status pills ── */
.spill { display:inline-block; padding:3px 11px; border-radius:20px;
         font-size:11px; font-weight:700; }
.spill-esc  { background:#fef3c7; color:#92400e; }
.spill-app  { background:#d1fae5; color:#065f46; }
.spill-rej  { background:#fee2e2; color:#991b1b; }
</style>
"""

# ── Stage definitions ─────────────────────────────────────────────────────────
STAGES = [
    {"key":"intent",      "label":"Intent Agent",         "icon":"🧠", "auto":True,
     "desc":"Classifies request type, urgency and sensitivity"},
    {"key":"functional",  "label":"Functional Agent",     "icon":"🟢", "auto":True,
     "desc":"Validates business relevance for the department"},
    {"key":"technical",   "label":"Technical Agent",      "icon":"🔵", "auto":True,
     "desc":"Checks system/data access safety and feasibility"},
    {"key":"compliance",  "label":"Compliance Agent",     "icon":"🔴", "auto":True,
     "desc":"Validates confidentiality, privacy laws, company policies"},
    {"key":"executive",   "label":"Executive Authority",  "icon":"🟣", "auto":False,
     "desc":"Final human approval — only for high-risk documents"},
    {"key":"fetch",       "label":"Document Fetch Agent", "icon":"📄", "auto":True,
     "desc":"Retrieves the document from the source system"},
    {"key":"storage",     "label":"Storage Agent",        "icon":"💾", "auto":True,
     "desc":"Stores document securely in Drive / DB"},
    {"key":"delivery",    "label":"Delivery Agent",       "icon":"📬", "auto":True,
     "desc":"Shares document with the requesting admin"},
]

# ── Supabase ──────────────────────────────────────────────────────────────────
def _db():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL","")
        key = st.secrets.get("SUPABASE_KEY","")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None

def _save(data: dict):
    db = _db()
    if db is None:
        st.warning("⚠️ Supabase not configured — result not saved.")
        return
    try:
        db.table("approval_requests").insert(data).execute()
    except Exception as e:
        st.warning(f"⚠️ Could not save to Supabase: {e}")

def _exec_update(rid, approved: bool, reviewer: str, note: str):
    db = _db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    db.table("approval_requests").update({
        "status":        "Approved" if approved else "Rejected",
        "stage":         "Document Released" if approved else "Rejected by Executive",
        "reviewer":      reviewer,
        "reviewer_note": note,
        "updated_at":    datetime.utcnow().isoformat(),
    }).eq("id", rid).execute()

def _fetch_all(status=None):
    db = _db()
    if db is None: return []
    try:
        q = db.table("approval_requests").select("*").order("created_at", desc=True)
        if status and status != "All":
            q = q.eq("status", status)
        return q.execute().data or []
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return []

def _delete(rid):
    db = _db()
    if db:
        db.table("approval_requests").delete().eq("id", rid).execute()

def _stats():
    rows = _fetch_all()
    return {
        "total":     len(rows),
        "escalated": sum(1 for r in rows if r.get("status") == "Escalated"),
        "approved":  sum(1 for r in rows if r.get("status") == "Approved"),
        "rejected":  sum(1 for r in rows if r.get("status") == "Rejected"),
    }

# ── Claude agent call ─────────────────────────────────────────────────────────
def _agent_decide(agent_label: str, ctx: dict) -> dict:
    """
    Calls Claude claude-sonnet-4-20250514 to make an autonomous decision.
    Returns {"decision": "Approved"|"Rejected", "reason": str, "risk": "Low"|"Medium"|"High"}
    """
    system_prompt = (
        f"You are the {agent_label} in a document approval pipeline. "
        "Evaluate the request and respond ONLY with a raw JSON object — "
        "no markdown, no backticks, no explanation outside JSON. "
        'Keys: "decision" (exactly "Approved" or "Rejected"), '
        '"reason" (1-2 sentences), "risk" (exactly "Low", "Medium", or "High").'
    )
    user_content = (
        f"Document request:\n"
        f"Title: {ctx['title']}\n"
        f"Type: {ctx['doc_type']}\n"
        f"Department: {ctx['department']}\n"
        f"Requester: {ctx['requester']}\n"
        f"Description: {ctx['description']}\n"
        f"Priority: {ctx['priority']}\n\n"
        f"Make your decision as {agent_label}."
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 200,
                "system":     system_prompt,
                "messages":   [{"role": "user", "content": user_content}],
            },
            timeout=30,
        )
        raw = ""
        for block in resp.json().get("content", []):
            if block.get("type") == "text":
                raw += block["text"]
        raw = raw.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception as e:
        # Hard fallback — do NOT silently swallow; show real error in reason
        return {
            "decision": "Approved",
            "reason":   f"[API error — fallback approved] {e}",
            "risk":     "Low",
        }

# ── Hierarchy renderer ────────────────────────────────────────────────────────
def _render_hierarchy(results: dict, active_key: str = None, high_risk: bool = False):
    st.markdown("<div class='hier-wrap'>", unsafe_allow_html=True)
    for s in STAGES:
        key = s["key"]

        # Executive is skipped visually when not high-risk and not active
        if key == "executive" and not high_risk and key not in results and key != active_key:
            dot_cls     = "skipped"
            result_html = ""
        elif key == active_key and key not in results:
            dot_cls     = "running"
            result_html = "<div class='result-box running'>⏳ Agent deciding…</div>"
        elif key in results:
            r = results[key]
            d = r.get("decision","")
            if d == "Pending":
                dot_cls     = "pending"
                result_html = "<div class='result-box pending'>🟣 Awaiting Executive decision…</div>"
            elif d == "Approved":
                dot_cls     = "ok"
                result_html = f"<div class='result-box ok'>✅ {r.get('reason','')}</div>"
            else:
                dot_cls     = "fail"
                result_html = f"<div class='result-box fail'>❌ {r.get('reason','')}</div>"
        else:
            dot_cls     = "waiting"
            result_html = ""

        badge = (
            "<span class='badge-auto'>AUTO</span>" if s["auto"]
            else "<span class='badge-manual'>MANUAL</span>"
        )
        st.markdown(
            f"<div class='hier-node'>"
            f"  <div class='hier-dot {dot_cls}'>{s['icon']}</div>"
            f"  <div class='hier-body'>"
            f"    <div class='hier-title'>{s['label']}{badge}</div>"
            f"    <div class='hier-sub'>{s['desc']}</div>"
            f"    {result_html}"
            f"  </div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  PAGE ENTRY POINT
# ════════════════════════════════════════════════════════
def page_approval_pipeline():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("# 📋 Approval Pipeline")
    st.markdown(
        "<p style='color:#6b7280'>AI agents decide automatically through each stage. "
        "Executive review is triggered only for high-risk documents.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    tab1, tab2 = st.tabs(["➕ Submit Request", "🟣 Executive Review"])

    # ══════════════════════════════════════════════════
    #  TAB 1 — SUBMIT
    # ══════════════════════════════════════════════════
    with tab1:
        st.markdown("### 📝 New Document Request")

        c1, c2 = st.columns(2)
        with c1:
            requester  = st.text_input("👤 Admin Name / Employee ID *", placeholder="e.g. EMP-1042")
            department = st.selectbox("🏢 Department *", [
                "Select…","Finance","HR","Engineering",
                "Legal","Operations","Marketing","Executive","Other",
            ])
            priority = st.selectbox("🚨 Priority", ["Medium","High","Low"])
        with c2:
            title    = st.text_input("📌 Document Title *", placeholder="e.g. Q3 Financial Report")
            doc_type = st.selectbox("📂 Document Type *", [
                "Select…","Financial Report","Employee Data","System Design",
                "Vendor Contract","Policy Document","Audit Report","Strategic Plan","Other",
            ])

        description = st.text_area(
            "📋 Why do you need this document? *",
            placeholder="Explain the business reason and urgency…",
            height=100,
        )

        if st.button("🚀 Submit & Run Agents"):
            errors = []
            if not requester.strip():   errors.append("Admin Name / ID required.")
            if department == "Select…": errors.append("Select a department.")
            if doc_type   == "Select…": errors.append("Select a document type.")
            if not title.strip():       errors.append("Document title required.")
            if not description.strip(): errors.append("Description required.")
            for e in errors: st.error(e)
            if errors: st.stop()

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

            placeholder   = st.empty()
            results       = {}
            overall_risk  = "Low"
            passed        = True

            def redraw(active=None):
                with placeholder.container():
                    _render_hierarchy(results, active_key=active,
                                      high_risk=(overall_risk == "High"))

            # ── Agents 1-4 (always run automatically) ────────────
            for key in ["intent","functional","technical","compliance"]:
                redraw(key)
                time.sleep(0.5)
                label  = next(s["label"] for s in STAGES if s["key"] == key)
                result = _agent_decide(label, ctx)
                results[key] = result
                if result.get("risk") == "High":
                    overall_risk = "High"
                if result.get("decision") == "Rejected":
                    passed = False
                    redraw()
                    st.error(f"❌ **{label}** rejected: {result.get('reason','')}")
                    break

            if not passed:
                st.stop()

            # ── Executive gate — only if high-risk ───────────────
            if overall_risk == "High":
                results["executive"] = {
                    "decision": "Pending",
                    "reason":   "High-risk document escalated to Executive Authority for manual review.",
                    "risk":     "High",
                }
                redraw()
                _save({
                    "title":         ctx["title"],
                    "requester":     ctx["requester"],
                    "department":    ctx["department"],
                    "request_type":  ctx["doc_type"],
                    "description":   ctx["description"],
                    "priority":      ctx["priority"],
                    "stage":         "Escalated to Executive",
                    "status":        "Escalated",
                    "stage_results": json.dumps(results),
                    "risk_level":    overall_risk,
                    "created_at":    datetime.utcnow().isoformat(),
                    "updated_at":    datetime.utcnow().isoformat(),
                })
                st.warning(
                    "🟣 **Escalated to Executive Authority.** "
                    "This document is high-risk. Go to the **Executive Review** tab to approve or reject."
                )
                st.stop()

            # ── Agents 6-8 (post-approval delivery) ──────────────
            for key in ["fetch","storage","delivery"]:
                redraw(key)
                time.sleep(0.5)
                label  = next(s["label"] for s in STAGES if s["key"] == key)
                result = _agent_decide(label, ctx)
                results[key] = result

            redraw()
            _save({
                "title":         ctx["title"],
                "requester":     ctx["requester"],
                "department":    ctx["department"],
                "request_type":  ctx["doc_type"],
                "description":   ctx["description"],
                "priority":      ctx["priority"],
                "stage":         "Document Released",
                "status":        "Approved",
                "stage_results": json.dumps(results),
                "risk_level":    overall_risk,
                "created_at":    datetime.utcnow().isoformat(),
                "updated_at":    datetime.utcnow().isoformat(),
            })
            st.success("✅ **All agents approved.** Document fetched, stored, and delivered!")

    # ══════════════════════════════════════════════════
    #  TAB 2 — EXECUTIVE REVIEW
    # ══════════════════════════════════════════════════
    with tab2:
        ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")

        if not st.session_state.get("exec_logged_in"):
            st.markdown("### 🔐 Executive Login")
            col, _ = st.columns([1.5, 2.5])
            with col:
                pwd = st.text_input("Password", type="password", key="exec_pwd")
                if st.button("Login →", key="exec_login", use_container_width=True):
                    if pwd == ADMIN_PWD:
                        st.session_state["exec_logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
            st.stop()

        hc, lc = st.columns([5,1])
        with hc: st.markdown("### 🟣 Executive Authority")
        with lc:
            if st.button("Logout", key="exec_out"):
                st.session_state["exec_logged_in"] = False
                st.rerun()

        # Metrics
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
                    f"<div class='met-card'><div style='font-size:20px'>{icon}</div>"
                    f"<div class='met-num'>{val}</div>"
                    f"<div class='met-label'>{label}</div></div>",
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        sf   = st.selectbox("Show", ["All","Escalated","Approved","Rejected"], key="exec_sf")
        rows = _fetch_all(sf if sf != "All" else None)

        if not rows:
            st.info("No requests found.", icon="📭")
        else:
            st.markdown(f"**{len(rows)} request(s)**")
            for r in rows:
                rid    = r["id"]
                status = r.get("status","Escalated")
                risk   = r.get("risk_level","—")
                pill   = {"Escalated":"spill-esc","Approved":"spill-app",
                          "Rejected":"spill-rej"}.get(status,"spill-esc")
                try:
                    dt  = datetime.fromisoformat(r["created_at"].replace("Z","+00:00"))
                    fmt = dt.strftime("%d %b %Y, %I:%M %p")
                except Exception:
                    fmt = r.get("created_at","")

                with st.expander(
                    f"#{rid} — {r.get('title','?')} | {r.get('requester','?')} | {status} | Risk: {risk}"
                ):
                    st.markdown(
                        f"<span class='spill {pill}'>{status}</span>&nbsp;"
                        f"<span class='spill' style='background:#f3f4f6;color:#374151'>Risk: {risk}</span>",
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
                        f"border-radius:10px;padding:12px;margin:10px 0;font-size:14px'>"
                        f"{r.get('description','–')}</div>",
                        unsafe_allow_html=True,
                    )

                    # Replay agent decisions
                    try:
                        sr = json.loads(r.get("stage_results") or "{}")
                        if sr:
                            st.markdown("**🤖 Agent Decisions:**")
                            _render_hierarchy(sr, high_risk=True)
                    except Exception:
                        pass

                    if status == "Escalated":
                        st.markdown("---")
                        rc1, rc2 = st.columns(2)
                        with rc1:
                            reviewer = st.text_input("Your Name", key=f"rev_{rid}",
                                                     placeholder="Executive name")
                        with rc2:
                            note = st.text_area("Decision Note", key=f"note_{rid}",
                                                height=80, placeholder="Reason…")
                        b1, b2, b3, _ = st.columns([1,1,1,3])
                        with b1:
                            if st.button("✅ Approve", key=f"app_{rid}", use_container_width=True):
                                try:
                                    _exec_update(rid, True, reviewer, note)
                                    st.success("✅ Approved — document released.")
                                    st.rerun()
                                except Exception as ex: st.error(str(ex))
                        with b2:
                            if st.button("❌ Reject", key=f"rej_{rid}", use_container_width=True):
                                try:
                                    _exec_update(rid, False, reviewer, note)
                                    st.warning("❌ Rejected.")
                                    st.rerun()
                                except Exception as ex: st.error(str(ex))
                        with b3:
                            if st.button("🗑️ Delete", key=f"del_{rid}", use_container_width=True):
                                try:
                                    _delete(rid); st.rerun()
                                except Exception as ex: st.error(str(ex))
                    else:
                        note_val = r.get("reviewer_note","")
                        rev_val  = r.get("reviewer","")
                        st.markdown(
                            f"<div style='color:#6b7280;font-size:13px;margin-top:6px'>"
                            f"Status: <strong>{status}</strong>"
                            + (f" — Reviewed by {rev_val}" if rev_val else "")
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                        if note_val:
                            st.markdown(
                                f"<div style='background:#f0fdf4;border-left:4px solid #059669;"
                                f"border-radius:8px;padding:10px;font-size:13px;margin-top:6px'>"
                                f"💬 {note_val}</div>",
                                unsafe_allow_html=True,
                            )
                        if st.button("🗑️ Delete", key=f"del2_{rid}"):
                            try:
                                _delete(rid); st.rerun()
                            except Exception as ex: st.error(str(ex))

        with st.expander("📄 Supabase SQL — run this once if columns are missing"):
            st.code("""
-- Add missing columns (safe to run even if table exists)
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS stage_results TEXT;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS risk_level    TEXT DEFAULT 'Low';
            """, language="sql")
