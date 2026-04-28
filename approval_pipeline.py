"""
approval_pipeline.py  —  Hierarchical Agentic Approval Pipeline
================================================================

Exact hierarchy:
  Junior Agent    → completes edit, creates "Review edit" task for Senior
  Senior Agent    → reviews, creates "Approve technical change" task for Tech Lead
  Tech Lead Agent → reviews, creates "Final approval" task for CTO (or CEO if security)
  CTO/CEO Agent   → analyzes, if human needed → creates approval request for YOU
  YOU             → only manual step — approve/reject in dashboard
  KB Update       → auto-triggered on approval → writes to resolved_issues

Each agent has a heartbeat — wakes every N seconds, checks its queue,
processes ONE task, sleeps again.
"""

import streamlit as st
import time
import json
import requests
from datetime import datetime, timezone

# ── Config ─────────────────────────────────────────────────────────────────
HEARTBEAT_SEC  = 7
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# ── Agent definitions (in order) ────────────────────────────────────────────
AGENTS = [
    {
        "id":       "junior",
        "label":    "Junior Agent",
        "icon":     "👩‍💻",
        "color":    "#6366f1",
        "bg":       "#eef2ff",
        "manual":   True,   # human fills form
        "creates":  "senior",
        "task_label": "Review edit",
        "desc":     "Completes edit suggestion → creates task for Senior Agent",
    },
    {
        "id":       "senior",
        "label":    "Senior Agent",
        "icon":     "👨‍💼",
        "color":    "#0ea5e9",
        "bg":       "#f0f9ff",
        "manual":   False,
        "creates":  "techlead",
        "task_label": "Approve technical change",
        "desc":     "Reviews edit quality → escalates to Tech Lead",
    },
    {
        "id":       "techlead",
        "label":    "Tech Lead Agent",
        "icon":     "🧑‍🔧",
        "color":    "#8b5cf6",
        "bg":       "#f5f3ff",
        "manual":   False,
        "creates":  "cto",   # or ceo if security
        "task_label": "Final approval",
        "desc":     "Validates technical safety → routes to CTO or CEO",
    },
    {
        "id":       "cto",
        "label":    "CTO / CEO Agent",
        "icon":     "🏛️",
        "color":    "#f59e0b",
        "bg":       "#fffbeb",
        "manual":   False,
        "creates":  "human",
        "task_label": "Human approval required",
        "desc":     "Final AI review → creates approval request for you if needed",
    },
    {
        "id":       "human",
        "label":    "Your Approval",
        "icon":     "✅",
        "color":    "#059669",
        "bg":       "#f0fdf4",
        "manual":   True,   # THE ONLY MANUAL STEP
        "creates":  "kb",
        "task_label": "KB update",
        "desc":     "THE ONLY MANUAL STEP — approve or reject in dashboard",
    },
    {
        "id":       "kb",
        "label":    "KB Update",
        "icon":     "📚",
        "color":    "#10b981",
        "bg":       "#ecfdf5",
        "manual":   False,
        "creates":  None,
        "task_label": None,
        "desc":     "Auto-triggered on approval → writes to resolved_issues KB",
    },
]

AGENT_BY_ID = {a["id"]: a for a in AGENTS}

# ── Status → agent mapping ───────────────────────────────────────────────────
# Each status means "currently waiting for this agent to act"
STATUS_AGENT = {
    "Queued":          "junior",
    "Senior Review":   "senior",
    "TechLead Review": "techlead",
    "CTO Review":      "cto",
    "Awaiting Approval":"human",
    "Approved":        "kb",
    "Rejected":        "kb",
    "Done":            "kb",
}

# ── CSS ──────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');

/* ── hierarchy tree ── */
.hier { display:flex; flex-direction:column; gap:0; margin:20px 0 10px; }

.hnode { display:flex; align-items:flex-start; gap:0; position:relative; }

/* vertical connector line */
.hnode:not(:last-child) .hline-wrap::after {
    content:'';
    position:absolute;
    left: 19px;
    top: 42px;
    width: 2px;
    height: calc(100% - 2px);
    background: linear-gradient(180deg,#94a3b855,#94a3b811);
    z-index:0;
}
.hline-wrap { position:relative; display:flex; flex-direction:column; align-items:center; }

.hdot {
    width: 40px; height: 40px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
    z-index: 1;
    border: 2px solid #e2e8f0;
    background: #f8fafc;
    transition: all .3s;
    margin-top: 2px;
}
.hdot.idle     { background:#f1f5f9; border-color:#cbd5e1; filter:grayscale(.6); }
.hdot.active   { border-width:3px; animation:activeglow 1.4s ease-in-out infinite; }
.hdot.done     { border-width:2px; }
.hdot.fail     { background:#fee2e2 !important; border-color:#dc2626 !important; }
.hdot.waiting  { animation:waitpulse 2s ease-in-out infinite; }

@keyframes activeglow {
    0%,100% { box-shadow: 0 0 0 0 rgba(99,102,241,.4); }
    50%      { box-shadow: 0 0 0 8px rgba(99,102,241,0); }
}
@keyframes waitpulse {
    0%,100% { opacity:1; } 50% { opacity:.55; }
}

/* arrow between dots */
.harrow {
    font-size:13px; color:#94a3b8;
    margin: 3px 0; line-height:1;
    z-index:1;
}

.hbody {
    flex:1; padding: 6px 0 22px 16px;
}
.htitle {
    font-family:'Syne',sans-serif;
    font-size:14px; font-weight:700; color:#0f172a;
    display:flex; align-items:center; gap:8px;
}
.badge-auto   { font-size:9px; font-weight:700; padding:2px 7px;
                border-radius:20px; background:#ede9fe; color:#7c3aed; }
.badge-manual { font-size:9px; font-weight:700; padding:2px 7px;
                border-radius:20px; background:#fef3c7; color:#92400e; }
.badge-active { font-size:9px; font-weight:700; padding:2px 7px;
                border-radius:20px; background:#dcfce7; color:#166534;
                animation:waitpulse 1.5s infinite; }

.hdesc { font-size:12px; color:#64748b; margin-top:2px; }

.hresult {
    font-size:12px; margin-top:7px; padding:8px 12px;
    border-radius:9px; line-height:1.6;
}
.hresult.done    { background:#f0fdf4; color:#166534; border-left:3px solid #059669; }
.hresult.fail    { background:#fef2f2; color:#991b1b; border-left:3px solid #dc2626; }
.hresult.active  { background:#f5f3ff; color:#4c1d95; border-left:3px solid #7c3aed; }
.hresult.waiting { background:#fffbeb; color:#92400e; border-left:3px solid #d97706; }

/* task chain pill */
.creates-arrow {
    font-size:11px; color:#94a3b8; margin:4px 0 0 0;
    display:flex; align-items:center; gap:5px;
}
.creates-pill {
    display:inline-block; font-size:10px; font-weight:600;
    padding:2px 9px; border-radius:20px;
    background:#f1f5f9; color:#475569; border:1px solid #e2e8f0;
}

/* ── metric cards ── */
.mc { background:white; border-radius:12px; padding:14px;
      text-align:center; box-shadow:0 2px 8px rgba(0,0,0,.06); }
.mc-n { font-family:'Syne',sans-serif; font-size:26px; font-weight:800; color:#6366f1; }
.mc-l { font-size:11px; color:#6b7280; margin-top:2px; }

/* ── status pills ── */
.spill { display:inline-block; padding:2px 10px; border-radius:20px;
         font-size:11px; font-weight:700; margin-right:4px; }

/* ── heartbeat bar ── */
.hbbar {
    display:flex; align-items:center; gap:10px;
    background:#f5f3ff; border-radius:10px; padding:8px 14px;
    font-size:13px; color:#4c1d95; margin-bottom:16px;
    border: 1px solid #ede9fe;
}
.hbdot {
    width:9px; height:9px; border-radius:50%; background:#7c3aed;
    animation:hbp 1.4s ease-in-out infinite;
}
@keyframes hbp {
    0%,100% { opacity:1; transform:scale(1.1); }
    50%      { opacity:.3; transform:scale(.7); }
}

/* ── task card ── */
.tcard {
    background:white; border-radius:14px; padding:18px 22px;
    margin-bottom:12px; box-shadow:0 2px 10px rgba(0,0,0,.07);
    border-left:5px solid #6366f1;
}
.tcard.done     { border-left-color:#059669; }
.tcard.rejected { border-left-color:#dc2626; }
.tcard.waiting  { border-left-color:#f59e0b; }
</style>
"""

# ── Supabase ─────────────────────────────────────────────────────────────────
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

def _load_sr(task):
    try: return json.loads(task.get("stage_results") or "{}")
    except: return {}

def _create_task(title, requester, dept, doc_type, desc, priority):
    db = _db()
    if db is None: raise ConnectionError("Supabase not configured.")
    row = {
        "title":         title,
        "requester":     requester,
        "department":    dept,
        "request_type":  doc_type,
        "description":   desc,
        "priority":      priority,
        "stage":         "junior",
        "status":        "Senior Review",   # immediately queued for Senior
        "stage_results": json.dumps({
            "junior": {
                "agent":    "Junior Agent",
                "action":   "Created task",
                "decision": "Approved",
                "reason":   f"Edit suggested by {requester}. Forwarded to Senior Agent for review.",
                "risk":     "Low",
            }
        }),
        "risk_level":    "Low",
        "created_at":    _now(),
        "updated_at":    _now(),
    }
    r = db.table("approval_requests").insert(row).execute()
    if r.data: return r.data[0]
    raise Exception("Insert failed.")

def _get_tasks_for_agent(status):
    db = _db()
    if db is None: return []
    try:
        return db.table("approval_requests")\
                 .select("*").eq("status", status)\
                 .order("created_at").execute().data or []
    except: return []

def _get_all_tasks(status_filter=None):
    db = _db()
    if db is None: return []
    try:
        q = db.table("approval_requests").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        return q.execute().data or []
    except: return []

def _update_task(tid, **kw):
    db = _db()
    if db is None: return
    kw["updated_at"] = _now()
    db.table("approval_requests").update(kw).eq("id", tid).execute()

def _delete_task(tid):
    db = _db()
    if db: db.table("approval_requests").delete().eq("id", tid).execute()

def _write_kb(query, solution):
    db = _db()
    if db is None: return
    try:
        ex = db.table("resolved_issues").select("id").eq("query",query).execute()
        if ex.data:
            db.table("resolved_issues").update({"solution":solution}).eq("query",query).execute()
        else:
            db.table("resolved_issues").insert({"query":query,"solution":solution}).execute()
    except Exception as e:
        st.warning(f"KB write: {e}")

def _stats():
    rows = _get_all_tasks()
    in_progress = {"Senior Review","TechLead Review","CTO Review"}
    return {
        "total":    len(rows),
        "progress": sum(1 for r in rows if r.get("status") in in_progress),
        "awaiting": sum(1 for r in rows if r.get("status") == "Awaiting Approval"),
        "approved": sum(1 for r in rows if r.get("status") == "Approved"),
        "rejected": sum(1 for r in rows if r.get("status") == "Rejected"),
    }

# ── Claude API ────────────────────────────────────────────────────────────────
def _claude(system: str, user: str) -> dict:
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json"},
            json={
                "model":      ANTHROPIC_MODEL,
                "max_tokens": 300,
                "system":     system,
                "messages":   [{"role":"user","content":user}],
            },
            timeout=30,
        )
        raw = ""
        for block in resp.json().get("content",[]):
            if block.get("type") == "text": raw += block["text"]
        raw = raw.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception as e:
        return {"decision":"Escalate","reason":f"Error: {e}","risk":"Medium"}

# ── Agent runners ─────────────────────────────────────────────────────────────

def _agent_system(role: str, next_role: str) -> str:
    return (
        f"You are the {role} in a document approval hierarchy. "
        f"Review the request and decide whether to approve and pass to {next_role}, "
        f"or reject it entirely. "
        "Respond ONLY with raw JSON (no markdown). "
        'Keys: "decision" ("Approve" or "Reject"), '
        '"reason" (1-2 sentences), '
        '"risk" ("Low", "Medium", or "High"), '
        '"security_involved" (true or false).'
    )

def _agent_user(task: dict, prev_notes: str = "") -> str:
    return (
        f"Document request:\n"
        f"Title: {task['title']}\n"
        f"Type: {task['request_type']}\n"
        f"Department: {task['department']}\n"
        f"Requester: {task['requester']}\n"
        f"Description: {task['description']}\n"
        f"Priority: {task['priority']}\n"
        + (f"Previous agent notes: {prev_notes}\n" if prev_notes else "")
    )

def run_senior_agent(task: dict):
    """
    Senior Agent wakes → picks up 'Senior Review' task →
    reviews → creates 'Approve technical change' task for Tech Lead
    """
    sr = _load_sr(task)
    prev = sr.get("junior",{}).get("reason","")
    result = _claude(
        _agent_system("Senior Agent", "Tech Lead"),
        _agent_user(task, prev),
    )
    sr["senior"] = {
        "agent":    "Senior Agent",
        "action":   "Reviewed edit",
        "decision": result.get("decision","Approve"),
        "reason":   result.get("reason",""),
        "risk":     result.get("risk","Low"),
    }
    if result.get("risk","Low") == "High":
        _update_task(task["id"], risk_level="High")

    if result.get("decision") == "Reject":
        _update_task(task["id"],
            status="Rejected", stage="senior",
            stage_results=json.dumps(sr))
    else:
        # Creates next task: "Approve technical change" for Tech Lead
        _update_task(task["id"],
            status="TechLead Review",
            stage="techlead",
            stage_results=json.dumps(sr))

def run_techlead_agent(task: dict):
    """
    Tech Lead Agent wakes → picks up 'TechLead Review' task →
    validates technical safety → routes to CTO or CEO
    """
    sr    = _load_sr(task)
    prev  = sr.get("senior",{}).get("reason","")
    result = _claude(
        _agent_system("Tech Lead Agent", "CTO or CEO"),
        _agent_user(task, prev),
    )
    sr["techlead"] = {
        "agent":             "Tech Lead Agent",
        "action":            "Validated technical safety",
        "decision":          result.get("decision","Approve"),
        "reason":            result.get("reason",""),
        "risk":              result.get("risk","Low"),
        "security_involved": result.get("security_involved", False),
    }
    if result.get("risk","Low") == "High":
        _update_task(task["id"], risk_level="High")

    if result.get("decision") == "Reject":
        _update_task(task["id"],
            status="Rejected", stage="techlead",
            stage_results=json.dumps(sr))
    else:
        # Creates "Final approval" task for CTO (or CEO if security)
        assignee = "CEO" if result.get("security_involved") else "CTO"
        sr["techlead"]["routed_to"] = assignee
        _update_task(task["id"],
            status="CTO Review",
            stage="cto",
            stage_results=json.dumps(sr))

def run_cto_ceo_agent(task: dict):
    """
    CTO/CEO Agent wakes → sees 'Final approval' task →
    if human approval required → creates approval request for YOU
    """
    sr   = _load_sr(task)
    prev = sr.get("techlead",{}).get("reason","")
    routed_to = sr.get("techlead",{}).get("routed_to","CTO")

    result = _claude(
        (
            f"You are the {routed_to} agent in a document approval hierarchy. "
            "This is the final AI review before human sign-off. "
            "Be conservative — escalate to human if there is any doubt. "
            "Respond ONLY with raw JSON (no markdown). "
            'Keys: "decision" ("Approve" — auto-approve if trivial, or "Escalate" — send to human), '
            '"reason" (1-2 sentences), "risk" ("Low","Medium","High").'
        ),
        _agent_user(task, prev),
    )

    sr["cto"] = {
        "agent":    f"{routed_to} Agent",
        "action":   "Final AI review",
        "decision": result.get("decision","Escalate"),
        "reason":   result.get("reason",""),
        "risk":     result.get("risk","Medium"),
    }

    if result.get("decision") == "Approve" and result.get("risk","High") == "Low":
        # Trivially safe — auto-approve, skip human, go straight to KB
        sr["human"] = {
            "agent":    "Auto",
            "decision": "Approved",
            "reason":   "Auto-approved by CTO/CEO agent (low risk).",
        }
        _update_task(task["id"],
            status="Approved", stage="kb",
            stage_results=json.dumps(sr))
        _run_kb({**task, "stage_results": json.dumps(sr)})
    else:
        # Escalate → creates approval request for human
        _update_task(task["id"],
            status="Awaiting Approval",
            stage="human",
            stage_results=json.dumps(sr))

def _run_kb(task: dict):
    """Auto-triggered on approval → writes to resolved_issues."""
    sr = _load_sr(task)
    reason = (
        sr.get("cto",{}).get("reason","")
        or sr.get("techlead",{}).get("reason","")
        or "Approved by pipeline."
    )
    solution = f"[Pipeline Approved] {reason}"
    _write_kb(task["title"], solution)
    sr["kb"] = {"status":"updated","written_at":_now()}
    _update_task(task["id"], stage_results=json.dumps(sr))

# ── Heartbeat — each agent checks its own queue ───────────────────────────────
def heartbeat_tick():
    """
    Simulates each agent waking on its heartbeat:
      Senior   → processes 'Senior Review' tasks
      TechLead → processes 'TechLead Review' tasks
      CTO/CEO  → processes 'CTO Review' tasks
    """
    processed = 0
    for status, runner in [
        ("Senior Review",   run_senior_agent),
        ("TechLead Review", run_techlead_agent),
        ("CTO Review",      run_cto_ceo_agent),
    ]:
        tasks = _get_tasks_for_agent(status)
        for task in tasks[:2]:   # process up to 2 per tick per agent
            try:
                runner(task)
                processed += 1
            except Exception as e:
                st.warning(f"Agent error on task #{task.get('id')}: {e}")
    return processed

# ── Hierarchy renderer ────────────────────────────────────────────────────────
def _pill_color(agent_id):
    colors = {
        "junior":   ("#eef2ff","#4338ca"),
        "senior":   ("#f0f9ff","#0369a1"),
        "techlead": ("#f5f3ff","#6d28d9"),
        "cto":      ("#fffbeb","#b45309"),
        "human":    ("#f0fdf4","#065f46"),
        "kb":       ("#ecfdf5","#047857"),
    }
    return colors.get(agent_id,("#f1f5f9","#475569"))

def _render_hierarchy(sr: dict, current_stage: str, risk_level: str = "Low"):
    """Render the full agent hierarchy with live status for a task."""
    st.markdown("<div class='hier'>", unsafe_allow_html=True)

    for i, agent in enumerate(AGENTS):
        aid   = agent["id"]
        res   = sr.get(aid)
        bg, fg = _pill_color(aid)

        # Determine dot state
        if res:
            d = res.get("decision","")
            if d in ("Approved","Approve","updated","Auto") or res.get("status") == "updated":
                dot_cls  = "done"
                dot_style = f"background:{bg};border-color:{fg};"
                res_cls  = "done"
                tick     = "✅"
                res_text = res.get("reason") or res.get("status","")
            elif d == "Reject":
                dot_cls  = "fail"
                dot_style = ""
                res_cls  = "fail"
                tick     = "❌"
                res_text = res.get("reason","")
            elif d in ("Escalate","Pending") or res.get("action") == "Created task":
                dot_cls  = "done"
                dot_style = f"background:{bg};border-color:{fg};"
                res_cls  = "done"
                tick     = "⬆️" if d == "Escalate" else "✅"
                res_text = res.get("reason") or res.get("action","")
            else:
                dot_cls  = "done"
                dot_style = f"background:{bg};border-color:{fg};"
                res_cls  = "done"
                tick     = "✅"
                res_text = res.get("reason","")
        elif aid == current_stage:
            dot_cls   = "active"
            dot_style = f"background:{bg};border-color:{fg};"
            res_cls   = "active"
            tick      = ""
            res_text  = "⏳ Agent working…"
        else:
            dot_cls   = "idle"
            dot_style = ""
            res_cls   = ""
            tick      = ""
            res_text  = ""

        # Badge
        if agent["manual"]:
            badge = "<span class='badge-manual'>MANUAL</span>"
        elif aid == current_stage and not res:
            badge = "<span class='badge-active'>● ACTIVE</span>"
        else:
            badge = "<span class='badge-auto'>AUTO</span>"

        # Creates-arrow
        if agent["creates"] and res and res.get("decision") not in ("Reject",):
            next_agent = AGENT_BY_ID.get(agent["creates"],{})
            creates_html = (
                f"<div class='creates-arrow'>"
                f"↓ creates task "
                f"<span class='creates-pill'>"
                f"{agent['task_label']} → {next_agent.get('label','')}"
                f"</span></div>"
            )
        else:
            creates_html = ""

        result_html = (
            f"<div class='hresult {res_cls}'>{tick} {res_text}</div>"
            if res_text else ""
        )

        # Routed-to note for CTO/CEO
        extra = ""
        if aid == "techlead" and res and res.get("routed_to"):
            extra = (
                f"<div style='font-size:11px;color:#7c3aed;margin-top:3px'>"
                f"→ Routed to: <strong>{res['routed_to']}</strong>"
                + (" (security involved)" if res.get("security_involved") else "")
                + "</div>"
            )

        st.markdown(
            f"<div class='hnode'>"
            f"  <div class='hline-wrap'>"
            f"    <div class='hdot {dot_cls}' style='{dot_style}'>{agent['icon']}</div>"
            f"    {'<div class=\"harrow\">↓</div>' if i < len(AGENTS)-1 else ''}"
            f"  </div>"
            f"  <div class='hbody'>"
            f"    <div class='htitle'>{agent['label']}{badge}</div>"
            f"    <div class='hdesc'>{agent['desc']}</div>"
            f"    {result_html}{extra}{creates_html}"
            f"  </div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _status_pill(status):
    cfg = {
        "Senior Review":    ("#dbeafe","#1e40af"),
        "TechLead Review":  ("#ede9fe","#5b21b6"),
        "CTO Review":       ("#fef3c7","#92400e"),
        "Awaiting Approval":("#fef3c7","#92400e"),
        "Approved":         ("#d1fae5","#065f46"),
        "Rejected":         ("#fee2e2","#991b1b"),
        "Done":             ("#d1fae5","#065f46"),
    }
    bg, fg = cfg.get(status,("#f1f5f9","#475569"))
    return f"<span class='spill' style='background:{bg};color:{fg}'>{status}</span>"

def _fmt(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z","+00:00")).strftime("%d %b %Y, %I:%M %p")
    except: return ts or "—"

# ════════════════════════════════════════════════════════
#  PAGE ENTRY POINT
# ════════════════════════════════════════════════════════
def page_approval_pipeline():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("# 📋 Approval Pipeline")
    st.markdown(
        "<p style='color:#6b7280'>"
        "Hierarchical agentic pipeline: Junior → Senior → Tech Lead → CTO/CEO → You → KB. "
        "Agents wake automatically. Your only action is the final approval."
        "</p>", unsafe_allow_html=True,
    )

    # ── Heartbeat ─────────────────────────────────────────────────────────────
    if "hb_last" not in st.session_state:
        st.session_state["hb_last"] = 0.0

    now        = time.time()
    since      = now - st.session_state["hb_last"]
    next_tick  = max(0, HEARTBEAT_SEC - since)

    if since >= HEARTBEAT_SEC:
        st.session_state["hb_last"] = now
        n = heartbeat_tick()
        if n:
            st.toast(f"⚙️ {n} task(s) advanced by agents", icon="🤖")

    st.markdown(
        f"<div class='hbbar'>"
        f"  <div class='hbdot'></div>"
        f"  <span>Agent heartbeat active — next wake in <strong>{int(next_tick)}s</strong></span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    tab1, tab2 = st.tabs(["👩‍💻 Submit Request", "✅ Your Approval"])

    # ══════════════════════════════════════════════════
    #  TAB 1 — JUNIOR CREATES TASK + LIVE PIPELINE
    # ══════════════════════════════════════════════════
    with tab1:
        st.markdown("### 👩‍💻 Junior Agent — Create Task")
        st.markdown(
            "<small style='color:#6366f1'>Fill in the request. "
            "It will automatically flow through Senior → Tech Lead → CTO/CEO.</small><br><br>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            requester  = st.text_input("👤 Your Name / ID *", placeholder="e.g. Junior Dev EMP-1042")
            department = st.selectbox("🏢 Department *", [
                "Select…","Engineering","Finance","HR",
                "Legal","Operations","Marketing","Executive","Other",
            ])
            priority = st.selectbox("🚨 Priority", ["Medium","High","Low"])
        with c2:
            title    = st.text_input("📌 Edit / Document Title *",
                                     placeholder="e.g. Refactor auth module")
            doc_type = st.selectbox("📂 Type *", [
                "Select…","Code Change","Financial Report","Employee Data",
                "System Design","Vendor Contract","Policy Document",
                "Audit Report","Security Patch","Other",
            ])

        description = st.text_area(
            "📋 Describe the edit / change *",
            placeholder="What did you change, why, and any risks you see?",
            height=100,
        )

        if st.button("🚀 Submit to Senior Agent"):
            errors = []
            if not requester.strip():   errors.append("Your name / ID required.")
            if department == "Select…": errors.append("Select department.")
            if doc_type   == "Select…": errors.append("Select type.")
            if not title.strip():       errors.append("Title required.")
            if not description.strip(): errors.append("Description required.")
            for e in errors: st.error(e)
            if not errors:
                try:
                    t = _create_task(
                        title.strip(), requester.strip(), department,
                        doc_type, description.strip(), priority,
                    )
                    st.success(
                        f"✅ Task #{t['id']} created! "
                        "Senior Agent will pick it up on the next heartbeat.",
                        icon="🎉",
                    )
                    time.sleep(0.3)
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed: {ex}")

        # ── Stats ─────────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📊 Pipeline Dashboard")
        try:
            s  = _stats()
            mc = st.columns(5)
            for col, val, label, icon in zip(
                mc,
                [s["total"],s["progress"],s["awaiting"],s["approved"],s["rejected"]],
                ["Total","In Progress","Needs Your OK","Approved","Rejected"],
                ["📋","⚙️","🔔","🟢","🔴"],
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
        sf_col, _ = st.columns([1.5,3])
        with sf_col:
            sf = st.selectbox("Show tasks", [
                "All","Senior Review","TechLead Review",
                "CTO Review","Awaiting Approval","Approved","Rejected",
            ], key="dash_sf")

        tasks = _get_all_tasks(sf if sf != "All" else None)
        if not tasks:
            st.info("No tasks yet.", icon="📭")
        else:
            for t in tasks:
                status = t.get("status","")
                sr     = _load_sr(t)
                stage  = t.get("stage","junior")
                with st.expander(
                    f"#{t['id']} — {t.get('title','?')} | {t.get('requester','?')} | {status}"
                ):
                    st.markdown(
                        f"{_status_pill(status)} "
                        f"<span class='spill' style='background:#f1f5f9;color:#475569'>"
                        f"Risk: {t.get('risk_level','—')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**Requester:** {t.get('requester','–')} &nbsp;|&nbsp; "
                        f"**Dept:** {t.get('department','–')} &nbsp;|&nbsp; "
                        f"**Type:** {t.get('request_type','–')} &nbsp;|&nbsp; "
                        f"**Submitted:** {_fmt(t.get('created_at',''))}"
                    )
                    st.markdown(
                        f"<div style='background:#f8fafc;border-left:4px solid #6366f1;"
                        f"border-radius:10px;padding:11px;margin:10px 0;font-size:13px'>"
                        f"{t.get('description','–')}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Agent Hierarchy:**")
                    _render_hierarchy(sr, current_stage=stage,
                                      risk_level=t.get("risk_level","Low"))

                    # Refresh + delete
                    rc1, rc2, _ = st.columns([1,1,4])
                    with rc1:
                        if st.button("🔄 Refresh", key=f"ref_{t['id']}"):
                            st.rerun()
                    with rc2:
                        if st.button("🗑️ Delete", key=f"del_dash_{t['id']}"):
                            try: _delete_task(t["id"]); st.rerun()
                            except Exception as ex: st.error(str(ex))

        # Force rerun after next heartbeat interval
        if st.button("⟳ Refresh now", key="manual_refresh"):
            st.rerun()

    # ══════════════════════════════════════════════════
    #  TAB 2 — YOUR APPROVAL (only manual step)
    # ══════════════════════════════════════════════════
    with tab2:
        ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD","admin123")

        if not st.session_state.get("exec_logged_in"):
            st.markdown("### 🔐 Login")
            col, _ = st.columns([1.5,2.5])
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
            st.markdown("### ✅ Step 5 — Your Approval")
            st.markdown(
                "<small style='color:#6b7280'>This is the ONLY manual step. "
                "Every task here has already been reviewed by Senior → Tech Lead → CTO/CEO.</small>",
                unsafe_allow_html=True,
            )
        with lc:
            if st.button("Logout", key="exec_out"):
                st.session_state["exec_logged_in"] = False
                st.rerun()

        awaiting = _get_tasks_for_agent("Awaiting Approval")

        if not awaiting:
            st.success("✅ Nothing waiting for your approval right now.", icon="🎉")
        else:
            st.warning(f"🔔 **{len(awaiting)} task(s) need your approval.**")

        for t in awaiting:
            rid  = t["id"]
            sr   = _load_sr(t)
            risk = t.get("risk_level","—")

            with st.expander(
                f"#{rid} — {t.get('title','?')} | Risk: {risk}",
                expanded=True,
            ):
                st.markdown(
                    f"{_status_pill('Awaiting Approval')} "
                    f"<span class='spill' style='background:#f1f5f9;color:#475569'>Risk: {risk}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Requester:** {t.get('requester','–')} &nbsp;|&nbsp; "
                    f"**Dept:** {t.get('department','–')} &nbsp;|&nbsp; "
                    f"**Type:** {t.get('request_type','–')}"
                )
                st.markdown(
                    f"<div style='background:#f8fafc;border-left:4px solid #6366f1;"
                    f"border-radius:10px;padding:11px;margin:10px 0;font-size:13px'>"
                    f"{t.get('description','–')}</div>",
                    unsafe_allow_html=True,
                )

                # Agent chain summary
                for aid, label, icon in [
                    ("junior",   "Junior",   "👩‍💻"),
                    ("senior",   "Senior",   "👨‍💼"),
                    ("techlead", "Tech Lead","🧑‍🔧"),
                    ("cto",      "CTO/CEO",  "🏛️"),
                ]:
                    res = sr.get(aid)
                    if res:
                        d = res.get("decision","")
                        color = "#f0fdf4" if d not in ("Reject","Rejected") else "#fef2f2"
                        border = "#059669" if d not in ("Reject","Rejected") else "#dc2626"
                        st.markdown(
                            f"<div style='background:{color};border-left:3px solid {border};"
                            f"border-radius:8px;padding:8px 12px;margin:4px 0;font-size:12px'>"
                            f"{icon} <strong>{label}:</strong> {res.get('reason','')}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                st.markdown("**Full hierarchy:**")
                _render_hierarchy(sr, current_stage="human", risk_level=risk)

                st.markdown("---")
                note = st.text_area(
                    "Your note (saved to KB on approval)",
                    key=f"note_{rid}", height=70,
                    placeholder="Add context or reasoning…",
                )

                b1, b2, b3, _ = st.columns([1,1,1,3])
                with b1:
                    if st.button("✅ Approve", key=f"app_{rid}", use_container_width=True):
                        try:
                            sr["human"] = {
                                "agent":    "You",
                                "decision": "Approved",
                                "reason":   note or "Approved by authority.",
                            }
                            _update_task(rid,
                                status="Approved", stage="kb",
                                stage_results=json.dumps(sr),
                                reviewer_note=note)
                            # Step 8 — KB auto-update
                            _run_kb({**t, "stage_results": json.dumps(sr)})
                            st.success(
                                "✅ Approved! KB updated — "
                                "next user asking a similar question will get this answer automatically."
                            )
                            st.rerun()
                        except Exception as ex: st.error(str(ex))
                with b2:
                    if st.button("❌ Reject", key=f"rej_{rid}", use_container_width=True):
                        try:
                            sr["human"] = {
                                "agent":    "You",
                                "decision": "Rejected",
                                "reason":   note or "Rejected by authority.",
                            }
                            _update_task(rid,
                                status="Rejected", stage="human",
                                stage_results=json.dumps(sr),
                                reviewer_note=note)
                            st.warning("❌ Rejected.")
                            st.rerun()
                        except Exception as ex: st.error(str(ex))
                with b3:
                    if st.button("🗑️ Delete", key=f"del_{rid}", use_container_width=True):
                        try: _delete_task(rid); st.rerun()
                        except Exception as ex: st.error(str(ex))

        # ── Decision history ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📋 Decision History")
        hist = [r for r in _get_all_tasks() if r.get("status") in ("Approved","Rejected")]
        if not hist:
            st.info("No decisions yet.")
        for t in hist:
            rid    = t["id"]
            status = t.get("status","")
            bg     = "#d1fae5" if status=="Approved" else "#fee2e2"
            fg     = "#065f46" if status=="Approved" else "#991b1b"
            with st.expander(f"#{rid} — {t.get('title','?')} | {status}"):
                st.markdown(
                    f"<span class='spill' style='background:{bg};color:{fg}'>{status}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Requester:** {t.get('requester','–')} | "
                    f"**Dept:** {t.get('department','–')} | "
                    f"**Submitted:** {_fmt(t.get('created_at',''))}"
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

        with st.expander("📄 Supabase SQL — run once if columns missing"):
            st.code("""
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS stage_results TEXT;
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS risk_level    TEXT DEFAULT 'Low';
ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS reviewer_note TEXT;
            """, language="sql")
