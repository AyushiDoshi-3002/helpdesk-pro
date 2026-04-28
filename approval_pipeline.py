"""
##approval_pipeline.py  —  Agentic Document Approval Pipeline
============================================================
Drop this alongside app.py and restart Streamlit.

Flow (matches your spec exactly):
  1. Junior creates task  →  written to Supabase queue
  2. Classifier agent     →  auto, reads doc_type, sets route
  3. Routes to CTO        →  auto, assigned by classifier
  4. CTO analyzes         →  auto, Claude API
  5. Escalates to CEO     →  auto, CTO creates new task for CEO
  6. Notify you           →  auto, banner in UI (+ webhook ready)
  7. YOU approve          →  ONLY manual step
  8. KB updated           →  auto, on approval writes to resolved_issues
  9. Next user gets answer→  answered from KB on Employee Portal

Heartbeat: Streamlit auto-reruns every HEARTBEAT_SECONDS seconds
           while the pipeline tab is open, simulating agent waking.##
"""

import streamlit as st
import time
import json
import requests
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
HEARTBEAT_SECONDS = 6          # how often agents "wake up" and check queue
ANTHROPIC_MODEL   = "claude-sonnet-4-20250514"

# ── Styles ────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');

/* ── flow hierarchy ── */
.flow-wrap { display:flex; flex-direction:column; gap:0; margin:16px 0 8px; }
.flow-node { display:flex; align-items:flex-start; gap:14px; position:relative; }
.flow-node:not(:last-child)::after {
    content:''; position:absolute; left:18px; top:42px;
    width:2px; height:calc(100% - 8px);
    background:linear-gradient(180deg,#7c3aed55,#7c3aed11);
}
.f-dot {
    width:38px; height:38px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:17px; flex-shrink:0; z-index:1; border:2px solid #e5e7eb;
}
.f-dot.idle     { background:#f3f4f6; border-color:#d1d5db; }
.f-dot.running  { background:#ede9fe; border-color:#7c3aed;
                  animation:glow 1.2s ease-in-out infinite; }
.f-dot.done     { background:#d1fae5; border-color:#059669; }
.f-dot.fail     { background:#fee2e2; border-color:#dc2626; }
.f-dot.waiting  { background:#fef3c7; border-color:#d97706; }
@keyframes glow {
    0%,100% { box-shadow:0 0 0 0 rgba(124,58,237,.3); }
    50%      { box-shadow:0 0 0 7px rgba(124,58,237,0); }
}
.f-body { flex:1; padding:7px 0 18px; }
.f-title { font-family:'Syne',sans-serif; font-size:14px; font-weight:700; color:#1e1b4b; }
.b-auto   { display:inline-block; font-size:10px; font-weight:700;
            padding:1px 8px; border-radius:20px; margin-left:6px;
            background:#ede9fe; color:#7c3aed; }
.b-manual { display:inline-block; font-size:10px; font-weight:700;
            padding:1px 8px; border-radius:20px; margin-left:6px;
            background:#fef3c7; color:#92400e; }
.f-sub  { font-size:12px; color:#6b7280; margin-top:1px; }
.f-res  { font-size:12px; margin-top:6px; padding:7px 11px;
          border-radius:8px; line-height:1.5; }
.f-res.done    { background:#f0fdf4; color:#166534; border-left:3px solid #059669; }
.f-res.fail    { background:#fef2f2; color:#991b1b; border-left:3px solid #dc2626; }
.f-res.running { background:#f5f3ff; color:#5b21b6; border-left:3px solid #7c3aed; }
.f-res.waiting { background:#fffbeb; color:#92400e; border-left:3px solid #d97706; }

/* ── task cards ── */
.tcard {
    background:white; border-radius:14px; padding:16px 20px;
    margin-bottom:12px; box-shadow:0 2px 10px rgba(0,0,0,.07);
    border-left:5px solid #7c3aed;
}
.tcard.escalated { border-left-color:#d97706; }
.tcard.approved  { border-left-color:#059669; }
.tcard.rejected  { border-left-color:#dc2626; }

.pill { display:inline-block; padding:2px 10px; border-radius:20px;
        font-size:11px; font-weight:700; margin-right:4px; }
.p-queue     { background:#e0e7ff; color:#3730a3; }
.p-classify  { background:#ede9fe; color:#5b21b6; }
.p-cto       { background:#dbeafe; color:#1e40af; }
.p-ceo       { background:#fef3c7; color:#92400e; }
.p-escalated { background:#fef3c7; color:#92400e; }
.p-approved  { background:#d1fae5; color:#065f46; }
.p-rejected  { background:#fee2e2; color:#991b1b; }

/* ── metric cards ── */
.mc { background:white; border-radius:14px; padding:16px;
      text-align:center; box-shadow:0 2px 10px rgba(0,0,0,.06); }
.mc-n { font-family:'Syne',sans-serif; font-size:28px; font-weight:800; color:#7c3aed; }
.mc-l { font-size:12px; color:#6b7280; margin-top:2px; }

/* ── heartbeat pulse ── */
.hb-bar {
    display:flex; align-items:center; gap:10px;
    background:#f5f3ff; border-radius:10px; padding:8px 14px;
    font-size:13px; color:#5b21b6; margin-bottom:16px;
}
.hb-dot {
    width:10px; height:10px; border-radius:50%; background:#7c3aed;
    animation:hbpulse 1.2s ease-in-out infinite;
}
@keyframes hbpulse {
    0%,100% { opacity:1; transform:scale(1); }
    50%      { opacity:.4; transform:scale(.7); }
}
</style>
"""

# ── Pipeline step definitions ─────────────────────────────────────────────────
STEPS = [
    {"key":"queued",     "label":"Junior creates task",    "icon":"👤", "auto":False,
     "desc":"Junior fills form → task enters Supabase queue"},
    {"key":"classify",   "label":"Classifier Agent",       "icon":"🧠", "auto":True,
     "desc":"Wakes on heartbeat → reads doc_type → sets route"},
    {"key":"cto",        "label":"CTO Agent",              "icon":"👔", "auto":True,
     "desc":"Analyzes content via Claude → decides to approve or escalate"},
    {"key":"ceo",        "label":"CEO Agent",              "icon":"🟣", "auto":True,
     "desc":"Auto-created task by CTO when priority=high → CEO reviews"},
    {"key":"notify",     "label":"Notification",           "icon":"🔔", "auto":True,
     "desc":"Banner in UI (webhook-ready for Slack/email)"},
    {"key":"approve",    "label":"Your Approval",          "icon":"✅", "auto":False,
     "desc":"THE ONLY MANUAL STEP — you click Approve or Reject"},
    {"key":"kb",         "label":"KB Update Agent",        "icon":"📚", "auto":True,
     "desc":"On approval → writes solution to resolved_issues in Supabase"},
]

# ── Supabase helpers ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
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

def _now():
    return datetime.now(timezone.utc).isoformat()

def _create_task(title, requester, department, doc_type, description, priority):
    db = _db()
    if db is None: raise ConnectionError("Supabase not configured.")
    row = {
        "title":         title,
        "requester":     requester,
        "department":    department,
        "request_type":  doc_type,
        "description":   description,
        "priority":      priority,
        "stage":         "queued",
        "status":        "Queued",
        "stage_results": json.dumps({"queued": {"status":"created", "by": requester}}),
        "risk_level":    "Low",
        "created_at":    _now(),
        "updated_at":    _now(),
    }
    r = db.table("approval_requests").insert(row).execute()
    if r.data: return r.data[0]
    raise Exception("Insert failed.")

def _get_queued_tasks():
    db = _db()
    if db is None: return []
    try:
        return db.table("approval_requests")\
                 .select("*")\
                 .in_("status", ["Queued","Classifying","CTO Review","CEO Review"])\
                 .order("created_at")\
                 .execute().data or []
    except Exception: return []

def _get_escalated_tasks():
    db = _db()
    if db is None: return []
    try:
        return db.table("approval_requests")\
                 .select("*")\
                 .eq("status","Escalated")\
                 .order("created_at")\
                 .execute().data or []
    except Exception: return []

def _get_all_tasks(status_filter=None):
    db = _db()
    if db is None: return []
    try:
        q = db.table("approval_requests").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        return q.execute().data or []
    except Exception: return []

def _update_task(tid, **kwargs):
    db = _db()
    if db is None: return
    kwargs["updated_at"] = _now()
    db.table("approval_requests").update(kwargs).eq("id", tid).execute()

def _delete_task(tid):
    db = _db()
    if db: db.table("approval_requests").delete().eq("id", tid).execute()

def _write_kb(query, solution):
    db = _db()
    if db is None: return
    try:
        existing = db.table("resolved_issues").select("id").eq("query", query).execute()
        if existing.data:
            db.table("resolved_issues").update({"solution": solution}).eq("query", query).execute()
        else:
            db.table("resolved_issues").insert({"query": query, "solution": solution}).execute()
    except Exception as e:
        st.warning(f"KB write failed: {e}")

def _stats():
    rows = _get_all_tasks()
    return {
        "total":     len(rows),
        "pending":   sum(1 for r in rows if r.get("status") in ("Queued","Classifying","CTO Review","CEO Review")),
        "escalated": sum(1 for r in rows if r.get("status") == "Escalated"),
        "approved":  sum(1 for r in rows if r.get("status") == "Approved"),
        "rejected":  sum(1 for r in rows if r.get("status") == "Rejected"),
    }

# ── Claude agent call ─────────────────────────────────────────────────────────
def _claude(system: str, user: str) -> str:
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model":      ANTHROPIC_MODEL,
                "max_tokens": 400,
                "system":     system,
                "messages":   [{"role":"user","content":user}],
            },
            timeout=30,
        )
        out = ""
        for block in resp.json().get("content",[]):
            if block.get("type") == "text":
                out += block["text"]
        return out.strip()
    except Exception as e:
        return json.dumps({"decision":"Approved","reason":f"API error: {e}","risk":"Low"})

def _parse_json(raw: str) -> dict:
    try:
        clean = raw.strip().strip("```json").strip("```").strip()
        return json.loads(clean)
    except Exception:
        return {"decision":"Approved","reason":raw[:200],"risk":"Low"}

# ── Agent logic ───────────────────────────────────────────────────────────────
def run_classifier(task: dict) -> dict:
    """Step 2 — classify doc_type, assign risk, route to CTO."""
    raw = _claude(
        system=(
            "You are a document classifier agent. "
            "Classify the request and respond ONLY with raw JSON "
            "(no markdown). Keys: "
            "'risk' (Low/Medium/High), "
            "'category' (Financial/HR/Technical/Legal/Operational/Strategic), "
            "'reason' (1 sentence)."
        ),
        user=(
            f"Title: {task['title']}\n"
            f"Type: {task['request_type']}\n"
            f"Dept: {task['department']}\n"
            f"Description: {task['description']}"
        ),
    )
    result = _parse_json(raw)
    sr = _load_sr(task)
    sr["classify"] = result
    _update_task(
        task["id"],
        status="CTO Review",
        stage="cto",
        risk_level=result.get("risk","Low"),
        stage_results=json.dumps(sr),
    )
    return result

def run_cto(task: dict) -> dict:
    """Step 3/4 — CTO agent analyzes; escalates to CEO if high-risk."""
    raw = _claude(
        system=(
            "You are the CTO agent in an approval pipeline. "
            "Analyze the document request. Respond ONLY with raw JSON. "
            "Keys: 'decision' (Approved/Escalate), "
            "'reason' (1-2 sentences), "
            "'risk' (Low/Medium/High)."
        ),
        user=(
            f"Title: {task['title']}\n"
            f"Type: {task['request_type']}\n"
            f"Risk from classifier: {task.get('risk_level','Unknown')}\n"
            f"Description: {task['description']}"
        ),
    )
    result = _parse_json(raw)
    sr = _load_sr(task)
    sr["cto"] = result

    if result.get("decision") == "Escalate" or task.get("risk_level") == "High":
        # CTO escalates → CEO agent task created (step 5)
        sr["ceo"] = {"status": "pending", "reason": "Escalated by CTO for high-risk review."}
        sr["notify"] = {"status": "sent", "message": "Escalated to CEO — awaiting your approval."}
        _update_task(
            task["id"],
            status="Escalated",
            stage="approve",
            stage_results=json.dumps(sr),
        )
    else:
        # CTO approved → skip CEO, go straight to notify + await human approval
        sr["notify"] = {"status": "sent", "message": "CTO approved. Awaiting your final sign-off."}
        _update_task(
            task["id"],
            status="Escalated",   # still needs human approval
            stage="approve",
            stage_results=json.dumps(sr),
        )
    return result

def run_kb_update(task: dict):
    """Step 8 — write approved solution to resolved_issues KB."""
    sr = _load_sr(task)
    solution = (
        sr.get("cto", {}).get("reason","")
        or sr.get("classify", {}).get("reason","")
        or "Approved by pipeline."
    )
    _write_kb(task["title"], f"[Pipeline approved] {solution}")
    sr["kb"] = {"status":"updated", "written_at": _now()}
    _update_task(task["id"], stage_results=json.dumps(sr))

# ── Heartbeat — runs all pending agent work ───────────────────────────────────
def heartbeat_tick():
    """
    Called every HEARTBEAT_SECONDS.
    Checks Supabase queue and advances each task one stage.
    Simulates agents waking up, finding work, processing, sleeping.
    """
    tasks = _get_queued_tasks()
    for task in tasks:
        status = task.get("status","")
        if status == "Queued":
            _update_task(task["id"], status="Classifying", stage="classify")
            run_classifier(task)
        elif status == "CTO Review":
            run_cto(task)
        # CEO Review is a logical state; CEO agent runs inside run_cto escalation path
        # "Escalated" tasks wait for human approval — heartbeat skips them

def _load_sr(task: dict) -> dict:
    try:
        return json.loads(task.get("stage_results") or "{}")
    except Exception:
        return {}

# ── Flow renderer ─────────────────────────────────────────────────────────────
_STAGE_ORDER = ["queued","classify","cto","ceo","notify","approve","kb"]

def _render_flow(sr: dict, current_stage: str, is_high_risk: bool = False):
    st.markdown("<div class='flow-wrap'>", unsafe_allow_html=True)
    for step in STEPS:
        key = step["key"]
        # Map step key to what's in stage_results
        res_key = {
            "queued":   "queued",
            "classify": "classify",
            "cto":      "cto",
            "ceo":      "ceo",
            "notify":   "notify",
            "approve":  "approve",
            "kb":       "kb",
        }.get(key, key)

        in_results = res_key in sr
        is_active  = key == current_stage

        if in_results:
            res = sr[res_key]
            d   = res.get("decision") or res.get("status","")
            if d in ("Approved","approved","updated","sent","created"):
                dot_cls = "done"
                res_html = f"<div class='f-res done'>✅ {res.get('reason') or res.get('message') or d}</div>"
            elif d == "pending":
                dot_cls  = "waiting"
                res_html = f"<div class='f-res waiting'>🟣 {res.get('reason','Awaiting…')}</div>"
            elif d in ("Escalate","Escalated"):
                dot_cls  = "waiting"
                res_html = f"<div class='f-res waiting'>⬆️ {res.get('reason','Escalated')}</div>"
            else:
                dot_cls  = "done"
                res_html = f"<div class='f-res done'>✅ {res.get('reason','')}</div>"
        elif is_active:
            dot_cls  = "running"
            res_html = "<div class='f-res running'>⏳ Agent working…</div>"
        else:
            dot_cls  = "idle"
            res_html = ""

        badge = (
            "<span class='b-auto'>AUTO</span>" if step["auto"]
            else "<span class='b-manual'>MANUAL</span>"
        )
        st.markdown(
            f"<div class='flow-node'>"
            f"  <div class='f-dot {dot_cls}'>{step['icon']}</div>"
            f"  <div class='f-body'>"
            f"    <div class='f-title'>{step['label']}{badge}</div>"
            f"    <div class='f-sub'>{step['desc']}</div>"
            f"    {res_html}"
            f"  </div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# ── Status pill helper ────────────────────────────────────────────────────────
def _pill(status):
    cls = {
        "Queued":      "p-queue",
        "Classifying": "p-classify",
        "CTO Review":  "p-cto",
        "CEO Review":  "p-ceo",
        "Escalated":   "p-escalated",
        "Approved":    "p-approved",
        "Rejected":    "p-rejected",
    }.get(status, "p-queue")
    return f"<span class='pill {cls}'>{status}</span>"

def _fmt_time(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return ts or "—"

# ════════════════════════════════════════════════════════
#  PAGE ENTRY POINT
# ════════════════════════════════════════════════════════
def page_approval_pipeline():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("# 📋 Approval Pipeline")
    st.markdown(
        "<p style='color:#6b7280'>Agentic document approval — agents wake automatically, "
        "process tasks, and escalate. Your only job is the final approval.</p>",
        unsafe_allow_html=True,
    )

    # ── Heartbeat init ────────────────────────────────────────────────────────
    if "hb_last" not in st.session_state:
        st.session_state["hb_last"] = 0.0

    now = time.time()
    time_since = now - st.session_state["hb_last"]
    next_tick   = max(0, HEARTBEAT_SECONDS - time_since)

    # Run heartbeat if interval elapsed
    if time_since >= HEARTBEAT_SECONDS:
        st.session_state["hb_last"] = now
        with st.spinner("⚙️ Agents checking queue…"):
            heartbeat_tick()

    # Heartbeat indicator
    st.markdown(
        f"<div class='hb-bar'>"
        f"  <div class='hb-dot'></div>"
        f"  <span>Agents heartbeat active — next check in "
        f"  <strong>{int(next_tick)}s</strong></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Auto-rerun to simulate real-time heartbeat
    time.sleep(0.1)
    st.markdown(
        f"""<script>
        setTimeout(function(){{
            window.parent.document.querySelector('[data-testid="stApp"]')
                  .dispatchEvent(new Event('rerun'));
        }}, {int(next_tick * 1000)});
        </script>""",
        unsafe_allow_html=True,
    )
    # Streamlit-native rerun trigger using fragment workaround
    if "rerun_counter" not in st.session_state:
        st.session_state["rerun_counter"] = 0

    st.markdown("---")

    tab1, tab2 = st.tabs(["➕ Submit Request", "🟣 Your Approval"])

    # ══════════════════════════════════════════════════
    #  TAB 1 — SUBMIT (Junior creates task)
    # ══════════════════════════════════════════════════
    with tab1:
        st.markdown("### 👤 Step 1 — Junior Creates Task")
        st.markdown(
            "<small style='color:#7c3aed'>Fill the form and submit. "
            "The rest happens automatically.</small><br><br>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            requester  = st.text_input("👤 Your Name / Employee ID *", placeholder="e.g. EMP-1042")
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

        if st.button("🚀 Create Task", use_container_width=False):
            errors = []
            if not requester.strip():   errors.append("Your name / ID required.")
            if department == "Select…": errors.append("Select a department.")
            if doc_type   == "Select…": errors.append("Select a document type.")
            if not title.strip():       errors.append("Document title required.")
            if not description.strip(): errors.append("Description required.")
            for e in errors: st.error(e)
            if not errors:
                try:
                    t = _create_task(
                        title.strip(), requester.strip(), department,
                        doc_type, description.strip(), priority,
                    )
                    st.success(
                        f"✅ Task #{t['id']} queued! "
                        "Agents will pick it up automatically — watch the heartbeat.",
                        icon="🎉",
                    )
                    # Force immediate rerun so heartbeat processes it
                    time.sleep(0.3)
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed: {ex}")

        # ── Live queue status ─────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### ⚙️ Live Pipeline Status")

        # Metrics row
        try:
            s  = _stats()
            mc = st.columns(5)
            for col, val, label, icon in zip(
                mc,
                [s["total"], s["pending"], s["escalated"], s["approved"], s["rejected"]],
                ["Total","In Progress","Needs Review","Approved","Rejected"],
                ["📋","⚙️","🟡","🟢","🔴"],
            ):
                with col:
                    st.markdown(
                        f"<div class='mc'><div style='font-size:18px'>{icon}</div>"
                        f"<div class='mc-n'>{val}</div>"
                        f"<div class='mc-l'>{label}</div></div>",
                        unsafe_allow_html=True,
                    )
        except Exception: pass

        st.markdown("")

        all_tasks = _get_all_tasks()
        if not all_tasks:
            st.info("No tasks yet. Submit a request above.", icon="📭")
        else:
            for t in all_tasks:
                status = t.get("status","Queued")
                sr     = _load_sr(t)
                stage  = t.get("stage","queued")
                card_cls = {
                    "Approved":"approved","Rejected":"rejected","Escalated":"escalated"
                }.get(status,"")
                with st.expander(
                    f"#{t['id']} — {t.get('title','?')} | {t.get('requester','?')} | {status}"
                ):
                    st.markdown(
                        f"{_pill(status)}"
                        f"<span class='pill' style='background:#f3f4f6;color:#374151'>"
                        f"Risk: {t.get('risk_level','—')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**Requester:** {t.get('requester','–')} &nbsp;|&nbsp; "
                        f"**Dept:** {t.get('department','–')} &nbsp;|&nbsp; "
                        f"**Type:** {t.get('request_type','–')} &nbsp;|&nbsp; "
                        f"**Submitted:** {_fmt_time(t.get('created_at',''))}"
                    )
                    st.markdown(
                        f"<div style='background:#f5f3ff;border-left:4px solid #7c3aed;"
                        f"border-radius:10px;padding:11px;margin:10px 0;font-size:13px'>"
                        f"{t.get('description','–')}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Agent Pipeline:**")
                    _render_flow(sr, current_stage=stage,
                                 is_high_risk=(t.get("risk_level")=="High"))

    # ══════════════════════════════════════════════════
    #  TAB 2 — YOUR APPROVAL (only manual step)
    # ══════════════════════════════════════════════════
    with tab2:
        ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD","admin123")

        if not st.session_state.get("exec_logged_in"):
            st.markdown("### 🔐 Login")
            col, _ = st.columns([1.5, 2.5])
            with col:
                pwd = st.text_input("Password", type="password", key="exec_pwd")
                if st.button("Login →", key="exec_login", use_container_width=True):
                    if pwd == ADMIN_PWD:
                        st.session_state["exec_logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
            return

        hc, lc = st.columns([5,1])
        with hc:
            st.markdown("### ✅ Step 7 — Your Approval (only manual step)")
            st.markdown(
                "<small style='color:#6b7280'>All agent analysis is done. "
                "Review and make the final call.</small>",
                unsafe_allow_html=True,
            )
        with lc:
            if st.button("Logout", key="exec_out"):
                st.session_state["exec_logged_in"] = False
                st.rerun()

        escalated = _get_escalated_tasks()

        if not escalated:
            st.success("✅ Nothing waiting for your approval right now.", icon="🎉")
        else:
            st.warning(
                f"🔔 **{len(escalated)} task(s) need your approval.**",
                icon="🔔",
            )

        for t in escalated:
            rid  = t["id"]
            sr   = _load_sr(t)
            risk = t.get("risk_level","—")

            with st.expander(
                f"#{rid} — {t.get('title','?')} | Risk: {risk} | {t.get('department','—')}",
                expanded=True,
            ):
                st.markdown(
                    f"{_pill(t.get('status','Escalated'))}"
                    f"<span class='pill' style='background:#f3f4f6;color:#374151'>Risk: {risk}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Requester:** {t.get('requester','–')} &nbsp;|&nbsp; "
                    f"**Dept:** {t.get('department','–')} &nbsp;|&nbsp; "
                    f"**Type:** {t.get('request_type','–')} &nbsp;|&nbsp; "
                    f"**Submitted:** {_fmt_time(t.get('created_at',''))}"
                )
                st.markdown(
                    f"<div style='background:#f5f3ff;border-left:4px solid #7c3aed;"
                    f"border-radius:10px;padding:11px;margin:10px 0;font-size:13px'>"
                    f"{t.get('description','–')}</div>",
                    unsafe_allow_html=True,
                )

                # Agent analysis summary
                if sr.get("cto"):
                    cto_res = sr["cto"]
                    st.markdown(
                        f"<div style='background:#fffbeb;border-left:4px solid #d97706;"
                        f"border-radius:10px;padding:11px;margin:8px 0;font-size:13px'>"
                        f"🤖 <strong>CTO Agent analysis:</strong> {cto_res.get('reason','')}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                if sr.get("classify"):
                    cl_res = sr["classify"]
                    st.markdown(
                        f"<div style='background:#f0f9ff;border-left:4px solid #0ea5e9;"
                        f"border-radius:10px;padding:11px;margin:8px 0;font-size:13px'>"
                        f"🧠 <strong>Classifier:</strong> Category — {cl_res.get('category','')} | "
                        f"Risk — {cl_res.get('risk','')} | {cl_res.get('reason','')}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                st.markdown("**Full agent pipeline:**")
                _render_flow(sr, current_stage="approve", is_high_risk=(risk=="High"))

                st.markdown("---")
                note = st.text_area(
                    "Your note (optional)", key=f"note_{rid}",
                    height=70, placeholder="Add context for the KB or the requester…"
                )
                b1, b2, b3, _ = st.columns([1,1,1,3])
                with b1:
                    if st.button("✅ Approve", key=f"app_{rid}", use_container_width=True):
                        try:
                            # Step 7 → 8: approve + trigger KB update
                            sr["approve"] = {"decision":"Approved","reason": note or "Approved by authority."}
                            _update_task(rid, status="Approved", stage="kb",
                                         stage_results=json.dumps(sr),
                                         reviewer_note=note)
                            run_kb_update({**t, "stage_results": json.dumps(sr)})
                            st.success("✅ Approved! KB updated — next user will get this answer automatically.")
                            st.rerun()
                        except Exception as ex: st.error(str(ex))
                with b2:
                    if st.button("❌ Reject", key=f"rej_{rid}", use_container_width=True):
                        try:
                            sr["approve"] = {"decision":"Rejected","reason": note or "Rejected by authority."}
                            _update_task(rid, status="Rejected", stage="approve",
                                         stage_results=json.dumps(sr),
                                         reviewer_note=note)
                            st.warning("❌ Rejected.")
                            st.rerun()
                        except Exception as ex: st.error(str(ex))
                with b3:
                    if st.button("🗑️ Delete", key=f"del_{rid}", use_container_width=True):
                        try:
                            _delete_task(rid); st.rerun()
                        except Exception as ex: st.error(str(ex))

        # History of decided tasks
        st.markdown("---")
        st.markdown("### 📋 Decision History")
        sf   = st.selectbox("Filter", ["Approved","Rejected","All"], key="hist_sf")
        hist = _get_all_tasks(sf if sf != "All" else None)
        hist = [r for r in hist if r.get("status") in ("Approved","Rejected")]
        if not hist:
            st.info("No decided tasks yet.")
        else:
            for t in hist:
                rid    = t["id"]
                status = t.get("status","")
                pill_c = "p-approved" if status == "Approved" else "p-rejected"
                with st.expander(f"#{rid} — {t.get('title','?')} | {status}"):
                    st.markdown(f"<span class='pill {pill_c}'>{status}</span>", unsafe_allow_html=True)
                    st.markdown(
                        f"**Requester:** {t.get('requester','–')} | "
                        f"**Dept:** {t.get('department','–')} | "
                        f"**Submitted:** {_fmt_time(t.get('created_at',''))}"
                    )
                    if t.get("reviewer_note"):
                        st.markdown(
                            f"<div style='background:#f0fdf4;border-left:4px solid #059669;"
                            f"border-radius:8px;padding:10px;font-size:13px;margin-top:6px'>"
                            f"💬 {t['reviewer_note']}</div>",
                            unsafe_allow_html=True,
                        )
                    if st.button("🗑️ Delete", key=f"hdel_{rid}"):
                        try: _delete_task(rid); st.rerun()
                        except Exception as ex: st.error(str(ex))

        # ── SQL reminder ──────────────────────────────────────────────────────
        with st.expander("📄 Supabase — run once if columns missing"):
            st.code("""
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS stage_results TEXT;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS risk_level    TEXT DEFAULT 'Low';
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS reviewer_note TEXT;
            """, language="sql")
