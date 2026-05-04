import streamlit as st
import re
import io
import requests
import csv
from datetime import datetime, timezone, timedelta
from collections import Counter

IST = timezone(timedelta(hours=5, minutes=30))

def _to_ist(dt_str: str) -> str:
    try:
        normalised = dt_str.strip().replace(" ", "T").replace("Z", "+00:00")
        if "+" not in normalised[10:] and normalised[-6] != "+":
            normalised += "+00:00"
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return dt_str

st.set_page_config(
    page_title="HelpDesk Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ─── Global Reset ─────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
    font-size: 15px;
}

/* ─── App Background ───────────────────────────── */
.stApp {
    background: linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 30%, #c8f0f7 60%, #d4f1f9 100%);
    min-height: 100vh;
}

/* ─── Main Content Area ────────────────────────── */
.main .block-container {
    background: rgba(255, 255, 255, 0.0);
    padding: 2rem 2.5rem;
    max-width: 1200px;
}

/* ─── Sidebar ──────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0077b6 0%, #023e8a 100%);
    border-right: 1px solid rgba(0, 119, 182, 0.3);
}
section[data-testid="stSidebar"] > div {
    padding: 0;
}
section[data-testid="stSidebar"] * {
    color: rgba(255,255,255,0.9) !important;
}

/* ─── Sidebar Radio (Nav) ──────────────────────── */
section[data-testid="stSidebar"] .stRadio > div {
    gap: 2px;
}
section[data-testid="stSidebar"] .stRadio label {
    display: flex !important;
    align-items: center !important;
    padding: 10px 20px !important;
    border-radius: 0 !important;
    font-size: 13.5px !important;
    font-weight: 400 !important;
    color: rgba(255,255,255,0.65) !important;
    cursor: pointer;
    transition: all 0.2s ease;
    border-left: 2px solid transparent;
    margin: 0 !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    color: rgba(255,255,255,0.95) !important;
    background: rgba(255,255,255,0.12) !important;
}
section[data-testid="stSidebar"] input[type="radio"]:checked + label,
section[data-testid="stSidebar"] .stRadio [aria-checked="true"] {
    color: white !important;
    background: rgba(255,255,255,0.18) !important;
    border-left: 2px solid #90e0ef !important;
}
section[data-testid="stSidebar"] .stRadio input[type="radio"] {
    display: none !important;
}

/* ─── Headings ─────────────────────────────────── */
h1, h2, h3 {
    font-family: 'Outfit', sans-serif !important;
    letter-spacing: -0.5px;
    color: #023e8a !important;
}

/* ─── Cards & Boxes ────────────────────────────── */
.hd-card {
    background: rgba(255, 255, 255, 0.75);
    border: 1px solid rgba(0, 119, 182, 0.18);
    border-radius: 16px;
    padding: 20px 22px;
    margin-bottom: 12px;
    backdrop-filter: blur(12px);
    transition: border-color 0.2s ease, background 0.2s ease;
    box-shadow: 0 2px 12px rgba(0, 119, 182, 0.08);
}
.hd-card:hover {
    background: rgba(255, 255, 255, 0.92);
    border-color: rgba(0, 119, 182, 0.4);
}

.answer-box {
    background: linear-gradient(135deg, rgba(0,119,182,0.08), rgba(2,62,138,0.06));
    border-radius: 14px;
    padding: 20px 22px;
    border: 1px solid rgba(0,119,182,0.2);
    font-size: 14.5px;
    line-height: 1.8;
    color: #023e8a;
}
.no-answer-box {
    background: rgba(249, 115, 22, 0.07);
    border-radius: 14px;
    padding: 16px 20px;
    border: 1px solid rgba(249,115,22,0.25);
    color: #c2410c;
    font-size: 14px;
}
.learned-box {
    background: linear-gradient(135deg, rgba(16,185,129,0.09), rgba(5,150,105,0.05));
    border-radius: 14px;
    padding: 20px 22px;
    border: 1px solid rgba(16,185,129,0.25);
    font-size: 14.5px;
    line-height: 1.8;
    color: #065f46;
}

/* ─── Metric Cards ─────────────────────────────── */
.metric-card {
    background: rgba(255,255,255,0.78);
    border: 1px solid rgba(0,119,182,0.15);
    border-radius: 16px;
    padding: 22px 20px;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: transform 0.2s, border-color 0.2s;
    box-shadow: 0 2px 10px rgba(0,119,182,0.07);
}
.metric-card:hover {
    transform: translateY(-2px);
    border-color: rgba(0,119,182,0.35);
}
.metric-number {
    font-family: 'Outfit', sans-serif;
    font-size: 38px;
    font-weight: 700;
    line-height: 1;
    background: linear-gradient(135deg, #0077b6, #023e8a);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.metric-number-amber {
    background: linear-gradient(135deg, #d97706, #b45309);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.metric-number-blue {
    background: linear-gradient(135deg, #0284c7, #0369a1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.metric-number-green {
    background: linear-gradient(135deg, #059669, #047857);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.metric-number-red {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.metric-label {
    font-size: 12px;
    color: rgba(2, 62, 138, 0.5);
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 500;
}

/* ─── Badges ───────────────────────────────────── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.2px;
}
.badge-open    { background: rgba(217,119,6,0.12);  color: #92400e; border: 1px solid rgba(217,119,6,0.3); }
.badge-inprogress { background: rgba(2,132,199,0.12); color: #0c4a6e; border: 1px solid rgba(2,132,199,0.3); }
.badge-resolved { background: rgba(5,150,105,0.12); color: #064e3b; border: 1px solid rgba(5,150,105,0.3); }
.badge-overdue { background: rgba(220,38,38,0.10); color: #7f1d1d; border: 1px solid rgba(220,38,38,0.25); }

.prio-dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    margin-right: 5px;
}
.prio-high   { background: #ef4444; box-shadow: 0 0 6px rgba(239,68,68,0.4); }
.prio-medium { background: #f59e0b; box-shadow: 0 0 6px rgba(245,158,11,0.4); }
.prio-low    { background: #10b981; box-shadow: 0 0 6px rgba(16,185,129,0.4); }

/* ─── Ticket Row ───────────────────────────────── */
.ticket-row {
    background: rgba(255,255,255,0.65);
    border: 1px solid rgba(0,119,182,0.14);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
}
.ticket-row:hover {
    background: rgba(255,255,255,0.88);
    border-color: rgba(0,119,182,0.28);
}
.ticket-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #0077b6;
    font-weight: 500;
}
.ticket-query {
    font-size: 14px;
    font-weight: 500;
    color: #023e8a;
    line-height: 1.5;
    margin: 4px 0;
}
.ticket-meta {
    font-size: 11.5px;
    color: rgba(2,62,138,0.45);
}

/* ─── Gap Card ─────────────────────────────────── */
.gap-card {
    background: rgba(249,115,22,0.06);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 10px;
    border: 1px solid rgba(249,115,22,0.18);
}
.gap-count {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
    font-weight: 700;
    color: #c2410c;
}

/* ─── Timeline ─────────────────────────────────── */
.timeline-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
}

/* ─── Buttons ──────────────────────────────────── */
div.stButton > button {
    background: linear-gradient(135deg, #0077b6, #023e8a);
    color: white !important;
    border: none !important;
    border-radius: 10px;
    padding: 9px 22px;
    font-weight: 600;
    font-size: 13.5px;
    font-family: 'Outfit', sans-serif;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(0,119,182,0.3);
}
div.stButton > button:hover {
    background: linear-gradient(135deg, #005f99, #012a5e) !important;
    box-shadow: 0 6px 20px rgba(0,119,182,0.4);
    transform: translateY(-1px);
}
div.stButton > button:active {
    transform: translateY(0);
}

/* ─── Inputs & Selects ─────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: rgba(255,255,255,0.85) !important;
    border: 1px solid rgba(0,119,182,0.25) !important;
    border-radius: 10px !important;
    color: #023e8a !important;
    font-family: 'Outfit', sans-serif !important;
    transition: border-color 0.2s;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(0,119,182,0.6) !important;
    box-shadow: 0 0 0 3px rgba(0,119,182,0.1) !important;
}
.stTextInput > label,
.stTextArea > label,
.stSelectbox > label {
    color: rgba(2,62,138,0.7) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

/* ─── Expander ─────────────────────────────────── */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.72) !important;
    border: 1px solid rgba(0,119,182,0.18) !important;
    border-radius: 12px !important;
    color: #023e8a !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 13.5px !important;
}
.streamlit-expanderContent {
    background: rgba(255,255,255,0.55) !important;
    border: 1px solid rgba(0,119,182,0.12) !important;
    border-top: none !important;
    border-radius: 0 0 12px 12px !important;
}

/* ─── Success / Error / Warning / Info ─────────── */
.stSuccess, div[data-testid="stSuccess"] {
    background: rgba(5,150,105,0.09) !important;
    border: 1px solid rgba(5,150,105,0.28) !important;
    border-radius: 10px !important;
    color: #064e3b !important;
}
.stError, div[data-testid="stError"] {
    background: rgba(220,38,38,0.08) !important;
    border: 1px solid rgba(220,38,38,0.25) !important;
    border-radius: 10px !important;
    color: #7f1d1d !important;
}
.stWarning, div[data-testid="stWarning"] {
    background: rgba(217,119,6,0.09) !important;
    border: 1px solid rgba(217,119,6,0.28) !important;
    border-radius: 10px !important;
    color: #78350f !important;
}
.stInfo, div[data-testid="stInfo"] {
    background: rgba(2,132,199,0.09) !important;
    border: 1px solid rgba(2,132,199,0.25) !important;
    border-radius: 10px !important;
    color: #0c4a6e !important;
}

/* ─── Markdown text ────────────────────────────── */
.stMarkdown p, .stMarkdown li, .stMarkdown small {
    color: rgba(2,62,138,0.8) !important;
}
.stMarkdown strong {
    color: #023e8a !important;
}
.stMarkdown code {
    background: rgba(0,119,182,0.1) !important;
    color: #0c4a6e !important;
    border-radius: 5px;
    padding: 1px 5px;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px;
}

/* ─── Divider ──────────────────────────────────── */
hr {
    border-color: rgba(0,119,182,0.15) !important;
    margin: 1.5rem 0 !important;
}

/* ─── Download Button ──────────────────────────── */
div[data-testid="stDownloadButton"] > button {
    background: rgba(255,255,255,0.75) !important;
    color: #023e8a !important;
    border: 1px solid rgba(0,119,182,0.25) !important;
    border-radius: 10px !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background: rgba(255,255,255,0.95) !important;
    border-color: rgba(0,119,182,0.4) !important;
}

/* ─── Plotly charts ────────────────────────────── */
.js-plotly-plot .plotly {
    border-radius: 14px;
    overflow: hidden;
}

/* ─── Page header style ────────────────────────── */
.page-header {
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(0,119,182,0.15);
}
.page-title {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin: 0 0 4px 0;
    background: linear-gradient(135deg, #023e8a 60%, #0077b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.page-subtitle {
    font-size: 13.5px;
    color: rgba(2,62,138,0.5);
    margin: 0;
}

/* ─── Section label ────────────────────────────── */
.section-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: rgba(0,119,182,0.7);
    margin-bottom: 12px;
}

/* ─── Sidebar logo area ────────────────────────── */
.sidebar-logo {
    padding: 24px 20px 20px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    margin-bottom: 12px;
}
.sidebar-logo-mark {
    font-size: 19px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.5px;
}
.sidebar-logo-sub {
    font-size: 11px;
    color: rgba(255,255,255,0.5) !important;
    margin-top: 2px;
}
.sidebar-section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.4) !important;
    padding: 16px 20px 6px;
}
.sidebar-footer {
    padding: 16px 20px;
    border-top: 1px solid rgba(255,255,255,0.12);
    font-size: 11px;
    color: rgba(255,255,255,0.35) !important;
}

/* ─── Toast override ───────────────────────────── */
div[data-testid="stToast"] {
    background: rgba(255,255,255,0.95) !important;
    border: 1px solid rgba(0,119,182,0.3) !important;
    border-radius: 12px !important;
    color: #023e8a !important;
    backdrop-filter: blur(20px);
}

/* ─── Spinner ──────────────────────────────────── */
.stSpinner > div {
    border-color: #0077b6 transparent transparent transparent !important;
}

/* ─── Checkbox ─────────────────────────────────── */
.stCheckbox > label {
    color: rgba(2,62,138,0.75) !important;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  IMPORT APPROVAL PIPELINE
# ════════════════════════════════════════════════════════
try:
    from approval_pipeline import page_approval_pipeline
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False


# ════════════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════════════
try:
    from supabase import create_client
    SUPABASE_OK = True
except ImportError:
    SUPABASE_OK = False

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    job_role    TEXT NOT NULL,
    query       TEXT NOT NULL,
    priority    TEXT NOT NULL DEFAULT 'Medium',
    status      TEXT NOT NULL DEFAULT 'Open',
    admin_note  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resolved_issues (
    id         BIGSERIAL PRIMARY KEY,
    query      TEXT NOT NULL,
    solution   TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS failed_queries (
    id         BIGSERIAL PRIMARY KEY,
    query      TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE tickets DISABLE ROW LEVEL SECURITY;
ALTER TABLE resolved_issues DISABLE ROW LEVEL SECURITY;
ALTER TABLE failed_queries DISABLE ROW LEVEL SECURITY;
"""

@st.cache_resource(show_spinner=False)
def get_db():
    if not SUPABASE_OK:
        return None
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if url and key:
        return create_client(url, key)
    return None

def db_create_ticket(user_id, job_role, query, priority):
    db = get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    row = {"user_id": user_id, "job_role": job_role, "query": query, "priority": priority, "status": "Open"}
    try:
        result = db.table("tickets").insert(row).execute()
        if result.data:
            ticket = result.data[0]
            st.toast(f"🎫 Ticket #{ticket.get('id')} saved to Supabase!", icon="☁️")
            return ticket
        raise Exception("No data returned from insert")
    except Exception as e:
        raise Exception(f"Insert failed: {e}")

def db_get_tickets(status_filter=None):
    db = get_db()
    if db is None:
        return []
    try:
        q = db.table("tickets").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        return q.execute().data or []
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return []

def db_update_ticket(tid, status, note):
    db = get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    try:
        db.table("tickets").update({"status": status, "admin_note": note}).eq("id", tid).execute()
        st.toast(f"✏️ Ticket #{tid} updated → {status}", icon="☁️")
    except Exception as e:
        raise Exception(f"Update failed: {e}")

def db_delete_ticket(tid):
    db = get_db()
    if db:
        try:
            db.table("tickets").delete().eq("id", tid).execute()
            st.toast(f"🗑️ Ticket #{tid} deleted", icon="☁️")
        except Exception as e:
            raise Exception(f"Delete failed: {e}")

def db_log_failed_query(query: str):
    db = get_db()
    if db:
        try:
            db.table("failed_queries").insert({"query": query}).execute()
            st.toast("📋 Unanswered question logged", icon="☁️")
        except Exception:
            pass

def db_stats():
    tickets = db_get_tickets()
    now = datetime.now(timezone.utc)
    overdue = sum(
        1 for t in tickets
        if t["status"] == "Open" and
        (now - datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))) > timedelta(hours=24)
    )
    return {
        "total": len(tickets),
        "open": sum(1 for t in tickets if t["status"] == "Open"),
        "in_progress": sum(1 for t in tickets if t["status"] == "In Progress"),
        "resolved": sum(1 for t in tickets if t["status"] == "Resolved"),
        "overdue": overdue,
    }

def is_overdue(created_at_str: str) -> bool:
    try:
        created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - created) > timedelta(hours=24)
    except Exception:
        return False

def auto_save_note_to_resolved(ticket_query: str, note: str):
    db = get_db()
    if db is None or not note.strip() or not ticket_query.strip():
        return False
    try:
        existing = db.table("resolved_issues").select("id").eq("query", ticket_query).execute()
        if not existing.data:
            db.table("resolved_issues").insert({"query": ticket_query, "solution": note.strip()}).execute()
            st.toast("🧠 New learned answer saved!", icon="☁️")
        else:
            db.table("resolved_issues").update({"solution": note.strip()}).eq("query", ticket_query).execute()
            st.toast("🧠 Learned answer updated", icon="☁️")
        return True
    except Exception:
        return False


# ════════════════════════════════════════════════════════
#  LEARNED ANSWERS LOOKUP
# ════════════════════════════════════════════════════════
_STOP_WORDS = {
    "what","is","are","the","a","an","of","in","on","at","to","for","and","or",
    "how","why","when","where","who","does","do","can","could","would","should",
    "explain","tell","me","about","difference","between","use","using"
}

def _normalize(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

def _content_words(text: str) -> set:
    words = re.findall(r'\b[a-z]{2,}\b', text.lower())
    return {w for w in words if w not in _STOP_WORDS}

def _keyword_score(query: str, stored_query: str) -> float:
    q_norm = _normalize(query)
    s_norm = _normalize(stored_query)
    if q_norm == s_norm:
        return 1.0
    q_words = _content_words(query)
    s_words = _content_words(stored_query)
    if not q_words or not s_words:
        return 0.0
    return len(q_words & s_words) / len(q_words | s_words)

_LEARNED_THRESHOLD = 0.55

def check_learned_answers(query: str):
    db = get_db()
    if db is None:
        return None
    best_score, best_solution, best_matched = 0.0, None, None
    try:
        resp = db.table("tickets").select("query, admin_note").not_.is_("admin_note", "null").execute()
        for row in (resp.data or []):
            note = (row.get("admin_note") or "").strip()
            q = (row.get("query") or "").strip()
            if not note or not q:
                continue
            score = _keyword_score(query, q)
            if score > best_score:
                best_score, best_solution, best_matched = score, note, q
    except Exception:
        pass
    try:
        resp2 = db.table("resolved_issues").select("query, solution").execute()
        for row in (resp2.data or []):
            sol = (row.get("solution") or "").strip()
            q = (row.get("query") or "").strip()
            if not sol or not q:
                continue
            score = _keyword_score(query, q)
            if score > best_score:
                best_score, best_solution, best_matched = score, sol, q
    except Exception:
        pass
    if best_solution and best_score >= _LEARNED_THRESHOLD:
        return {"solution": best_solution, "matched_query": best_matched, "score": best_score, "source": "learned"}
    return None


# ════════════════════════════════════════════════════════
#  PDF DOWNLOAD
# ════════════════════════════════════════════════════════
_PDF_PUBLIC_URL = "https://jvulbphmksdebkkkhgvh.supabase.co/storage/v1/object/public/Documents/questions.pdf"

@st.cache_resource(show_spinner="📄 Downloading PDF from Supabase…")
def get_pdf_bytes(_v=3):
    try:
        supabase_key = st.secrets.get("SUPABASE_KEY", "")
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        resp = requests.get(_PDF_PUBLIC_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        st.warning(f"PDF download failed: {e}")
        return None

@st.cache_resource(show_spinner="📄 Extracting Q&A from PDF…")
def load_qa_pairs():
    pdf_bytes = get_pdf_bytes()
    if not pdf_bytes:
        return []
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        st.warning(f"pdfplumber failed: {e}")
        return []
    text = text.lower()
    qa_pairs = []
    for part in re.split(r'q\.', text):
        if "answer" not in part:
            continue
        try:
            q_part, a_part = part.split("answer", 1)
            question = q_part.strip()
            answer = a_part.strip()
            if "enroll" in answer or "course" in answer:
                continue
            if len(answer) < 30 or len(question) < 5:
                continue
            qa_pairs.append((question, answer))
        except Exception:
            continue
    return qa_pairs


# ════════════════════════════════════════════════════════
#  SEMANTIC SEARCH MODEL
# ════════════════════════════════════════════════════════
_Q_THRESHOLD   = 0.40
_A_THRESHOLD   = 0.45
_ANSWER_WEIGHT = 0.85

@st.cache_resource(show_spinner="🧠 Loading semantic search model…")
def load_model_and_embeddings():
    try:
        from sentence_transformers import SentenceTransformer, util
        pairs = load_qa_pairs()
        if not pairs:
            return None, None, None, None, None
        model = SentenceTransformer('multi-qa-mpnet-base-dot-v1')
        questions = [q for q, _ in pairs]
        answers   = [a for _, a in pairs]
        q_embeddings = model.encode(questions, convert_to_tensor=True, show_progress_bar=False)
        a_embeddings = model.encode(answers,   convert_to_tensor=True, show_progress_bar=False)
        return model, q_embeddings, a_embeddings, pairs, util
    except Exception as e:
        st.warning(f"Semantic model error: {e}")
        return None, None, None, None, None

def answer_question(query: str) -> dict:
    model, q_embeddings, a_embeddings, pairs, util = load_model_and_embeddings()
    if model is not None and q_embeddings is not None and a_embeddings is not None and pairs is not None and util is not None:
        try:
            query_embedding = model.encode(query.lower(), convert_to_tensor=True)
            q_scores = util.cos_sim(query_embedding, q_embeddings)[0]
            best_q_idx   = int(q_scores.argmax())
            best_q_score = float(q_scores[best_q_idx])
            a_scores = util.cos_sim(query_embedding, a_embeddings)[0]
            best_a_idx   = int(a_scores.argmax())
            best_a_score = float(a_scores[best_a_idx])
            weighted_a_score = best_a_score * _ANSWER_WEIGHT
            if best_q_score >= _Q_THRESHOLD or best_a_score >= _A_THRESHOLD:
                if best_q_score >= weighted_a_score:
                    chosen_idx, chosen_score, match_source = best_q_idx, best_q_score, "question"
                else:
                    chosen_idx, chosen_score, match_source = best_a_idx, best_a_score, "answer"
                question, answer = pairs[chosen_idx]
                return {
                    "found": True, "answer": answer.strip(), "matched": question.strip(),
                    "score": chosen_score, "match_src": match_source,
                    "pdf_error": False, "source": "pdf"
                }
        except Exception:
            pass

    learned = check_learned_answers(query)
    if learned:
        return {
            "found": True, "answer": learned["solution"], "matched": learned["matched_query"],
            "score": learned["score"], "match_src": "learned", "pdf_error": False,
            "source": learned.get("source", "learned")
        }

    pdf_unavailable = (model is None or q_embeddings is None)
    return {
        "found": False, "answer": "", "matched": "", "score": 0,
        "match_src": "none", "pdf_error": pdf_unavailable, "source": "none"
    }

def tickets_to_csv(tickets: list) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id","user_id","job_role","query","priority","status","admin_note","created_at"])
    writer.writeheader()
    for t in tickets:
        writer.writerow({k: t.get(k, "") for k in writer.fieldnames})
    return output.getvalue().encode("utf-8")


# ════════════════════════════════════════════════════════
#  PAGE: EMPLOYEE PORTAL
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("""
    <div class="page-header">
        <div class="page-title">Employee Help Portal</div>
        <div class="page-subtitle">Ask any question — powered by AI semantic search across your knowledge base</div>
    </div>
    """, unsafe_allow_html=True)

    pairs = load_qa_pairs()
    if len(pairs) == 0:
        st.error("⚠️ PDF knowledge base could not be loaded.")
    else:
        st.markdown(f"""
        <div class="hd-card" style="display:flex; align-items:center; gap:14px; padding:14px 20px;">
            <span style="font-size:22px;">📚</span>
            <div>
                <div style="font-size:13.5px; font-weight:600; color:#023e8a;">{len(pairs)} Q&amp;A pairs loaded</div>
                <div style="font-size:12px; color:rgba(2,62,138,0.5);">Semantic AI search active · multi-qa-mpnet-base-dot-v1</div>
            </div>
            <span style="margin-left:auto; background:rgba(5,150,105,0.12); color:#065f46; font-size:11px; font-weight:600; padding:3px 10px; border-radius:20px; border:1px solid rgba(5,150,105,0.25);">● Live</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div class='section-label' style='margin-top:24px;'>Search</div>", unsafe_allow_html=True)
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("", placeholder="e.g. What is the difference between a list and a tuple?", label_visibility="collapsed")
    with col2:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        search = st.button("🔎  Search", use_container_width=True)

    if search and question.strip():
        with st.spinner("Searching knowledge base…"):
            result = answer_question(question.strip())

        if result.get("pdf_error") and not result["found"]:
            st.error("❌ Knowledge base unavailable. Please raise a support ticket.")
            db_log_failed_query(question.strip())
            st.session_state["show_ticket"] = True
            st.session_state["ticket_query"] = question.strip()

        elif result["found"]:
            source    = result.get("source", "pdf")
            match_src = result.get("match_src", "question")

            if source == "learned":
                st.markdown(f"""
                <div style="margin:16px 0 6px;">
                    <span style="font-size:12px; color:#059669; font-weight:600;">✓ Answer found</span>
                    <span style="font-size:11px; color:rgba(2,62,138,0.45); margin-left:10px;">Source: previously resolved ticket · {result['score']:.0%} match</span>
                </div>
                <div class="learned-box">{result['answer']}</div>
                """, unsafe_allow_html=True)
            else:
                match_label = "matched via question" if match_src == "question" else "matched via answer content"
                st.markdown(f"""
                <div style="margin:16px 0 6px;">
                    <span style="font-size:12px; color:#0077b6; font-weight:600;">✓ Answer found</span>
                    <span style="font-size:11px; color:rgba(2,62,138,0.45); margin-left:10px;">PDF Knowledge Base · {match_label} · score {result['score']:.2f}</span>
                </div>
                <div class="answer-box">{result['answer']}</div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            col_a, col_b, _ = st.columns([1, 1, 4])
            with col_a:
                if st.button("👍  Helpful", key="emp_helpful"):
                    st.success("Great! Glad it helped.")
            with col_b:
                if st.button("👎  Not helpful", key="emp_not_helpful"):
                    db_log_failed_query(question.strip())
                    st.session_state["show_ticket"] = True
                    st.session_state["ticket_query"] = question.strip()
                    st.warning("Sorry! Please raise a ticket below.")
        else:
            st.markdown(f"""
            <div class="no-answer-box" style="margin:16px 0;">
                ⚠️ No answer found in the knowledge base. Please fill in the ticket form below and our team will help you.
            </div>
            """, unsafe_allow_html=True)
            db_log_failed_query(question.strip())
            st.session_state["show_ticket"] = True
            st.session_state["ticket_query"] = question.strip()

    elif search:
        st.warning("Please enter a question first.")

    st.markdown("<hr>", unsafe_allow_html=True)

    if st.session_state.get("show_ticket", False):
        st.markdown("<div class='section-label'>Raise a Support Ticket</div>", unsafe_allow_html=True)

        original_question = st.session_state.get("ticket_query", "")
        if original_question:
            st.markdown(f"""
            <div class="hd-card" style="padding:12px 18px; margin-bottom:16px;">
                <span style="font-size:11px; color:#0077b6; font-weight:600;">YOUR SEARCH</span>
                <div style="font-size:13.5px; color:#023e8a; margin-top:4px;">{original_question}</div>
            </div>
            """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            user_id  = st.text_input("Employee ID", placeholder="e.g. EMP-1042", key="emp_user_id")
            job_role = st.selectbox("Job Role", ["Select…","Software Engineer","Data Analyst","QA Engineer","DevOps Engineer","Product Manager","HR / Operations","Other"], key="emp_job_role")
        with c2:
            priority = st.selectbox("Priority", ["Medium","High","Low"], key="emp_priority")
            st.markdown("""
            <div style="margin-top:8px; padding:10px 14px; background:rgba(2,132,199,0.07); border-radius:10px; border:1px solid rgba(2,132,199,0.18);">
                <div style="font-size:11.5px; color:rgba(2,62,138,0.55);">⏱ Tickets are usually resolved within 24 hours</div>
            </div>
            """, unsafe_allow_html=True)

        query_text = st.text_area("Describe your problem in detail", value="", placeholder="Add more context about your issue…", height=120, key="emp_query_text")

        col_sub, col_cancel, _ = st.columns([1, 1, 4])
        with col_sub:
            if st.button("🚀  Submit Ticket", use_container_width=True, key="emp_submit"):
                errors = []
                if not user_id.strip(): errors.append("Employee ID required.")
                if job_role == "Select…": errors.append("Select your job role.")
                if not original_question and not query_text.strip(): errors.append("Problem description required.")
                for e in errors:
                    st.error(e)
                if not errors:
                    final_query = original_question if original_question else query_text.strip()
                    try:
                        t = db_create_ticket(user_id.strip(), job_role, final_query, priority)
                        st.success(f"✅ Ticket #{t.get('id', '–')} submitted! Our team will respond shortly.")
                        st.session_state["show_ticket"] = False
                    except Exception as ex:
                        st.error(f"Failed: {ex}")
        with col_cancel:
            if st.button("✖  Cancel", use_container_width=True, key="emp_cancel"):
                st.session_state["show_ticket"] = False
                st.rerun()


# ════════════════════════════════════════════════════════
#  PAGE: ADMIN PANEL
# ════════════════════════════════════════════════════════
def page_admin():
    ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")
    if not st.session_state.get("admin_logged_in"):
        st.markdown("""
        <div class="page-header">
            <div class="page-title">Admin Panel</div>
            <div class="page-subtitle">Restricted access — enter your password to continue</div>
        </div>
        """, unsafe_allow_html=True)
        col, _ = st.columns([1.5, 2.5])
        with col:
            pwd = st.text_input("Password", type="password", key="admin_pwd_input")
            if st.button("Login →", use_container_width=True, key="admin_login_btn"):
                if pwd == ADMIN_PWD:
                    st.session_state["admin_logged_in"] = True
                    st.toast("🛡️ Admin logged in successfully", icon="✅")
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown("""
        <div class="page-header">
            <div class="page-title">Admin Dashboard</div>
            <div class="page-subtitle">Review, update and manage all support tickets</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("Logout", key="admin_logout_btn"):
            st.session_state["admin_logged_in"] = False
            st.toast("👋 Logged out", icon="🔒")
            st.rerun()

    # ── Stats ────────────────────────────────────────────
    try:
        stats = db_stats()
        metric_data = [
            (stats["total"],       "Total",       "metric-number"),
            (stats["open"],        "Open",        "metric-number metric-number-amber"),
            (stats["in_progress"], "In Progress", "metric-number metric-number-blue"),
            (stats["resolved"],    "Resolved",    "metric-number metric-number-green"),
            (stats["overdue"],     "Overdue",     "metric-number metric-number-red"),
        ]
        cols = st.columns(5)
        for col, (val, label, cls) in zip(cols, metric_data):
            with col:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="{cls}">{val}</div>
                    <div class="metric-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Stats error: {e}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Filters ──────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1])
    with c1:
        sf = st.selectbox("Status", ["All","Open","In Progress","Resolved","Overdue"], key="admin_filter_status")
    with c2:
        pf = st.selectbox("Priority", ["All","High","Medium","Low"], key="admin_filter_priority")
    with c3:
        search_term = st.text_input("Search tickets", placeholder="keyword / employee ID", key="admin_search_term")
    with c4:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        export_btn = st.button("📥 Export CSV", use_container_width=True, key="admin_export_btn")

    try:
        tickets = db_get_tickets(sf if sf not in ["All","Overdue"] else None)
    except Exception as e:
        st.error(f"DB error: {e}")
        return

    if sf == "Overdue":
        tickets = [t for t in tickets if t.get("status") == "Open" and is_overdue(t.get("created_at",""))]
    if pf != "All":
        tickets = [t for t in tickets if t.get("priority") == pf]
    if search_term.strip():
        kw = search_term.strip().lower()
        tickets = [t for t in tickets if kw in t.get("query","").lower() or kw in t.get("user_id","").lower()]

    if export_btn:
        all_tickets = db_get_tickets()
        csv_bytes = tickets_to_csv(all_tickets)
        st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="helpdesk_tickets.csv", mime="text/csv", key="admin_download_csv")
        st.toast("📥 CSV exported", icon="✅")

    if not tickets:
        st.markdown("""
        <div class="hd-card" style="text-align:center; padding:40px;">
            <div style="font-size:32px; margin-bottom:12px;">📭</div>
            <div style="font-size:14px; color:rgba(2,62,138,0.5);">No tickets found matching your filters</div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"<div class='section-label'>{len(tickets)} Ticket(s)</div>", unsafe_allow_html=True)

    for t in tickets:
        tid    = t.get("id")
        status = t.get("status", "Open")
        priority = t.get("priority", "Medium")
        created  = t.get("created_at", "")
        overdue  = is_overdue(created) and status == "Open"
        ticket_query = t.get("query", "")

        try:
            created_fmt = _to_ist(created)
        except Exception:
            created_fmt = created

        badge_class = "badge-overdue" if overdue else {
            "Open": "badge-open",
            "In Progress": "badge-inprogress",
            "Resolved": "badge-resolved"
        }.get(status, "badge-open")
        display_status = "OVERDUE" if overdue else status

        prio_dot_class = {"High": "prio-high", "Medium": "prio-medium", "Low": "prio-low"}.get(priority, "prio-medium")

        with st.expander(f"#{tid}  ·  {t.get('user_id','?')}  ·  {ticket_query[:70]}{'…' if len(ticket_query)>70 else ''}"):
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap;">
                <span class="badge {badge_class}">{display_status}</span>
                <span style="display:inline-flex; align-items:center; font-size:12px; color:rgba(2,62,138,0.55);">
                    <span class="prio-dot {prio_dot_class}"></span>{priority} priority
                </span>
                <span style="font-size:12px; color:rgba(2,62,138,0.4); margin-left:auto;">
                    {t.get('user_id','–')} · {t.get('job_role','–')} · {created_fmt}
                </span>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div style="margin-bottom:14px; padding:12px 16px; background:rgba(255,255,255,0.55); border-radius:10px; border:1px solid rgba(0,119,182,0.12);">
                <div style="font-size:11px; font-weight:600; letter-spacing:0.8px; text-transform:uppercase; color:rgba(2,62,138,0.4); margin-bottom:8px;">Timeline</div>
                <div style="font-size:12.5px; color:rgba(2,62,138,0.7);">
                    <span class="timeline-dot" style="background:#0077b6;"></span><strong>Opened</strong> — {created_fmt}
                </div>
                {"<div style='font-size:12.5px; color:rgba(2,62,138,0.7); margin-top:6px;'><span class='timeline-dot' style='background:#0284c7;'></span><strong>In Progress</strong> — being worked on</div>" if status == "In Progress" else ""}
                {"<div style='font-size:12.5px; color:rgba(2,62,138,0.7); margin-top:6px;'><span class='timeline-dot' style='background:#059669;'></span><strong>Resolved</strong> ✅</div>" if status == "Resolved" else ""}
                {"<div style='font-size:12.5px; color:#b91c1c; margin-top:6px;'><span class='timeline-dot' style='background:#dc2626;'></span><strong>⚠️ Overdue</strong> — open for more than 24 hours</div>" if overdue else ""}
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div style="font-size:11px; font-weight:600; letter-spacing:0.8px; text-transform:uppercase; color:rgba(2,62,138,0.4); margin-bottom:6px;">Problem</div>
            <div class="answer-box" style="margin-bottom:16px;">{ticket_query}</div>
            """, unsafe_allow_html=True)

            nc1, nc2 = st.columns(2)
            with nc1:
                new_status = st.selectbox(
                    "Update Status",
                    ["Open","In Progress","Resolved"],
                    index=["Open","In Progress","Resolved"].index(status),
                    key=f"admin_s_{tid}"
                )
            with nc2:
                prefill_note = st.session_state.pop(f"admin_prefill_{tid}", None)
                default_note = prefill_note if prefill_note is not None else (t.get("admin_note") or "")
                note = st.text_area(
                    "Admin Note / Solution",
                    value=default_note,
                    key=f"admin_n_{tid}",
                    height=100,
                    placeholder="Write solution here…"
                )

            bc1, bc2, _, _ = st.columns([1, 1, 1.5, 1])
            with bc1:
                if st.button("💾  Save", key=f"admin_save_{tid}", use_container_width=True):
                    try:
                        db_update_ticket(tid, new_status, note)
                        if note.strip():
                            auto_save_note_to_resolved(ticket_query, note)
                        st.success("✅ Ticket updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with bc2:
                if st.button("🗑️  Delete", key=f"admin_del_{tid}", use_container_width=True):
                    try:
                        db_delete_ticket(tid)
                        st.warning("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))


# ════════════════════════════════════════════════════════
#  PAGE: ANALYTICS
# ════════════════════════════════════════════════════════
def page_analytics():
    if not st.session_state.get("admin_logged_in"):
        st.warning("Please log in via the Admin Panel first.")
        return

    st.markdown("""
    <div class="page-header">
        <div class="page-title">Analytics Dashboard</div>
        <div class="page-subtitle">Ticket trends, resolution rates and team performance</div>
    </div>
    """, unsafe_allow_html=True)

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        import pandas as pd
    except ImportError:
        st.error("Please install plotly and pandas.")
        return

    tickets = db_get_tickets()
    if not tickets:
        st.info("No ticket data yet.")
        return

    df = pd.DataFrame(tickets)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["created_at_ist"] = df["created_at"] + pd.Timedelta(hours=5, minutes=30)
    df["date"] = df["created_at_ist"].dt.strftime("%d %b %Y")

    resolved = df[df["status"] == "Resolved"]
    resolution_rate = round(len(resolved) / len(df) * 100, 1) if len(df) else 0

    metric_data = [
        (len(df),          "Total tickets",  "metric-number"),
        (f"{resolution_rate}%", "Resolution rate", "metric-number metric-number-green"),
        (len(df[df["status"]=="Open"]), "Open tickets", "metric-number metric-number-amber"),
        (len(df[df["priority"]=="High"]), "High priority", "metric-number metric-number-red"),
    ]
    cols = st.columns(4)
    for col, (val, label, cls) in zip(cols, metric_data):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="{cls}">{val}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Light theme plotly layout
    plot_layout = dict(
        paper_bgcolor="rgba(255,255,255,0.6)",
        plot_bgcolor="rgba(255,255,255,0.4)",
        font=dict(family="Outfit", color="rgba(2,62,138,0.7)", size=12),
        margin=dict(t=20, b=60, l=40, r=20),
        xaxis=dict(gridcolor="rgba(0,119,182,0.08)", linecolor="rgba(0,119,182,0.15)"),
        yaxis=dict(gridcolor="rgba(0,119,182,0.08)", linecolor="rgba(0,119,182,0.15)"),
    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("<div class='section-label'>Tickets per day</div>", unsafe_allow_html=True)
        daily = df.groupby("date").size().reset_index(name="count")
        fig1 = px.bar(daily, x="date", y="count", text="count",
                      color_discrete_sequence=["#0077b6"])
        fig1.update_traces(textposition="outside", marker_line_width=0,
                           marker_color="#0077b6", opacity=0.85)
        fig1.update_layout(**plot_layout, bargap=0.4,
                           xaxis=dict(**plot_layout["xaxis"], tickangle=-35, type="category", tickfont=dict(size=10)),
                           yaxis=dict(**plot_layout["yaxis"], tickformat="d", dtick=1))
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.markdown("<div class='section-label'>Status breakdown</div>", unsafe_allow_html=True)
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig2 = px.pie(status_counts, names="status", values="count", hole=0.45,
                      color="status",
                      color_discrete_map={"Open":"#d97706","In Progress":"#0284c7","Resolved":"#059669"})
        fig2.update_traces(textinfo="label+percent", textfont=dict(size=12, color="rgba(2,62,138,0.85)"),
                           marker=dict(line=dict(color="rgba(255,255,255,0.5)", width=2)))
        fig2.update_layout(paper_bgcolor="rgba(255,255,255,0.6)",
                           font=dict(family="Outfit", color="rgba(2,62,138,0.7)"),
                           margin=dict(t=20, b=20, l=20, r=20),
                           legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                                       font=dict(color="rgba(2,62,138,0.6)")))
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("<div class='section-label'>Tickets by priority</div>", unsafe_allow_html=True)
        prio_order = ["High","Medium","Low"]
        prio_counts = df["priority"].value_counts().reindex(prio_order, fill_value=0).reset_index()
        prio_counts.columns = ["priority","count"]
        fig3 = px.bar(prio_counts, x="priority", y="count", color="priority", text="count",
                      color_discrete_map={"High":"#dc2626","Medium":"#d97706","Low":"#059669"},
                      category_orders={"priority": prio_order})
        fig3.update_traces(textposition="outside", marker_line_width=0, opacity=0.85)
        fig3.update_layout(**plot_layout, showlegend=False, bargap=0.45,
                           yaxis=dict(**plot_layout["yaxis"], tickformat="d", dtick=1))
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown("<div class='section-label'>Tickets by job role</div>", unsafe_allow_html=True)
        role_counts = df["job_role"].value_counts().reset_index()
        role_counts.columns = ["role","count"]
        fig4 = px.bar(role_counts, x="count", y="role", orientation="h", text="count",
                      color_discrete_sequence=["#0284c7"])
        fig4.update_traces(textposition="outside", marker_line_width=0, opacity=0.85)
        fig4.update_layout(**plot_layout,
                           xaxis=dict(**plot_layout["xaxis"], tickformat="d", dtick=1),
                           yaxis=dict(**plot_layout["yaxis"]),
                           bargap=0.35,
                           height=max(280, len(role_counts)*50),
                           margin=dict(t=20, b=20, l=140, r=20))
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Export</div>", unsafe_allow_html=True)
    csv_bytes = tickets_to_csv(tickets)
    st.download_button("⬇️ Download All Tickets as CSV", data=csv_bytes,
                       file_name="helpdesk_tickets.csv", mime="text/csv",
                       key="analytics_download_csv")


# ════════════════════════════════════════════════════════
#  PAGE: KNOWLEDGE GAP REPORT
# ════════════════════════════════════════════════════════
def page_knowledge_gap():
    if not st.session_state.get("admin_logged_in"):
        st.warning("Please log in via the Admin Panel first.")
        return

    st.markdown("""
    <div class="page-header">
        <div class="page-title">Knowledge Gap Report</div>
        <div class="page-subtitle">Questions employees asked that the system couldn't answer</div>
    </div>
    """, unsafe_allow_html=True)

    db = get_db()
    if db is None:
        st.error("Supabase not configured.")
        return

    try:
        rows = db.table("failed_queries").select("query, created_at").order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"Error: {e}")
        return

    if not rows:
        st.markdown("""
        <div class="hd-card" style="text-align:center; padding:40px;">
            <div style="font-size:32px; margin-bottom:12px;">🎉</div>
            <div style="font-size:15px; color:#023e8a; font-weight:500;">No knowledge gaps yet!</div>
            <div style="font-size:13px; color:rgba(2,62,138,0.45); margin-top:6px;">Every question has been answered.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    queries = [r["query"] for r in rows]
    unique  = len(set(q.lower().strip() for q in queries))

    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-number">{len(queries)}</div>
            <div class="metric-label">Total unanswered</div>
        </div>
        """, unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-number metric-number-amber">{unique}</div>
            <div class="metric-label">Unique questions</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>All Unanswered Questions</div>", unsafe_allow_html=True)

    for i, row in enumerate(rows, 1):
        try:
            date_fmt = _to_ist(row.get("created_at",""))
        except Exception:
            date_fmt = row.get("created_at","")
        st.markdown(f"""
        <div class="gap-card">
            <span class="gap-count">#{i}</span>
            <span style="font-size:14px; font-weight:500; color:#023e8a; margin-left:10px;">{row['query']}</span>
            <div style="font-size:11px; color:rgba(2,62,138,0.4); margin-top:6px;">Asked on {date_fmt}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Most Requested Missing Topics</div>", unsafe_allow_html=True)

    all_words = []
    for q in queries:
        all_words.extend(_content_words(q))
    word_freq = Counter(all_words).most_common(15)

    if word_freq:
        try:
            import plotly.express as px
            import pandas as pd
            wdf = pd.DataFrame(word_freq, columns=["keyword","count"])
            fig = px.bar(wdf, x="count", y="keyword", orientation="h", text="count",
                         color_discrete_sequence=["#0077b6"])
            fig.update_layout(
                paper_bgcolor="rgba(255,255,255,0.6)",
                plot_bgcolor="rgba(255,255,255,0.4)",
                font=dict(family="Outfit", color="rgba(2,62,138,0.7)", size=12),
                margin=dict(t=10, l=120, r=20, b=20),
                height=max(280, len(wdf)*38),
                bargap=0.35,
                xaxis=dict(gridcolor="rgba(0,119,182,0.08)", tickformat="d", dtick=1),
                yaxis=dict(gridcolor="rgba(0,119,182,0.08)", autorange="reversed"),
            )
            fig.update_traces(textposition="outside", marker_line_width=0, opacity=0.85)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            for word, count in word_freq:
                st.markdown(f"**{word}** — {count} time(s)")

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("🗑️  Clear All Failed Queries (after fixing KB)", key="gap_clear_btn"):
        try:
            db.table("failed_queries").delete().neq("id", 0).execute()
            st.toast("🗑️ All failed queries cleared", icon="✅")
            st.success("Cleared!")
            st.rerun()
        except Exception as e:
            st.error(str(e))


# ════════════════════════════════════════════════════════
#  PAGE: SETUP
# ════════════════════════════════════════════════════════
def page_setup():
    st.markdown("""
    <div class="page-header">
        <div class="page-title">Setup & Configuration</div>
        <div class="page-subtitle">Connect your database, test the PDF pipeline and view learned answers</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📁 Streamlit Secrets", expanded=True):
        st.code('[secrets]\nSUPABASE_URL   = "https://xxxx.supabase.co"\nSUPABASE_KEY   = "eyJ..."\nADMIN_PASSWORD = "your_password"', language="toml")
    with st.expander("🗄️ Create Supabase Tables"):
        st.code(SCHEMA_SQL, language="sql")
    with st.expander("📦 Install Dependencies"):
        st.code("pip install streamlit supabase pdfplumber sentence-transformers requests torch plotly pandas", language="bash")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Connection Status</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.secrets.get("SUPABASE_URL",""):
            st.success("✅ Supabase URL configured")
        else:
            st.error("❌ Supabase URL missing")
    with c2:
        if st.secrets.get("SUPABASE_KEY",""):
            st.success("✅ Supabase Key configured")
        else:
            st.error("❌ Supabase Key missing")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Tests</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🧪 Test Database", use_container_width=True, key="setup_test_db"):
            try:
                db = get_db()
                if db is None:
                    st.error("Not configured.")
                else:
                    db.table("tickets").select("id").limit(1).execute()
                    st.success("✅ Database connected!")
                    st.toast("✅ Supabase connected", icon="☁️")
            except Exception as e:
                st.error(f"Failed: {e}")

    with col2:
        if st.button("📄 Test PDF + Q&A", use_container_width=True, key="setup_test_pdf"):
            pdf_bytes = get_pdf_bytes()
            if not pdf_bytes:
                st.error("❌ Could not download PDF.")
            else:
                st.success(f"✅ PDF downloaded ({len(pdf_bytes)//1024} KB)")
                pairs = load_qa_pairs()
                if pairs:
                    st.success(f"✅ {len(pairs)} Q&A pairs extracted!")
                else:
                    st.error("❌ No Q&A pairs found.")

    with col3:
        if st.button("🧠 Test Semantic Model", use_container_width=True, key="setup_test_model"):
            model, q_emb, a_emb, pairs, util = load_model_and_embeddings()
            if model is None:
                st.error("❌ Model failed to load.")
            else:
                st.success(f"✅ Model loaded · {len(pairs)} embeddings ready")
                st.toast("🧠 Semantic model loaded", icon="⚡")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Learned Answers</div>", unsafe_allow_html=True)

    if st.button("📋 View All Learned Answers", key="setup_view_learned"):
        db = get_db()
        if db is None:
            st.error("Supabase not configured.")
        else:
            try:
                rows = db.table("resolved_issues").select("*").order("created_at", desc=True).execute().data or []
                if rows:
                    st.success(f"{len(rows)} learned answer(s) in database.")
                    for row in rows:
                        with st.expander(f"🟢 {row['query'][:100]}"):
                            st.markdown(f"**Original question:** {row['query']}")
                            st.markdown(f"**Admin solution:** {row['solution']}")
                            st.markdown(f"<small style='color:rgba(2,62,138,0.4)'>Saved: {_to_ist(row.get('created_at',''))}</small>", unsafe_allow_html=True)
                else:
                    st.info("No learned answers yet.")
            except Exception as e:
                st.error(f"Error: {e}")


# ════════════════════════════════════════════════════════
#  SIDEBAR + ROUTING
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <div class="sidebar-logo-mark">🎯 HelpDesk Pro</div>
        <div class="sidebar-logo-sub">Internal support system</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='sidebar-section-label'>Navigation</div>", unsafe_allow_html=True)

    page = st.radio("Navigation", [
        "🔍  Employee Portal",
        "🛡️  Admin Panel",
        "📊  Analytics",
        "🕳️  Knowledge Gaps",
        "📋  Approval Pipeline",
        "⚙️  Setup / Config",
    ], label_visibility="collapsed")

    st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)

    if not PIPELINE_AVAILABLE:
        st.warning("⚠️ approval_pipeline.py not found")

    st.markdown("""
    <div class="sidebar-footer">
        Powered by Supabase + pdfplumber<br>
        <span style="opacity:0.5">sentence-transformers · Streamlit</span>
    </div>
    """, unsafe_allow_html=True)


if   page == "🔍  Employee Portal":  page_employee()
elif page == "🛡️  Admin Panel":       page_admin()
elif page == "📊  Analytics":         page_analytics()
elif page == "🕳️  Knowledge Gaps":    page_knowledge_gap()
elif page == "📋  Approval Pipeline":
    if PIPELINE_AVAILABLE:
        page_approval_pipeline()
    else:
        st.error("❌ `approval_pipeline.py` is missing from your project folder.")
elif page == "⚙️  Setup / Config":   page_setup()
