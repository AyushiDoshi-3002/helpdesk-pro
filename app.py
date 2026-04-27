import streamlit as st
import re
import io
import json
import time
import requests
from datetime import datetime

st.set_page_config(page_title="HelpDesk Pro — Agent Pipeline", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f0c29, #302b63, #24243e); }
section[data-testid="stSidebar"] * { color: white !important; }
.main { background: #f8f7ff; }

/* ── Agent pipeline bar ── */
.pipeline-wrap {
    background: #0d0d16;
    border-radius: 14px;
    padding: 16px 24px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
    overflow-x: auto;
}
.agent-bubble {
    display: flex; flex-direction: column; align-items: center;
    gap: 4px; min-width: 72px;
}
.agent-circle {
    width: 42px; height: 42px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
    border: 1.5px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.04);
    transition: all 0.3s;
}
.agent-circle.active  { border-color:#7c6fff; background:rgba(124,111,255,0.18); box-shadow:0 0 14px rgba(124,111,255,0.5); }
.agent-circle.done    { border-color:#00d4aa; background:rgba(0,212,170,0.12); }
.agent-circle.skipped { border-color:#444; background:rgba(255,255,255,0.02); opacity:0.4; }
.agent-lbl { font-family:'JetBrains Mono',monospace; font-size:8px; color:#555; letter-spacing:0.5px; text-transform:uppercase; }
.agent-lbl.active  { color:#a89fff; }
.agent-lbl.done    { color:#00d4aa; }
.pipe-arrow { color:#333; font-size:16px; }
.pipe-arrow.lit { color:#7c6fff; }

/* ── Log stream ── */
.log-box {
    background:#0a0a0f; border-radius:10px; padding:12px 16px;
    font-family:'JetBrains Mono',monospace; font-size:11px;
    max-height:260px; overflow-y:auto; margin-bottom:16px;
}
.log-line { padding: 3px 0; border-left: 2px solid transparent; padding-left: 8px; }
.log-line.sys    { color:#555; border-color:#333; }
.log-line.triage { color:#a89fff; border-color:#7c6fff; }
.log-line.kb     { color:#00d4aa; border-color:#00d4aa; }
.log-line.ticket { color:#f5a623; border-color:#f5a623; }
.log-line.resolv { color:#ff6b6b; border-color:#ff6b6b; }
.log-line.handoff{ color:#888; border-color:#555; }

/* ── Result cards ── */
.answer-box { background:linear-gradient(135deg,#ede9fe,#ddd6fe); border-radius:12px; padding:20px; border-left:4px solid #7c3aed; font-size:15px; line-height:1.7; color:#1e1b4b; }
.learned-box { background:linear-gradient(135deg,#d1fae5,#a7f3d0); border-radius:12px; padding:20px; border-left:4px solid #059669; font-size:15px; line-height:1.7; color:#064e3b; }
.no-answer-box { background:#fff7ed; border-radius:12px; padding:16px 20px; border-left:4px solid #f97316; color:#7c2d12; font-size:14px; }
.ticket-card { background:linear-gradient(135deg,#fef3c7,#fde68a); border-radius:12px; padding:20px; border-left:4px solid #d97706; font-size:14px; color:#1c1917; }
.ticket-id-big { font-family:'JetBrains Mono',monospace; font-size:26px; font-weight:700; color:#b45309; }

/* ── Agent decision badge ── */
.decision-badge {
    display:inline-block; font-family:'JetBrains Mono',monospace;
    font-size:10px; padding:3px 10px; border-radius:20px; font-weight:700;
    letter-spacing:0.5px; margin:2px;
}
.badge-route  { background:rgba(124,111,255,0.15); color:#7c6fff; }
.badge-kb     { background:rgba(0,212,170,0.15); color:#00a882; }
.badge-ticket { background:rgba(245,166,35,0.15); color:#d97706; }
.badge-done   { background:rgba(0,212,170,0.15); color:#059669; }

/* ── Misc ── */
.badge-open      { background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-inprogress{ background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-resolved  { background:#d1fae5;color:#065f46;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.prio-high  { background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-medium{ background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-low   { background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
div.stButton > button { background:linear-gradient(135deg,#7c3aed,#5b21b6); color:white; border:none; border-radius:10px; padding:10px 24px; font-weight:600; font-size:14px; }
div.stButton > button:hover { background:linear-gradient(135deg,#6d28d9,#4c1d95); }
.metric-card { background:white;border-radius:14px;padding:20px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,0.06); }
.metric-number { font-family:'Syne',sans-serif;font-size:36px;font-weight:800;color:#7c3aed; }
.metric-label  { font-size:13px;color:#6b7280;margin-top:4px; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  ANTHROPIC CLIENT  (Claude powers all agents)
# ════════════════════════════════════════════════════════
def call_claude(system_prompt: str, user_msg: str, max_tokens: int = 800) -> str:
    """Call Claude via Anthropic API. Requires ANTHROPIC_API_KEY in st.secrets."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in Streamlit secrets.")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_msg}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(b.get("text", "") for b in data.get("content", []))


# ════════════════════════════════════════════════════════
#  DATABASE  (unchanged from original)
# ════════════════════════════════════════════════════════
try:
    from supabase import create_client
    SUPABASE_OK = True
except ImportError:
    SUPABASE_OK = False

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    id         BIGSERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    job_role   TEXT NOT NULL,
    query      TEXT NOT NULL,
    priority   TEXT NOT NULL DEFAULT 'Medium',
    status     TEXT NOT NULL DEFAULT 'Open',
    admin_note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS resolved_issues (
    id         BIGSERIAL PRIMARY KEY,
    query      TEXT NOT NULL,
    solution   TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE tickets        DISABLE ROW LEVEL SECURITY;
ALTER TABLE resolved_issues DISABLE ROW LEVEL SECURITY;
"""

@st.cache_resource(show_spinner=False)
def get_db():
    if not SUPABASE_OK: return None
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if url and key:
        return create_client(url, key)
    return None

def db_create_ticket(user_id, job_role, query, priority):
    db = get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    result = db.table("tickets").insert({"user_id":user_id,"job_role":job_role,"query":query,"priority":priority,"status":"Open"}).execute()
    if result.data: return result.data[0]
    raise Exception("Insert returned no data")

def db_get_tickets(status_filter=None):
    db = get_db()
    if db is None: return []
    q = db.table("tickets").select("*").order("created_at", desc=True)
    if status_filter and status_filter != "All": q = q.eq("status", status_filter)
    return q.execute().data or []

def db_update_ticket(tid, status, note):
    db = get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    result = db.table("tickets").update({"status":status,"admin_note":note}).eq("id", tid).execute()
    if not result.data: raise Exception("Update returned no data — check RLS")

def db_delete_ticket(tid):
    db = get_db()
    if db: db.table("tickets").delete().eq("id", tid).execute()

def db_stats():
    tickets = db_get_tickets()
    return {
        "total": len(tickets),
        "open": sum(1 for t in tickets if t["status"] == "Open"),
        "in_progress": sum(1 for t in tickets if t["status"] == "In Progress"),
        "resolved": sum(1 for t in tickets if t["status"] == "Resolved"),
    }


# ════════════════════════════════════════════════════════
#  LEARNED ANSWERS LOOKUP  (unchanged)
# ════════════════════════════════════════════════════════
def _normalize(text):
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

def _all_words(text):
    return re.findall(r'\b[a-z]{2,}\b', text.lower())

def _keyword_score(query, stored_query):
    q_norm, s_norm = _normalize(query), _normalize(stored_query)
    if q_norm == s_norm: return 1.0
    if q_norm in s_norm or s_norm in q_norm: return 0.9
    q_words, s_words = set(_all_words(query)), set(_all_words(stored_query))
    if not q_words: return 0.0
    if q_words.issubset(s_words): return 0.85
    union = q_words | s_words
    return len(q_words & s_words) / len(union) if union else 0.0

def check_learned_answers(query):
    db = get_db()
    if db is None: return None
    THRESHOLD = 0.3
    best_score, best_solution, best_matched = 0.0, None, None
    try:
        resp = db.table("tickets").select("query, admin_note").not_.is_("admin_note", "null").execute()
        for row in (resp.data or []):
            note, q = (row.get("admin_note") or "").strip(), (row.get("query") or "").strip()
            if not note or not q: continue
            score = _keyword_score(query, q)
            if score > best_score: best_score, best_solution, best_matched = score, note, q
    except Exception: pass
    try:
        resp2 = db.table("resolved_issues").select("query, solution").execute()
        for row in (resp2.data or []):
            sol, q = (row.get("solution") or "").strip(), (row.get("query") or "").strip()
            if not sol or not q: continue
            score = _keyword_score(query, q)
            if score > best_score: best_score, best_solution, best_matched = score, sol, q
    except Exception: pass
    if best_solution and best_score >= THRESHOLD:
        return {"solution": best_solution, "matched_query": best_matched, "score": best_score}
    return None


# ════════════════════════════════════════════════════════
#  PDF KNOWLEDGE BASE  (unchanged)
# ════════════════════════════════════════════════════════
_GDRIVE_FILE_ID = "1cUagShzCe0XsCbF5NEU9T62ICcU2I5AO"

@st.cache_resource(show_spinner="📄 Downloading PDF…")
def get_pdf_bytes():
    try:
        session = requests.Session()
        url1 = f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}"
        resp = session.get(url1, timeout=30)
        if "text/html" in resp.headers.get("content-type",""):
            url2 = f"https://drive.usercontent.google.com/download?id={_GDRIVE_FILE_ID}&export=download&confirm=t"
            resp = session.get(url2, timeout=30)
        if "text/html" in resp.headers.get("content-type",""):
            m = re.search(r'confirm=([0-9A-Za-z_\-]+)', resp.text)
            if m:
                resp = session.get(f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}&confirm={m.group(1)}", timeout=30)
        resp.raise_for_status()
        return None if "text/html" in resp.headers.get("content-type","") else resp.content
    except Exception: return None

@st.cache_resource(show_spinner="📄 Extracting Q&A…")
def load_qa_pairs():
    pdf_bytes = get_pdf_bytes()
    if not pdf_bytes: return []
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        text = text.lower()
        qa_pairs = []
        for part in re.split(r'q\.', text):
            if "answer" not in part: continue
            try:
                q_part, a_part = part.split("answer", 1)
                q, a = q_part.strip(), a_part.strip()
                if len(q) < 5 or len(a) < 30: continue
                if "enroll" in a or "course" in a: continue
                qa_pairs.append((q, a))
            except: continue
        return qa_pairs
    except Exception: return []

@st.cache_resource(show_spinner="🧠 Loading semantic model…")
def load_model_and_embeddings():
    try:
        from sentence_transformers import SentenceTransformer, util
        pairs = load_qa_pairs()
        if not pairs: return None, None, None, util
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode([q for q, a in pairs], convert_to_tensor=True)
        return model, embeddings, pairs, util
    except Exception: return None, None, None, None


# ════════════════════════════════════════════════════════
#  PIPELINE UI HELPERS
# ════════════════════════════════════════════════════════
def render_pipeline_bar(states: dict):
    """
    states: dict keyed by agent name → 'idle' | 'active' | 'done' | 'skipped'
    agents: triage, kb, ticket, resolver
    """
    agents = [
        ("triage",  "🎯", "Triage"),
        ("kb",      "🧠", "Knowledge"),
        ("ticket",  "🎫", "Ticketing"),
        ("resolver","⚡", "Resolver"),
    ]
    parts = ['<div class="pipeline-wrap">']
    for i, (key, icon, label) in enumerate(agents):
        state = states.get(key, "idle")
        parts.append(f'''
        <div class="agent-bubble">
          <div class="agent-circle {state}">{icon}</div>
          <div class="agent-lbl {state}">{label}</div>
        </div>''')
        if i < len(agents) - 1:
            lit = "lit" if states.get(agents[i+1][0]) in ("active","done") else ""
            parts.append(f'<div class="pipe-arrow {lit}">›</div>')
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)

def render_log(logs: list):
    lines = "".join(
        f'<div class="log-line {cls}"><span style="color:#444">[{ts}]</span> {msg}</div>'
        for ts, cls, msg in logs
    )
    st.markdown(f'<div class="log-box">{lines}</div>', unsafe_allow_html=True)

def now_ts():
    return datetime.now().strftime("%H:%M:%S")


# ════════════════════════════════════════════════════════
#  THE FOUR AGENTS
# ════════════════════════════════════════════════════════

def agent_triage(query: str, priority: str, logs: list) -> dict:
    """
    Triage Agent: classify intent, urgency, decide routing.
    Returns dict with keys: category, urgency, route, confidence, reason
    """
    logs.append((now_ts(), "triage", f"🎯 TRIAGE — Received query. Classifying…"))
    raw = call_claude(
        system_prompt="""You are a helpdesk triage agent. Analyze the user's support query and respond ONLY with a JSON object — no markdown, no extra text:
{"category": "technical|password|access|hardware|general",
 "urgency": "critical|high|medium|low",
 "route": "KB_SEARCH|CREATE_TICKET|ESCALATE",
 "confidence": 0.0-1.0,
 "reason": "one sentence explanation"}
Route to KB_SEARCH if the issue is likely answerable from a knowledge base (passwords, VPN, software).
Route to CREATE_TICKET if it needs human intervention (database access, hardware repair, permissions).
Route to ESCALATE if it's a security incident or critical production issue.""",
        user_msg=f'Query: "{query}"\nUser-set priority: {priority}'
    )
    try:
        result = json.loads(raw.strip().replace("```json","").replace("```",""))
    except Exception:
        result = {"category":"general","urgency":priority.lower(),"route":"KB_SEARCH","confidence":0.6,"reason":"Parse fallback"}
    logs.append((now_ts(), "triage", f"   Category: {result.get('category')} | Urgency: {result.get('urgency')} | Route → {result.get('route')} ({int(result.get('confidence',0)*100)}% confidence)"))
    logs.append((now_ts(), "handoff", f"   ↳ Triage → Knowledge Agent"))
    return result


def agent_kb(query: str, triage: dict, logs: list) -> dict:
    """
    Knowledge Agent: checks learned answers + PDF KB + Claude's own KB knowledge.
    Returns dict: found (bool), answer, source, confidence, needs_ticket
    """
    logs.append((now_ts(), "kb", f"🧠 KB AGENT — Searching knowledge base…"))

    # 1. Check Supabase learned answers
    learned = check_learned_answers(query)
    if learned:
        logs.append((now_ts(), "kb", f"   ✓ Match in resolved tickets (score {learned['score']:.0%})"))
        logs.append((now_ts(), "handoff", "   ↳ KB Agent → Resolver Agent"))
        return {"found": True, "answer": learned["solution"], "source": "learned",
                "matched": learned["matched_query"], "confidence": learned["score"], "needs_ticket": False}

    # 2. PDF semantic search
    model, embeddings, pairs, util = load_model_and_embeddings()
    if model and embeddings is not None and pairs:
        try:
            from sentence_transformers import util as st_util
            q_emb = model.encode(query.lower(), convert_to_tensor=True)
            scores = util.cos_sim(q_emb, embeddings)[0]
            best_idx = int(scores.argmax())
            best_score = float(scores[best_idx])
            if best_score >= 0.4:
                q, a = pairs[best_idx]
                logs.append((now_ts(), "kb", f"   ✓ PDF KB match (score {best_score:.2f})"))
                logs.append((now_ts(), "handoff", "   ↳ KB Agent → Resolver Agent"))
                return {"found": True, "answer": a.strip(), "source": "pdf",
                        "matched": q.strip(), "confidence": best_score, "needs_ticket": False}
        except Exception: pass

    # 3. Ask Claude if it can answer from general knowledge
    if triage.get("route") == "KB_SEARCH":
        logs.append((now_ts(), "kb", "   Asking Claude for general knowledge answer…"))
        raw = call_claude(
            system_prompt="""You are a corporate IT helpdesk knowledge agent. Answer common IT questions confidently.
Respond ONLY with JSON:
{"found": true/false, "answer": "full answer or empty string", "needs_ticket": true/false}
found=true if you can give a useful answer (passwords, VPN, software issues, general IT).
found=false + needs_ticket=true if it requires specific access or human action.""",
            user_msg=f'IT Query: "{query}"'
        )
        try:
            result = json.loads(raw.strip().replace("```json","").replace("```",""))
            if result.get("found"):
                logs.append((now_ts(), "kb", "   ✓ Claude general knowledge answer found"))
                logs.append((now_ts(), "handoff", "   ↳ KB Agent → Resolver Agent"))
                return {"found": True, "answer": result["answer"], "source": "claude_kb",
                        "matched": query, "confidence": 0.75, "needs_ticket": False}
        except Exception: pass

    logs.append((now_ts(), "kb", "   ✗ No KB match — escalating to ticketing"))
    logs.append((now_ts(), "handoff", "   ↳ KB Agent → Ticketing Agent"))
    return {"found": False, "answer": "", "source": "none", "matched": "", "confidence": 0.0, "needs_ticket": True}


def agent_ticket(query: str, triage: dict, user_id: str, job_role: str, priority: str, logs: list) -> dict:
    """
    Ticketing Agent: creates a structured ticket automatically.
    Returns dict with ticket metadata + db ticket id.
    """
    logs.append((now_ts(), "ticket", "🎫 TICKET AGENT — Generating structured ticket…"))
    raw = call_claude(
        system_prompt="""You are a helpdesk ticketing agent. Create a structured support ticket.
Respond ONLY with JSON — no markdown:
{"title": "max 8 word title",
 "description": "clear 2-sentence description of the issue",
 "assign_to": "IT Support|Security Team|Hardware Team|Database Admin|Network Team",
 "sla": "4h|8h|24h|48h",
 "tags": ["tag1","tag2"]}""",
        user_msg=f'Query: "{query}"\nCategory: {triage.get("category")}\nUrgency: {triage.get("urgency")}\nPriority: {priority}'
    )
    try:
        meta = json.loads(raw.strip().replace("```json","").replace("```",""))
    except Exception:
        meta = {"title": "Support Request", "description": query,
                "assign_to": "IT Support", "sla": "24h", "tags": ["support"]}

    # Create ticket in DB
    ticket_id = None
    try:
        t = db_create_ticket(user_id, job_role, query, priority)
        ticket_id = t.get("id")
        logs.append((now_ts(), "ticket", f"   ✓ Ticket #{ticket_id} created in database"))
    except Exception as e:
        logs.append((now_ts(), "ticket", f"   ⚠ DB error: {e} — ticket metadata still generated"))

    logs.append((now_ts(), "ticket", f"   Assigned to: {meta.get('assign_to')} | SLA: {meta.get('sla')}"))
    logs.append((now_ts(), "handoff", "   ↳ Ticket Agent → Resolver Agent"))
    return {**meta, "db_id": ticket_id}


def agent_resolver(query: str, kb_result: dict, ticket_meta: dict, logs: list) -> dict:
    """
    Resolver Agent: formats the final user-facing response.
    Returns dict: mode ('resolved' or 'escalated'), message
    """
    logs.append((now_ts(), "resolv", "⚡ RESOLVER AGENT — Formatting final response…"))

    if kb_result.get("found"):
        # Polish the KB answer
        polished = call_claude(
            system_prompt="You are the final response agent. Take this helpdesk KB answer and make it clear, friendly, and actionable for the employee. Use numbered steps where helpful. Keep it concise.",
            user_msg=f'Original query: "{query}"\nKB answer: "{kb_result["answer"]}"'
        )
        logs.append((now_ts(), "resolv", "   ✓ Answer polished and ready"))
        return {"mode": "resolved", "message": polished, "source": kb_result.get("source","kb")}
    else:
        # Write acknowledgment
        ack = call_claude(
            system_prompt="You are the final response agent. Write a warm, professional 2-3 sentence acknowledgment to the employee: their ticket was created, which team will handle it, and the expected SLA. Be reassuring.",
            user_msg=f'Ticket: #{ticket_meta.get("db_id","–")}\nIssue: "{query}"\nAssigned to: {ticket_meta.get("assign_to","IT Support")}\nSLA: {ticket_meta.get("sla","24h")}'
        )
        logs.append((now_ts(), "resolv", "   ✓ Acknowledgment composed"))
        return {"mode": "escalated", "message": ack, "ticket": ticket_meta}


# ════════════════════════════════════════════════════════
#  RUN FULL PIPELINE
# ════════════════════════════════════════════════════════
def run_agent_pipeline(query: str, priority: str, user_id: str = "EMP-AUTO", job_role: str = "Employee"):
    """
    Orchestrates all four agents with live UI updates.
    Returns final result dict.
    """
    logs = []
    logs.append((now_ts(), "sys", "🚀 Pipeline started — autonomous agent mode"))

    # Placeholder slots for live updates
    bar_slot = st.empty()
    log_slot = st.empty()
    status_slot = st.empty()

    states = {"triage":"active","kb":"idle","ticket":"idle","resolver":"idle"}
    bar_slot.markdown(render_pipeline_bar.__doc__ or "")  # trigger render
    render_pipeline_bar(states)  # initial render — overwrite below

    def refresh():
        bar_slot.empty()
        with bar_slot.container():
            render_pipeline_bar(states)
        log_slot.empty()
        with log_slot.container():
            render_log(logs)

    refresh()

    # ── Agent 1: Triage ──────────────────────────────────
    states = {"triage":"active","kb":"idle","ticket":"idle","resolver":"idle"}
    refresh()
    triage = agent_triage(query, priority, logs)
    states["triage"] = "done"
    refresh()

    # ── Agent 2: Knowledge ───────────────────────────────
    states["kb"] = "active"
    refresh()
    kb_result = agent_kb(query, triage, logs)
    states["kb"] = "done"
    refresh()

    # ── Agent 3: Ticket (only if KB couldn't answer) ─────
    ticket_meta = {}
    if kb_result.get("needs_ticket") or triage.get("route") in ("CREATE_TICKET","ESCALATE"):
        states["ticket"] = "active"
        refresh()
        ticket_meta = agent_ticket(query, triage, user_id, job_role, priority, logs)
        states["ticket"] = "done"
    else:
        states["ticket"] = "skipped"
    refresh()

    # ── Agent 4: Resolver ────────────────────────────────
    states["resolver"] = "active"
    refresh()
    final = agent_resolver(query, kb_result, ticket_meta, logs)
    states["resolver"] = "done"
    logs.append((now_ts(), "sys", f"✅ Pipeline complete"))
    refresh()

    bar_slot.empty()
    log_slot.empty()

    return {
        "triage": triage,
        "kb": kb_result,
        "ticket": ticket_meta,
        "final": final,
        "logs": logs,
        "states": states,
    }


# ════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("# 🤖 Employee Help Portal")
    st.markdown("<p style='color:#6b7280'>Powered by an autonomous 4-agent pipeline — Triage → Knowledge → Ticketing → Resolver</p>", unsafe_allow_html=True)
    st.markdown("---")

    pairs = load_qa_pairs()
    if pairs:
        st.success(f"📚 Knowledge base ready — {len(pairs)} Q&A pairs loaded.", icon="✅")
    else:
        st.warning("⚠️ PDF KB not loaded. Agents will fall back to Claude's general knowledge + Supabase.", icon="⚠️")

    st.markdown("### 💬 Describe your issue")
    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        question = st.text_input("", placeholder="e.g. I can't connect to VPN after the Windows update", label_visibility="collapsed")
    with col2:
        priority = st.selectbox("Priority", ["Medium","High","Low"], label_visibility="collapsed")
    with col3:
        run = st.button("▶ Run Agents", use_container_width=True)

    # Optional: employee details (used if a ticket gets raised)
    with st.expander("👤 Employee details (used if a ticket is created)", expanded=False):
        ec1, ec2 = st.columns(2)
        with ec1:
            emp_id = st.text_input("Employee ID", value="EMP-001")
        with ec2:
            job_role = st.selectbox("Job Role", ["Software Engineer","Data Analyst","QA Engineer","DevOps Engineer","Product Manager","HR / Operations","Other"])

    if run and question.strip():
        st.markdown("---")
        st.markdown("### 🔄 Running pipeline…")

        result = run_agent_pipeline(
            query=question.strip(),
            priority=priority,
            user_id=emp_id if emp_id.strip() else "EMP-AUTO",
            job_role=job_role,
        )

        final = result["final"]
        triage = result["triage"]
        kb = result["kb"]
        ticket = result["ticket"]

        # ── Pipeline bar (static final state) ───────────────────
        st.markdown("#### 🔁 Agent pipeline — complete")
        render_pipeline_bar(result["states"])

        # ── Log ─────────────────────────────────────────────────
        with st.expander("📋 Agent log", expanded=False):
            render_log(result["logs"])

        # ── Triage decision ─────────────────────────────────────
        st.markdown(
            f"<div style='margin:8px 0'>"
            f"<span class='decision-badge badge-route'>🎯 {triage.get('category','–')}</span>"
            f"<span class='decision-badge badge-route'>⚡ {triage.get('urgency','–')}</span>"
            f"<span class='decision-badge badge-route'>🔀 {triage.get('route','–')}</span>"
            f"<span class='decision-badge badge-route'>🎯 {int(triage.get('confidence',0)*100)}% confidence</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ── Final answer ─────────────────────────────────────────
        if final["mode"] == "resolved":
            source_label = {
                "learned":   "💡 Previously resolved ticket",
                "pdf":       "📚 PDF Knowledge Base",
                "claude_kb": "🧠 Claude Knowledge Base",
            }.get(final.get("source",""), "📚 Knowledge Base")

            st.markdown("#### ✅ Resolved by agents")
            st.markdown(f"<small style='color:#059669'><strong>Source: {source_label}</strong></small>", unsafe_allow_html=True)
            if kb.get("matched"):
                st.markdown(f"<small style='color:#6b7280'>📌 Matched: <em>{kb['matched'][:120]}</em></small>", unsafe_allow_html=True)

            box_class = "learned-box" if final.get("source") == "learned" else "answer-box"
            st.markdown(
                f"<div class='{box_class}'>{final['message'].replace(chr(10),'<br>')}</div>",
                unsafe_allow_html=True
            )

            st.markdown("---")
            col_a, col_b, _ = st.columns([1, 1, 4])
            with col_a:
                if st.button("👍 Helpful"): st.success("Great!")
            with col_b:
                if st.button("👎 Not helpful"):
                    st.session_state["show_ticket_form"] = True
                    st.session_state["ticket_query"] = question.strip()
                    st.warning("Sorry! Raise a manual ticket below.")

        else:
            # Escalated — ticket was created
            st.markdown("#### 🎫 Ticket created by agents")
            tid = ticket.get("db_id","–")
            assign = ticket.get("assign_to","IT Support")
            sla = ticket.get("sla","24h")
            tags = ", ".join(ticket.get("tags",[]))

            st.markdown(
                f"<div class='ticket-card'>"
                f"<div class='ticket-id-big'>TKT-{tid}</div>"
                f"<b>{ticket.get('title','Support Request')}</b><br><br>"
                f"{ticket.get('description','')}<br><br>"
                f"<span class='decision-badge badge-ticket'>👥 {assign}</span>"
                f"<span class='decision-badge badge-ticket'>⏱ SLA: {sla}</span>"
                f"<span class='decision-badge badge-ticket'>🏷 {tags}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            st.markdown(f"<div class='answer-box' style='margin-top:12px'>{final['message'].replace(chr(10),'<br>')}</div>", unsafe_allow_html=True)

    elif run:
        st.warning("Please enter your issue first.")

    # Manual ticket fallback
    if st.session_state.get("show_ticket_form"):
        st.markdown("---")
        st.markdown("### 📝 Manual Support Ticket")
        c1, c2 = st.columns(2)
        with c1:
            uid2 = st.text_input("👤 Employee ID *", placeholder="EMP-1042")
            role2 = st.selectbox("💼 Role *", ["Select…","Software Engineer","Data Analyst","QA Engineer","DevOps Engineer","Product Manager","HR / Operations","Other"])
        with c2:
            prio2 = st.selectbox("🚨 Priority *", ["Medium","High","Low"])
        desc2 = st.text_area("📋 Details", height=100)
        s1, s2, _ = st.columns([1,1,4])
        with s1:
            if st.button("🚀 Submit"):
                if uid2.strip() and role2 != "Select…":
                    q = st.session_state.get("ticket_query","") or desc2.strip()
                    t = db_create_ticket(uid2.strip(), role2, q, prio2)
                    st.success(f"Ticket #{t.get('id','–')} submitted!")
                    st.session_state["show_ticket_form"] = False
        with s2:
            if st.button("✖ Cancel"):
                st.session_state["show_ticket_form"] = False
                st.rerun()


def page_admin():
    ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")
    if not st.session_state.get("admin_logged_in"):
        st.markdown("# 🛡️ Admin Panel")
        col, _ = st.columns([1.5, 2.5])
        with col:
            pwd = st.text_input("Password", type="password")
            if st.button("Login →", use_container_width=True):
                if pwd == ADMIN_PWD:
                    st.session_state["admin_logged_in"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    c1, c2 = st.columns([5, 1])
    with c1: st.markdown("# 🛡️ Admin Dashboard")
    with c2:
        if st.button("Logout"):
            st.session_state["admin_logged_in"] = False
            st.rerun()

    try:
        stats = db_stats()
        cols = st.columns(4)
        for col, val, label, icon in zip(cols,
            [stats["total"],stats["open"],stats["in_progress"],stats["resolved"]],
            ["Total","Open","In Progress","Resolved"],["📋","🟡","🔵","🟢"]):
            with col:
                st.markdown(f"<div class='metric-card'><div style='font-size:28px'>{icon}</div><div class='metric-number'>{val}</div><div class='metric-label'>{label}</div></div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Stats error: {e}")

    st.markdown("---")
    c1, c2, _ = st.columns([1.5, 1.5, 3])
    with c1: sf = st.selectbox("Status", ["All","Open","In Progress","Resolved"])
    with c2: pf = st.selectbox("Priority", ["All","High","Medium","Low"])

    tickets = db_get_tickets(sf if sf != "All" else None)
    if pf != "All": tickets = [t for t in tickets if t.get("priority") == pf]
    if not tickets: st.info("No tickets.", icon="📭"); return

    st.markdown(f"**{len(tickets)} ticket(s)**")
    for t in tickets:
        tid = t.get("id")
        status = t.get("status","Open")
        priority = t.get("priority","Medium")
        created = t.get("created_at","")
        try:
            dt = datetime.fromisoformat(created.replace("Z","+00:00"))
            created_fmt = dt.strftime("%d %b %Y, %I:%M %p")
        except: created_fmt = created
        badge = {"Open":"badge-open","In Progress":"badge-inprogress","Resolved":"badge-resolved"}.get(status,"badge-open")
        prio = {"High":"prio-high","Medium":"prio-medium","Low":"prio-low"}.get(priority,"prio-medium")

        with st.expander(f"🎫 #{tid} — {t.get('user_id','?')} ({t.get('job_role','?')}) | {status} | {priority} | {created_fmt}"):
            st.markdown(f"<span class='{badge}'>{status}</span>&nbsp;<span class='{prio}'>{priority}</span>", unsafe_allow_html=True)
            st.markdown(f"**Employee:** {t.get('user_id','–')} &nbsp;|&nbsp; **Role:** {t.get('job_role','–')} &nbsp;|&nbsp; **Submitted:** {created_fmt}")
            st.markdown("**Problem:**")
            st.markdown(f"<div class='answer-box'>{t.get('query','–')}</div>", unsafe_allow_html=True)
            st.markdown("---")
            nc1, nc2 = st.columns(2)
            with nc1:
                new_status = st.selectbox("Update Status",["Open","In Progress","Resolved"],
                    index=["Open","In Progress","Resolved"].index(status), key=f"s_{tid}")
            with nc2:
                note = st.text_area("Admin Note / Solution", value=t.get("admin_note") or "",
                    key=f"n_{tid}", height=100,
                    placeholder="Solution saved to KB so agents can auto-answer similar questions.")
            bc1, bc2, _, _ = st.columns([1,1,1.5,1])
            with bc1:
                if st.button("💾 Save", key=f"save_{tid}", use_container_width=True):
                    try:
                        db_update_ticket(tid, new_status, note)
                        if new_status == "Resolved" and note.strip():
                            db = get_db()
                            if db:
                                existing = db.table("resolved_issues").select("id").eq("query", t.get("query","")).execute()
                                if not existing.data:
                                    db.table("resolved_issues").insert({"query":t.get("query",""),"solution":note.strip()}).execute()
                                    st.success("✅ Updated & solution saved to KB — agents will auto-answer similar queries!")
                                else:
                                    db.table("resolved_issues").update({"solution":note.strip()}).eq("query",t.get("query","")).execute()
                                    st.success("✅ Updated & KB entry refreshed!")
                        else:
                            st.success("Updated!")
                        st.rerun()
                    except Exception as e: st.error(str(e))
            with bc2:
                if st.button("🗑️ Delete", key=f"del_{tid}", use_container_width=True):
                    try: db_delete_ticket(tid); st.warning("Deleted."); st.rerun()
                    except Exception as e: st.error(str(e))


def page_setup():
    st.markdown("# ⚙️ Setup & Configuration")

    with st.expander("📁 Streamlit Secrets", expanded=True):
        st.code("""[secrets]
SUPABASE_URL     = "https://xxxx.supabase.co"
SUPABASE_KEY     = "eyJ..."
ADMIN_PASSWORD   = "your_password"
ANTHROPIC_API_KEY = "sk-ant-..."   # ← required for agent pipeline""", language="toml")

    with st.expander("🗄️ Supabase Tables", expanded=True):
        st.code(SCHEMA_SQL, language="sql")

    with st.expander("📦 Install Dependencies"):
        st.code("pip install streamlit supabase pdfplumber sentence-transformers requests anthropic", language="bash")

    st.markdown("---")
    st.markdown("### 🔌 Connection Status")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.secrets.get("SUPABASE_URL",""): st.success("✅ Supabase URL")
        else: st.error("❌ Supabase URL missing")
    with c2:
        if st.secrets.get("SUPABASE_KEY",""): st.success("✅ Supabase Key")
        else: st.error("❌ Supabase Key missing")
    with c3:
        if st.secrets.get("ANTHROPIC_API_KEY",""): st.success("✅ Anthropic API Key")
        else: st.error("❌ Anthropic API Key missing")

    st.markdown("---")
    if st.button("🧪 Test Database"):
        try:
            db = get_db()
            if db is None: st.error("Not configured.")
            else:
                db.table("tickets").select("id").limit(1).execute()
                st.success("✅ Database connected!")
        except Exception as e: st.error(f"Failed: {e}")

    if st.button("🤖 Test Agent Pipeline"):
        try:
            result = run_agent_pipeline("How do I reset my password?", "Low", "EMP-TEST", "Software Engineer")
            st.success(f"✅ Pipeline ran successfully! Mode: {result['final']['mode']}")
        except Exception as e: st.error(f"Pipeline failed: {e}")

    if st.button("📄 Test PDF + Q&A"):
        pdf_bytes = get_pdf_bytes()
        if not pdf_bytes: st.error("❌ Could not download PDF.")
        else:
            st.success(f"✅ PDF downloaded ({len(pdf_bytes)//1024} KB)")
            pairs = load_qa_pairs()
            if pairs:
                st.success(f"✅ {len(pairs)} Q&A pairs extracted!")
                with st.expander("Preview first 5"):
                    for q, a in pairs[:5]:
                        st.markdown(f"**Q:** {q[:200]}")
                        st.markdown(f"**A:** {a[:200]}")
                        st.markdown("---")
            else: st.error("❌ No Q&A pairs found.")

    st.markdown("---")
    st.markdown("### 🧠 Learned Answers (from resolved tickets)")
    if st.button("📋 View All Learned Answers"):
        db = get_db()
        if db is None: st.error("Supabase not configured.")
        else:
            rows = db.table("resolved_issues").select("*").order("created_at", desc=True).execute().data or []
            if rows:
                st.success(f"{len(rows)} learned answer(s) in database.")
                for row in rows:
                    with st.expander(f"🟢 {row['query'][:100]}"):
                        st.markdown(f"**Q:** {row['query']}")
                        st.markdown(f"**A:** {row['solution']}")
                        st.markdown(f"<small style='color:#6b7280'>Saved: {row.get('created_at','')[:10]}</small>", unsafe_allow_html=True)
            else:
                st.info("No learned answers yet. Resolve tickets with a note to build the KB.")


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🤖 HelpDesk Pro")
    st.markdown("<small style='opacity:0.7'>Autonomous Agent Pipeline</small>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio("Navigation", ["🔍 Employee Portal", "🛡️ Admin Panel", "⚙️ Setup / Config"])
    st.markdown("---")
    st.markdown("""
<small style='opacity:0.6'>
<b>Agents:</b><br>
🎯 Triage → classifies<br>
🧠 Knowledge → searches KB<br>
🎫 Ticketing → creates ticket<br>
⚡ Resolver → formats reply
</small>""", unsafe_allow_html=True)

if page == "🔍 Employee Portal":
    page_employee()
elif page == "🛡️ Admin Panel":
    page_admin()
elif page == "⚙️ Setup / Config":
    page_setup()
