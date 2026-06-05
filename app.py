import streamlit as st
import re
import io
import requests
import csv
from datetime import datetime, timezone, timedelta
from collections import Counter

# ── IST Timezone (UTC+5:30) ───────────────────────────────────────────────────
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

st.set_page_config(page_title="HelpDesk Pro", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

import streamlit.components.v1 as components
components.html("""
<script>
(function() {
    function applyFonts() {
        var style = document.createElement('style');
        style.id = 'font-override-inject';
        style.innerHTML = `
            html { font-size: 20px !important; }
            body { font-size: 20px !important; }
            p, span, div, li, td, th, label, a,
            .stMarkdown p,
            [data-testid="stMarkdownContainer"] p,
            [data-testid="stMarkdownContainer"] li,
            [data-testid="stMarkdownContainer"] span {
                font-size: 20px !important;
                font-family: 'EB Garamond', Georgia, serif !important;
            }
            input, textarea, select {
                font-size: 20px !important;
                font-family: 'EB Garamond', Georgia, serif !important;
            }
            button, button span, button p {
                font-size: 20px !important;
                font-family: 'EB Garamond', Georgia, serif !important;
            }
            label, label p, label span {
                font-size: 20px !important;
                font-family: 'EB Garamond', Georgia, serif !important;
            }
            [data-baseweb="select"] div,
            [data-baseweb="select"] span,
            [role="option"] {
                font-size: 20px !important;
                font-family: 'EB Garamond', Georgia, serif !important;
            }
            [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] span,
            [data-testid="stSidebar"] label {
                font-size: 20px !important;
            }
            [data-testid="stAlert"] p,
            [data-testid="stAlert"] span {
                font-size: 20px !important;
            }
            [data-testid="stExpander"] summary p {
                font-size: 20px !important;
            }
        `;
        var existing = document.getElementById('font-override-inject');
        if (existing) existing.remove();
        document.head.appendChild(style);
    }
    applyFonts();
    var observer = new MutationObserver(applyFonts);
    observer.observe(document.body, { childList: true, subtree: true });
})();
</script>
""", height=0)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=DM+Mono:wght@400;500&display=swap');

:root {
    --cream:       #f5f0e8;
    --cream-dark:  #ede7d9;
    --cream-mid:   #e8e0d0;
    --paper:       #faf7f2;
    --ink:         #1a1612;
    --ink-light:   #3d3530;
    --ink-muted:   #6b5f55;
    --ink-faint:   #9c8e82;
    --rust:        #8b3a2a;
    --rust-light:  #c4543a;
    --rust-pale:   #f0e0db;
    --sage:        #3d5a4a;
    --sage-light:  #d4e8dc;
    --amber:       #8b6914;
    --amber-light: #f0e2b0;
    --slate:       #2d3d4f;
    --slate-light: #c8d8e8;
    --border:      #d4c9bc;
    --border-dark: #b8a898;
    --shadow:      rgba(26,22,18,0.08);
    --shadow-md:   rgba(26,22,18,0.14);
}

html, body, [class*="css"] {
    font-family: 'EB Garamond', Georgia, serif;
    color: var(--ink);
    background: var(--cream);
    font-size: 20px;
}
h1, h2, h3, h4, h5 {
    font-family: 'Playfair Display', Georgia, serif !important;
    color: var(--ink) !important;
    letter-spacing: -0.01em;
}
code, pre, .stCode {
    font-family: 'DM Mono', monospace !important;
    font-size: 20px !important;
}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
    background: var(--cream) !important;
}
section[data-testid="stSidebar"] {
    background: var(--ink) !important;
    border-right: 1px solid #2a2420;
}
section[data-testid="stSidebar"] * { color: var(--cream) !important; }
section[data-testid="stSidebar"] .stRadio label {
    font-family: 'EB Garamond', serif !important;
    font-size: 24px !important;
    letter-spacing: 0.02em;
    color: var(--cream-mid) !important;
    padding: 6px 0;
    cursor: pointer;
    transition: color 0.2s;
}
section[data-testid="stSidebar"] .stRadio label:hover { color: white !important; }
section[data-testid="stSidebar"] hr { border-color: #3a3028 !important; margin: 12px 0; }
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: 1px solid #3a3028 !important;
    color: var(--cream-mid) !important;
    font-family: 'EB Garamond', serif !important;
    font-size: 22px !important;
    letter-spacing: 0.04em;
    transition: all 0.2s;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #2a2420 !important;
    border-color: #6b5f55 !important;
    color: white !important;
}
[data-testid="stMainBlockContainer"] { padding: 2rem 3rem; max-width: 1400px; }

.answer-box {
    background: var(--paper); border-radius: 3px; padding: 24px 28px;
    border-left: 3px solid var(--rust); font-size: 24px; line-height: 1.9;
    color: var(--ink-light); font-family: 'EB Garamond', serif;
    box-shadow: 0 1px 8px var(--shadow); margin: 8px 0;
}
.no-answer-box {
    background: var(--rust-pale); border-radius: 3px; padding: 18px 22px;
    border-left: 3px solid var(--rust-light); color: var(--rust);
    font-size: 23px; font-family: 'EB Garamond', serif;
}
.learned-box {
    background: var(--paper); border-radius: 3px; padding: 24px 28px;
    border-left: 3px solid var(--sage); font-size: 24px; line-height: 1.9;
    color: var(--ink-light); font-family: 'EB Garamond', serif;
    box-shadow: 0 1px 8px var(--shadow);
}
.badge-open {
    background: var(--amber-light); color: var(--amber); padding: 3px 12px;
    border-radius: 2px; font-size: 16px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; font-family: 'DM Mono', monospace; border: 1px solid #d4b830;
}
.badge-inprogress {
    background: var(--slate-light); color: var(--slate); padding: 3px 12px;
    border-radius: 2px; font-size: 16px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; font-family: 'DM Mono', monospace; border: 1px solid #8ab0cc;
}
.badge-resolved {
    background: var(--sage-light); color: var(--sage); padding: 3px 12px;
    border-radius: 2px; font-size: 16px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; font-family: 'DM Mono', monospace; border: 1px solid #7ab898;
}
.badge-overdue {
    background: var(--rust-pale); color: var(--rust); padding: 3px 12px;
    border-radius: 2px; font-size: 16px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; font-family: 'DM Mono', monospace; border: 1px solid #c4543a;
}
.prio-high {
    background: var(--rust-pale); color: var(--rust); padding: 2px 10px;
    border-radius: 2px; font-size: 16px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; font-family: 'DM Mono', monospace;
}
.prio-medium {
    background: var(--amber-light); color: var(--amber); padding: 2px 10px;
    border-radius: 2px; font-size: 16px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; font-family: 'DM Mono', monospace;
}
.prio-low {
    background: var(--sage-light); color: var(--sage); padding: 2px 10px;
    border-radius: 2px; font-size: 16px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase; font-family: 'DM Mono', monospace;
}
div.stButton > button {
    background: var(--ink) !important; color: #f5f0e8 !important;
    border: 1px solid var(--ink) !important; border-radius: 2px !important;
    padding: 14px 28px !important; font-family: 'EB Garamond', serif !important;
    font-size: 22px !important; font-weight: 500 !important;
    letter-spacing: 0.04em !important; transition: all 0.18s ease !important;
    box-shadow: none !important; min-height: 52px !important; line-height: 1.4 !important;
}
div.stButton > button p, div.stButton > button span, div.stButton > button div {
    color: #f5f0e8 !important; background: transparent !important; padding: 0 !important;
    margin: 0 !important; border: none !important; font-size: inherit !important;
    font-family: inherit !important; letter-spacing: inherit !important; line-height: inherit !important;
}
div.stButton > button:hover { background: var(--rust) !important; border-color: var(--rust) !important; color: #ffffff !important; }
div.stButton > button:hover p, div.stButton > button:hover span, div.stButton > button:hover div { color: #ffffff !important; }
div.stButton > button[kind="primary"] { background: var(--rust) !important; border-color: var(--rust) !important; color: #ffffff !important; }
div.stButton > button[kind="primary"] p, div.stButton > button[kind="primary"] span, div.stButton > button[kind="primary"] div { color: #ffffff !important; }
div.stButton > button[kind="primary"]:hover { background: var(--rust-light) !important; border-color: var(--rust-light) !important; color: #ffffff !important; }

.metric-card {
    background: var(--paper); border-radius: 3px; padding: 24px 22px; text-align: left;
    border: 1px solid var(--border); box-shadow: 0 1px 6px var(--shadow);
    position: relative; overflow: hidden;
}
.metric-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 2px; background: var(--rust);
}
.metric-number {
    font-family: 'Playfair Display', serif !important; font-size: 54px !important;
    font-weight: 700 !important; color: var(--ink) !important; line-height: 1; margin-bottom: 8px;
}
.metric-label {
    font-size: 16px; color: var(--ink-muted); letter-spacing: 0.1em;
    text-transform: uppercase; font-family: 'DM Mono', monospace;
}
.gap-card {
    background: var(--paper); border-radius: 3px; padding: 18px 22px; margin-bottom: 10px;
    border-left: 3px solid var(--rust); border: 1px solid var(--border);
    box-shadow: 0 1px 4px var(--shadow);
}
.gap-count { font-family: 'Playfair Display', serif; font-size: 28px; font-weight: 700; color: var(--rust); }
.timeline-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 8px; vertical-align: middle; }

.stTextInput > div > div > input, .stTextArea > div > div > textarea {
    background: var(--paper) !important; border: 1px solid var(--border) !important;
    border-radius: 2px !important; color: var(--ink) !important;
    font-family: 'EB Garamond', serif !important; font-size: 24px !important;
    padding: 16px 20px !important; line-height: 1.6 !important;
}
.stTextInput > div > div > input::placeholder, .stTextArea > div > div > textarea::placeholder {
    color: var(--ink-faint) !important; font-size: 22px !important;
    font-style: italic !important; font-family: 'EB Garamond', serif !important;
}
.stSelectbox > div > div, .stSelectbox > div > div > div {
    background: var(--paper) !important; border: 1px solid var(--border) !important;
    border-radius: 2px !important; color: var(--ink) !important;
    font-family: 'EB Garamond', serif !important; font-size: 24px !important; min-height: 56px !important;
}
[data-baseweb="select"] span, [data-baseweb="select"] div {
    font-family: 'EB Garamond', serif !important; font-size: 24px !important; color: var(--ink) !important;
}
.stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
    border-color: var(--rust) !important; box-shadow: 0 0 0 1px var(--rust) !important;
}
label[data-testid="stWidgetLabel"], label[data-testid="stWidgetLabel"] p {
    font-family: 'EB Garamond', serif !important; font-size: 23px !important;
    font-weight: 600 !important; letter-spacing: 0.01em !important;
    text-transform: none !important; color: var(--ink) !important;
}
[data-testid="stExpander"] {
    background: var(--paper) !important; border: 1px solid var(--border) !important;
    border-radius: 3px !important; margin-bottom: 8px;
}
[data-testid="stExpander"] > div:first-child {
    font-family: 'EB Garamond', serif !important; font-size: 22px !important; color: var(--ink-light) !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important; border-bottom: 1px solid var(--border) !important; gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; border-radius: 0 !important;
    border-bottom: 2px solid transparent !important; color: var(--ink-muted) !important;
    font-family: 'DM Mono', monospace !important; font-size: 16px !important;
    letter-spacing: 0.06em !important; text-transform: uppercase !important;
    padding: 12px 20px !important; margin-bottom: -1px; transition: all 0.15s;
}
.stTabs [aria-selected="true"] { border-bottom-color: var(--rust) !important; color: var(--rust) !important; }
.stAlert { border-radius: 3px !important; border-left-width: 3px !important; font-family: 'EB Garamond', serif !important; font-size: 24px !important; }
.stAlert p, .stAlert div, .stAlert span { font-family: 'EB Garamond', serif !important; font-size: 24px !important; }
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 20px 0 !important; }
small, .stCaption { font-family: 'DM Mono', monospace !important; font-size: 17px !important; color: var(--ink-faint) !important; letter-spacing: 0.03em; }
[data-testid="stMarkdownContainer"] p { font-family: 'EB Garamond', serif; font-size: 24px; line-height: 1.85; color: var(--ink-light); }
[data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] ul, [data-testid="stMarkdownContainer"] ol { font-family: 'EB Garamond', serif; font-size: 24px; line-height: 1.85; color: var(--ink-light); }

.doc-card { background: var(--paper); border-radius: 3px; padding: 18px 22px; margin-bottom: 10px; border: 1px solid var(--border); box-shadow: 0 1px 4px var(--shadow); position: relative; }
.doc-card-restricted { border-left: 3px solid var(--rust); }
.doc-card-accessible { border-left: 3px solid var(--sage); }
.doc-card-pending    { border-left: 3px solid var(--amber); }
.role-badge { display: inline-block; padding: 3px 12px; border-radius: 2px; font-size: 14px; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; font-family: 'DM Mono', monospace; }
.role-ceo  { background: #1a1612; color: #f5f0e8; }
.role-cto  { background: var(--slate); color: #f5f0e8; }
.role-tech { background: var(--slate-light); color: var(--slate); border: 1px solid #8ab0cc; }
.role-mgr  { background: var(--amber-light); color: var(--amber); border: 1px solid #d4b830; }
.role-emp  { background: var(--sage-light); color: var(--sage); border: 1px solid #7ab898; }
.role-all  { background: var(--cream-dark); color: var(--ink-muted); border: 1px solid var(--border); }
.access-granted  { color: var(--sage);  font-family: 'DM Mono', monospace; font-size: 15px; letter-spacing: 0.06em; text-transform: uppercase; }
.access-denied   { color: var(--rust);  font-family: 'DM Mono', monospace; font-size: 15px; letter-spacing: 0.06em; text-transform: uppercase; }
.access-pending  { color: var(--amber); font-family: 'DM Mono', monospace; font-size: 15px; letter-spacing: 0.06em; text-transform: uppercase; }
.access-expiring { color: #8b6914;      font-family: 'DM Mono', monospace; font-size: 15px; letter-spacing: 0.06em; text-transform: uppercase; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--cream); }
::-webkit-scrollbar-thumb { background: var(--border-dark); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--ink-muted); }
.stSpinner > div { border-top-color: var(--rust) !important; }
[data-testid="stMetric"] { background: var(--paper); border: 1px solid var(--border); border-radius: 3px; padding: 16px 20px; }
[data-testid="stMetricValue"] { font-family: 'Playfair Display', serif !important; font-size: 42px !important; color: var(--ink) !important; }
[data-testid="stMetricLabel"] { font-family: 'DM Mono', monospace !important; font-size: 15px !important; letter-spacing: 0.06em !important; text-transform: uppercase !important; color: var(--ink-muted) !important; }

/* Approval pipeline CSS */
.ap-policy-box { background: linear-gradient(135deg,#fffbeb,#fef3c7); border: 1.5px solid #fcd34d; border-radius: 14px; padding: 16px 20px; margin: 12px 0; }
.ap-chain-role { background: white; border: 1.5px solid #fcd34d; border-radius: 10px; padding: 6px 14px; font-size: 13px; font-weight: 600; color: #92400e; display: inline-block; margin: 2px; }
.ap-chain-arrow { font-size: 18px; color: #d97706; margin: 0 2px; }
.ap-timer-chip { background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 2px 8px; font-size: 11px; font-weight: 700; color: #92400e; display: inline-block; margin: 2px; }
.ap-esc-item { background: #fff7ed; border-left: 3px solid #f97316; border-radius: 0 8px 8px 0; padding: 8px 14px; margin: 6px 0; font-size: 13px; color: #9a3412; }
.ap-deadline-chip { display: inline-block; background: #fef9c3; border: 1px solid #fde047; border-radius: 8px; padding: 3px 10px; font-size: 12px; color: #713f12; margin-top: 4px; }
.ap-role-reminder { background: #fffbeb; border: 1.5px solid #fcd34d; border-radius: 10px; padding: 12px 16px; margin-bottom: 12px; font-size: 13px; color: #92400e; }
.ap-escalation-banner { background: linear-gradient(135deg,#fff7ed,#ffedd5); border: 1.5px solid #fed7aa; border-radius: 12px; padding: 14px 18px; margin: 10px 0; font-size: 13px; color: #9a3412; line-height: 1.7; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  IMPORT APPROVAL PIPELINE
# ════════════════════════════════════════════════════════
try:
    from approval_pipeline import (
        DOC_CATEGORIES, _build_chain, _classify_request,
        _init as _ap_init, _load_requests as _ap_load_requests,
        _check_expiry, _migrate_chain, _db_update as _ap_db_update,
        _view_role, _escalation_label, _fmt as _ap_fmt,
        ROLE_PASSWORDS as AP_ROLE_PASSWORDS,
    )
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
CREATE TABLE IF NOT EXISTS documents (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT NOT NULL DEFAULT 'General',
    sensitivity     TEXT NOT NULL DEFAULT 'Normal',
    min_role        TEXT NOT NULL DEFAULT 'Employee',
    owner_id        TEXT,
    file_url        TEXT,
    content_preview TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS doc_access (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL,
    user_role   TEXT NOT NULL,
    granted_by  TEXT,
    granted_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days'),
    status      TEXT NOT NULL DEFAULT 'Approved'
);
CREATE TABLE IF NOT EXISTS doc_access_requests (
    id           BIGSERIAL PRIMARY KEY,
    doc_id       BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id      TEXT NOT NULL,
    user_role    TEXT NOT NULL,
    reason       TEXT,
    status       TEXT NOT NULL DEFAULT 'Pending',
    reviewed_by  TEXT,
    reviewed_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE tickets DISABLE ROW LEVEL SECURITY;
ALTER TABLE resolved_issues DISABLE ROW LEVEL SECURITY;
ALTER TABLE failed_queries DISABLE ROW LEVEL SECURITY;
ALTER TABLE documents DISABLE ROW LEVEL SECURITY;
ALTER TABLE doc_access DISABLE ROW LEVEL SECURITY;
ALTER TABLE doc_access_requests DISABLE ROW LEVEL SECURITY;
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
    result = db.table("tickets").insert(row).execute()
    if result.data:
        ticket = result.data[0]
        st.toast(f"🎫 Ticket #{ticket.get('id')} saved to Supabase!", icon="☁️")
        return ticket
    raise Exception("No data returned from insert")

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
    db.table("tickets").update({"status": status, "admin_note": note}).eq("id", tid).execute()
    st.toast(f"✏️ Ticket #{tid} updated → {status}", icon="☁️")

def db_delete_ticket(tid):
    db = get_db()
    if db:
        db.table("tickets").delete().eq("id", tid).execute()
        st.toast(f"🗑️ Ticket #{tid} deleted", icon="☁️")

def db_log_failed_query(query: str):
    db = get_db()
    if db:
        try:
            db.table("failed_queries").insert({"query": query}).execute()
            st.toast("📋 Logged to failed_queries", icon="☁️")
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
            st.toast("🧠 Admin note saved as learned answer!", icon="☁️")
        else:
            db.table("resolved_issues").update({"solution": note.strip()}).eq("query", ticket_query).execute()
            st.toast("🧠 Learned answer updated!", icon="☁️")
        return True
    except Exception:
        return False

def tickets_to_csv(tickets: list) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id","user_id","job_role","query","priority","status","admin_note","created_at"])
    writer.writeheader()
    for t in tickets:
        writer.writerow({k: t.get(k, "") for k in writer.fieldnames})
    return output.getvalue().encode("utf-8")


# ════════════════════════════════════════════════════════
#  LEARNED ANSWERS
# ════════════════════════════════════════════════════════
_STOP_WORDS = {
    "what","is","are","the","a","an","of","in","on","at","to","for","and","or",
    "how","why","when","where","who","does","do","can","could","would","should",
    "explain","tell","me","about","difference","between","use","using","means",
    "mean","define","definition","describe","give",
}

def _normalize(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

def _content_words(text: str) -> set:
    words = re.findall(r'\b[a-z]{2,}\b', text.lower())
    return {w for w in words if w not in _STOP_WORDS}

def _keyword_score(query: str, stored_query: str) -> float:
    q_norm = _normalize(query); s_norm = _normalize(stored_query)
    if q_norm == s_norm: return 1.0
    if q_norm in s_norm or s_norm in q_norm: return 0.85
    q_words = _content_words(query); s_words = _content_words(stored_query)
    if not q_words or not s_words: return 0.0
    intersection = q_words & s_words
    shorter = q_words if len(q_words) <= len(s_words) else s_words
    if intersection == shorter and len(shorter) >= 1: return 0.80
    jaccard = len(intersection) / len(q_words | s_words)
    return max(jaccard, 0.35) if intersection else 0.0

_LEARNED_THRESHOLD = 0.30

def check_learned_answers(query: str):
    db = get_db()
    if db is None: return None
    best_score, best_solution, best_matched = 0.0, None, None
    try:
        resp = db.table("tickets").select("query, admin_note").not_.is_("admin_note", "null").execute()
        for row in (resp.data or []):
            note = (row.get("admin_note") or "").strip()
            q    = (row.get("query") or "").strip()
            if not note or not q: continue
            score = _keyword_score(query, q)
            if score > best_score:
                best_score, best_solution, best_matched = score, note, q
    except Exception: pass
    try:
        resp2 = db.table("resolved_issues").select("query, solution").execute()
        for row in (resp2.data or []):
            sol = (row.get("solution") or "").strip()
            q   = (row.get("query") or "").strip()
            if not sol or not q: continue
            score = _keyword_score(query, q)
            if score > best_score:
                best_score, best_solution, best_matched = score, sol, q
    except Exception: pass
    if best_solution and best_score >= _LEARNED_THRESHOLD:
        return {"solution": best_solution, "matched_query": best_matched, "score": best_score, "source": "learned"}
    return None


# ════════════════════════════════════════════════════════
#  PDF + SEMANTIC SEARCH
# ════════════════════════════════════════════════════════
_PDF_PUBLIC_URL = "https://jvulbphmksdebkkkhgvh.supabase.co/storage/v1/object/public/Documents/questions.pdf"
_Q_THRESHOLD   = 0.60
_A_THRESHOLD   = 0.65
_ANSWER_WEIGHT = 0.85

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
    if not pdf_bytes: return []
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: text += page_text + "\n"
    except Exception as e:
        st.warning(f"pdfplumber failed: {e}")
        return []
    text = text.lower()
    qa_pairs = []
    for part in re.split(r'q\.', text):
        if "answer" not in part: continue
        try:
            q_part, a_part = part.split("answer", 1)
            question = q_part.strip(); answer = a_part.strip()
            if "enroll" in answer or "course" in answer: continue
            if len(answer) < 30 or len(question) < 5: continue
            qa_pairs.append((question, answer))
        except Exception: continue
    return qa_pairs

@st.cache_resource(show_spinner="🧠 Loading semantic search model…")
def load_model_and_embeddings():
    try:
        from sentence_transformers import SentenceTransformer, util
        pairs = load_qa_pairs()
        if not pairs: return None, None, None, None, None
        model        = SentenceTransformer('multi-qa-mpnet-base-dot-v1')
        questions    = [q for q, _ in pairs]
        answers      = [a for _, a in pairs]
        q_embeddings = model.encode(questions, convert_to_tensor=True, show_progress_bar=False)
        a_embeddings = model.encode(answers,   convert_to_tensor=True, show_progress_bar=False)
        return model, q_embeddings, a_embeddings, pairs, util
    except Exception as e:
        st.warning(f"Semantic model error: {e}")
        return None, None, None, None, None

def answer_question(query: str) -> dict:
    model, q_embeddings, a_embeddings, pairs, util = load_model_and_embeddings()
    if model is not None and q_embeddings is not None and pairs is not None:
        try:
            query_embedding  = model.encode(query.lower(), convert_to_tensor=True)
            q_scores         = util.cos_sim(query_embedding, q_embeddings)[0]
            best_q_idx       = int(q_scores.argmax()); best_q_score = float(q_scores[best_q_idx])
            a_scores         = util.cos_sim(query_embedding, a_embeddings)[0]
            best_a_idx       = int(a_scores.argmax()); best_a_score = float(a_scores[best_a_idx])
            weighted_a_score = best_a_score * _ANSWER_WEIGHT
            if best_q_score >= _Q_THRESHOLD or best_a_score >= _A_THRESHOLD:
                if best_q_score >= weighted_a_score:
                    chosen_idx, chosen_score, match_source = best_q_idx, best_q_score, "question"
                else:
                    chosen_idx, chosen_score, match_source = best_a_idx, best_a_score, "answer"
                question, answer = pairs[chosen_idx]
                return {"found": True, "answer": answer.strip(), "matched": question.strip(),
                        "score": chosen_score, "match_src": match_source, "pdf_error": False, "source": "pdf"}
        except Exception: pass
    learned = check_learned_answers(query)
    if learned:
        return {"found": True, "answer": learned["solution"], "matched": learned["matched_query"],
                "score": learned["score"], "match_src": "learned", "pdf_error": False, "source": learned.get("source", "learned")}
    return {"found": False, "answer": "", "matched": "", "score": 0, "match_src": "none",
            "pdf_error": (model is None or q_embeddings is None), "source": "none"}


# ════════════════════════════════════════════════════════
#  TICKET INTENT DETECTOR
# ════════════════════════════════════════════════════════
_TICKET_INTENT_PHRASES = [
    "raise a ticket","raise ticket","raise a query","raise query","raise an issue","raise issue",
    "submit a ticket","submit ticket","create a ticket","create ticket","open a ticket","log a ticket",
    "report an issue","report a problem","report a bug","need help ticket","contact support","get support",
    "need human help","talk to someone","speak to admin","escalate",
]

def _is_ticket_intent(text: str) -> bool:
    lower = text.lower().strip()
    return any(phrase in lower for phrase in _TICKET_INTENT_PHRASES)


# ════════════════════════════════════════════════════════
#  DOC VISIBILITY — ROLE HIERARCHY + HELPERS
# ════════════════════════════════════════════════════════
ROLE_HIERARCHY    = ["Employee", "Manager", "Tech Manager", "CTO", "CEO"]
AUTO_ACCESS_ROLES = {"CTO", "CEO"}

def _role_level(role: str) -> int:
    try: return ROLE_HIERARCHY.index(role)
    except ValueError: return 0

def _can_auto_access(user_role: str, doc_min_role: str) -> bool:
    if user_role in AUTO_ACCESS_ROLES: return True
    return _role_level(user_role) >= _role_level(doc_min_role)

def _sensitivity_color(sensitivity: str) -> str:
    return {"Normal": "var(--sage)", "Restricted": "var(--amber)", "Confidential": "var(--rust)", "Top Secret": "#1a1612"}.get(sensitivity, "var(--ink-muted)")

def _sensitivity_bg(sensitivity: str) -> str:
    return {"Normal": "var(--sage-light)", "Restricted": "var(--amber-light)", "Confidential": "var(--rust-pale)", "Top Secret": "#e8e0d0"}.get(sensitivity, "var(--cream-dark)")

def _role_badge_class(role: str) -> str:
    return {"CEO": "role-ceo", "CTO": "role-cto", "Tech Manager": "role-tech", "Manager": "role-mgr", "Employee": "role-emp"}.get(role, "role-all")

def db_get_documents():
    db = get_db()
    if db is None: return []
    try:
        return db.table("documents").select("*").order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"Doc fetch error: {e}"); return []

def db_add_document(title, description, category, sensitivity, min_role, owner_id, file_url, content_preview):
    db = get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    row = {"title": title, "description": description, "category": category, "sensitivity": sensitivity,
           "min_role": min_role, "owner_id": owner_id, "file_url": file_url, "content_preview": content_preview}
    result = db.table("documents").insert(row).execute()
    if result.data:
        st.toast(f"📄 Document '{title}' added", icon="☁️")
        return result.data[0]
    raise Exception("Insert failed")

def db_delete_document(doc_id):
    db = get_db()
    if db:
        db.table("documents").delete().eq("id", doc_id).execute()
        st.toast(f"🗑️ Document #{doc_id} deleted", icon="☁️")

def db_get_access_grants(user_id=None, doc_id=None):
    db = get_db()
    if db is None: return []
    try:
        q = db.table("doc_access").select("*")
        if user_id: q = q.eq("user_id", user_id)
        if doc_id:  q = q.eq("doc_id", doc_id)
        return q.execute().data or []
    except Exception: return []

def db_check_active_grant(user_id: str, doc_id: int):
    grants = db_get_access_grants(user_id=user_id, doc_id=doc_id)
    now = datetime.now(timezone.utc)
    for g in grants:
        if g.get("status") != "Approved": continue
        try:
            exp = datetime.fromisoformat(g["expires_at"].replace("Z", "+00:00"))
            if exp > now: return g
        except Exception: pass
    return None

def db_grant_access(doc_id, user_id, user_role, granted_by="System"):
    db = get_db()
    if db is None: return
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    row = {"doc_id": doc_id, "user_id": user_id, "user_role": user_role, "granted_by": granted_by, "expires_at": expires, "status": "Approved"}
    db.table("doc_access").insert(row).execute()
    st.toast(f"🔓 Access granted to {user_id} (7 days)", icon="☁️")

def db_revoke_access(grant_id):
    db = get_db()
    if db:
        db.table("doc_access").update({"status": "Revoked"}).eq("id", grant_id).execute()
        st.toast(f"🔒 Access grant #{grant_id} revoked", icon="☁️")

def db_get_access_requests(status_filter=None, doc_id=None):
    db = get_db()
    if db is None: return []
    try:
        q = db.table("doc_access_requests").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All": q = q.eq("status", status_filter)
        if doc_id: q = q.eq("doc_id", doc_id)
        return q.execute().data or []
    except Exception: return []

def db_submit_access_request(doc_id, user_id, user_role, reason):
    db = get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    existing = db.table("doc_access_requests").select("id, status").eq("doc_id", doc_id).eq("user_id", user_id).eq("status", "Pending").execute().data or []
    if existing: return None
    row = {"doc_id": doc_id, "user_id": user_id, "user_role": user_role, "reason": reason, "status": "Pending"}
    result = db.table("doc_access_requests").insert(row).execute()
    if result.data:
        st.toast(f"📩 Access request submitted for doc #{doc_id}", icon="☁️")
        return result.data[0]
    return None

def db_review_access_request(req_id, action, reviewed_by, doc_id=None, user_id=None, user_role=None):
    db = get_db()
    if db is None: return
    now_str = datetime.now(timezone.utc).isoformat()
    db.table("doc_access_requests").update({"status": action, "reviewed_by": reviewed_by, "reviewed_at": now_str}).eq("id", req_id).execute()
    if action == "Approved" and doc_id and user_id and user_role:
        db_grant_access(doc_id, user_id, user_role, granted_by=reviewed_by)
    st.toast(f"✅ Request #{req_id} {action}", icon="☁️")


# ════════════════════════════════════════════════════════
#  PAGE: EMPLOYEE PORTAL
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("# Employee Help Portal")
    st.markdown("<p style='color:#6b5f55; font-size:26px; font-family: EB Garamond, serif;'>Ask any question — or type <em>raise a ticket</em> to go straight to support.</p>", unsafe_allow_html=True)
    st.markdown("---")

    pairs = load_qa_pairs()
    if len(pairs) == 0:
        st.error("⚠️ PDF knowledge base could not be loaded.")
    else:
        st.success(f"📚 Knowledge Base ready — {len(pairs)} Q&A pairs indexed")

    st.markdown("### Ask a Question")
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("", placeholder="e.g. What is the difference between a list and a tuple?  ·  or: raise a ticket", label_visibility="collapsed")
    with col2:
        search = st.button("Search →", use_container_width=True)

    if search and question.strip():
        if _is_ticket_intent(question.strip()):
            st.markdown("<div style='background:var(--paper);border:1px solid var(--border);border-left:3px solid var(--rust);border-radius:3px;padding:16px 20px;margin-bottom:8px;'><p style='margin:0;font-family:EB Garamond,serif;font-size:24px;color:var(--ink-light);'>Sure — fill in the form below and our team will get back to you.</p></div>", unsafe_allow_html=True)
            st.session_state["show_ticket"] = True
            st.session_state["ticket_query"] = ""
        else:
            with st.spinner("Searching knowledge base…"):
                result = answer_question(question.strip())
            if result.get("pdf_error") and not result["found"]:
                st.error("Knowledge base unavailable. Please raise a ticket.")
                db_log_failed_query(question.strip())
                st.session_state["show_ticket"] = True
                st.session_state["ticket_query"] = question.strip()
            elif result["found"]:
                source = result.get("source", "pdf")
                match_src = result.get("match_src", "question")
                if source == "learned":
                    st.markdown("#### ✦ Answer Found")
                    st.markdown(f"<small style='color:#3d5a4a;font-family:DM Mono,monospace;font-size:17px;letter-spacing:0.06em;text-transform:uppercase;'>Source: Previously resolved support ticket</small>", unsafe_allow_html=True)
                    st.markdown(f"<small style='color:#9c8e82;font-family:EB Garamond,serif;font-size:20px;'>Similar question: <em>{result['matched'][:160]}</em> &nbsp;·&nbsp; similarity {result['score']:.0%}</small>", unsafe_allow_html=True)
                    st.markdown(f"<div class='learned-box'>{result['answer']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("#### ✦ Answer Found")
                    match_label = "matched via question" if match_src == "question" else "matched via answer content"
                    st.markdown(f"<small style='color:#8b3a2a;font-family:DM Mono,monospace;font-size:17px;letter-spacing:0.06em;text-transform:uppercase;'>Source: PDF Knowledge Base &nbsp;·&nbsp; {match_label}</small>", unsafe_allow_html=True)
                    st.markdown(f"<small style='color:#9c8e82;font-family:EB Garamond,serif;font-size:20px;'>Matched: <em>{result['matched'][:120]}</em> &nbsp;·&nbsp; score {result['score']:.2f}</small>", unsafe_allow_html=True)
                    st.markdown(f"<div class='answer-box'>{result['answer']}</div>", unsafe_allow_html=True)
                st.markdown("---")
                col_a, col_b, _ = st.columns([1, 1, 4])
                with col_a:
                    if st.button("👍 Helpful", key="emp_helpful"):
                        st.success("Great! Glad it helped.")
                with col_b:
                    if st.button("👎 Not helpful", key="emp_not_helpful"):
                        db_log_failed_query(question.strip())
                        st.session_state["show_ticket"] = True
                        st.session_state["ticket_query"] = question.strip()
                        st.warning("Sorry! Please raise a ticket below.")
            else:
                st.markdown("#### ✦ No Answer Found")
                st.markdown("<div class='no-answer-box'>No answer found in the knowledge base. Please fill in the ticket details below and our team will help you.</div>", unsafe_allow_html=True)
                db_log_failed_query(question.strip())
                st.session_state["show_ticket"] = True
                st.session_state["ticket_query"] = question.strip()
    elif search:
        st.warning("Please enter a question.")

    st.markdown("---")

    if st.session_state.get("show_ticket", False):
        st.markdown("### Raise a Support Ticket")
        c1, c2 = st.columns(2)
        with c1:
            user_id  = st.text_input("Employee ID *", placeholder="e.g. EMP-1042", key="emp_user_id")
            job_role = st.selectbox("Job Role *", ["Select…","Software Engineer","Data Analyst","QA Engineer","DevOps Engineer","Product Manager","HR / Operations","Other"], key="emp_job_role")
        with c2:
            priority = st.selectbox("Priority *", ["Medium","High","Low"], key="emp_priority")

        original_question = st.session_state.get("ticket_query", "")
        if original_question:
            st.markdown(f"<small style='color:#8b3a2a;font-family:DM Mono,monospace;font-size:17px;letter-spacing:0.04em;'>Search query: {original_question}</small>", unsafe_allow_html=True)
        query_text = st.text_area("Describe your problem in detail *", value="", placeholder="Add more details about your issue…", height=120, key="emp_query_text")

        col_sub, col_cancel, _ = st.columns([1, 1, 4])
        with col_sub:
            if st.button("Submit Ticket →", use_container_width=True, key="emp_submit"):
                errors = []
                if not user_id.strip(): errors.append("Employee ID required.")
                if job_role == "Select…": errors.append("Select your job role.")
                if not original_question and not query_text.strip(): errors.append("Problem description required.")
                for e in errors: st.error(e)
                if not errors:
                    final_query = original_question if original_question else query_text.strip()
                    try:
                        t = db_create_ticket(user_id.strip(), job_role, final_query, priority)
                        st.toast(f"🎉 Ticket #{t.get('id')} submitted!", icon="✅")
                        st.success(f"Ticket #{t.get('id', '–')} submitted. Our team will respond shortly.")
                        st.session_state["show_ticket"] = False
                    except Exception as ex:
                        st.error(f"Failed: {ex}")
        with col_cancel:
            if st.button("Cancel", use_container_width=True, key="emp_cancel"):
                st.session_state["show_ticket"] = False
                st.rerun()


# ════════════════════════════════════════════════════════
#  ADMIN PAGE — 5 TABS
# ════════════════════════════════════════════════════════
def page_admin():
    ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")

    # ── Auth gate ─────────────────────────────────────────────────────────────
    if not st.session_state.get("admin_logged_in"):
        st.markdown("# Admin Panel")
        st.markdown("---")
        col, _ = st.columns([1.5, 2.5])
        with col:
            st.markdown(
                "<div style='background:#faf7f2;border:1px solid #d4c9bc;border-top:3px solid #8b3a2a;border-radius:3px;padding:28px 24px;'>"
                "<h3 style='font-family:Playfair Display,serif;margin-bottom:20px;'>Sign In</h3>",
                unsafe_allow_html=True,
            )
            pwd = st.text_input("Password", type="password", key="admin_pwd_input")
            if st.button("Continue →", use_container_width=True, key="admin_login_btn"):
                if pwd == ADMIN_PWD:
                    st.session_state["admin_logged_in"] = True
                    st.toast("Logged in successfully", icon="✅")
                    st.rerun()
                else:
                    st.error("Incorrect password.")
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── Header + logout ───────────────────────────────────────────────────────
    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown("# Admin Dashboard")
        st.markdown("<p style='color:#6b5f55;font-size:22px;margin-top:-8px;'>Manage tickets, monitor analytics, track knowledge gaps, control document visibility and oversee approval pipelines — all in one place.</p>", unsafe_allow_html=True)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign out", key="admin_logout_btn"):
            st.session_state["admin_logged_in"] = False
            st.toast("Signed out", icon="🔒")
            st.rerun()

    st.markdown("---")

    # ── 5 TABS ────────────────────────────────────────────────────────────────
    tab_tickets, tab_analytics, tab_knowledge, tab_docs, tab_pipeline = st.tabs([
        "🎫 Ticket Management",
        "📊 Analytics",
        "🕳️ Knowledge Gap",
        "📁 Doc Visibility",
        "📋 Approval Pipeline",
    ])

    with tab_tickets:
        _admin_ticket_management()

    with tab_analytics:
        _admin_analytics()

    with tab_knowledge:
        _admin_knowledge_gap()

    with tab_docs:
        _admin_doc_visibility()

    with tab_pipeline:
        _admin_approval_pipeline()


# ════════════════════════════════════════════════════════
#  TAB 1 — TICKET MANAGEMENT
# ════════════════════════════════════════════════════════
def _admin_ticket_management():
    try:
        stats = db_stats()
        cols  = st.columns(5)
        for col, val, label, icon in zip(
            cols,
            [stats["total"], stats["open"], stats["in_progress"], stats["resolved"], stats["overdue"]],
            ["Total","Open","In Progress","Resolved","Overdue"],
            ["📋","○","◑","●","⚠"],
        ):
            with col:
                st.markdown(f"<div class='metric-card'><div class='metric-number'>{val}</div><div class='metric-label'>{icon} {label}</div></div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Stats error: {e}")

    st.markdown("---")

    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1])
    with c1:
        sf = st.selectbox("Status", ["All","Open","In Progress","Resolved","Overdue"], key="admin_filter_status")
    with c2:
        pf = st.selectbox("Priority", ["All","High","Medium","Low"], key="admin_filter_priority")
    with c3:
        search_term = st.text_input("Search tickets", placeholder="keyword / employee ID", key="admin_search_term")
    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        export_btn = st.button("Export CSV", use_container_width=True, key="admin_export_btn")

    try:
        tickets = db_get_tickets(sf if sf not in ["All","Overdue"] else None)
    except Exception as e:
        st.error(f"DB error: {e}")
        return

    if sf == "Overdue":
        tickets = [t for t in tickets if t.get("status") == "Open" and is_overdue(t.get("created_at", ""))]
    if pf != "All":
        tickets = [t for t in tickets if t.get("priority") == pf]
    if search_term.strip():
        kw = search_term.strip().lower()
        tickets = [t for t in tickets if kw in t.get("query","").lower() or kw in t.get("user_id","").lower()]

    if export_btn:
        all_tickets = db_get_tickets()
        csv_bytes   = tickets_to_csv(all_tickets)
        st.download_button("⬇ Download CSV", data=csv_bytes, file_name="helpdesk_tickets.csv", mime="text/csv", key="admin_download_csv")
        st.toast("CSV exported", icon="✅")

    if not tickets:
        st.info("No tickets found.", icon="📭")
        return

    st.markdown(f"<p style='font-family:DM Mono,monospace;font-size:16px;color:#9c8e82;letter-spacing:0.06em;text-transform:uppercase;'>{len(tickets)} ticket(s)</p>", unsafe_allow_html=True)

    for t in tickets:
        tid          = t.get("id")
        status       = t.get("status", "Open")
        priority     = t.get("priority", "Medium")
        created      = t.get("created_at", "")
        overdue      = is_overdue(created) and status == "Open"
        ticket_query = t.get("query", "")
        try:
            created_fmt = _to_ist(created)
        except Exception:
            created_fmt = created

        badge_class    = "badge-overdue" if overdue else {"Open":"badge-open","In Progress":"badge-inprogress","Resolved":"badge-resolved"}.get(status,"badge-open")
        display_status = "OVERDUE" if overdue else status
        prio_class     = {"High":"prio-high","Medium":"prio-medium","Low":"prio-low"}.get(priority,"prio-medium")

        with st.expander(f"#{tid} — {t.get('user_id','?')} · {t.get('job_role','?')} · {display_status} · {priority} · {created_fmt}"):
            st.markdown(f"<span class='{badge_class}'>{display_status}</span>&nbsp;&nbsp;<span class='{prio_class}'>{priority}</span>", unsafe_allow_html=True)
            st.markdown(f"**Employee:** {t.get('user_id','–')} &nbsp;·&nbsp; **Role:** {t.get('job_role','–')} &nbsp;·&nbsp; **Submitted:** {created_fmt}")
            st.markdown("**Timeline:**")
            st.markdown(f"<span class='timeline-dot' style='background:#8b3a2a'></span> Opened — {created_fmt}", unsafe_allow_html=True)
            if status == "In Progress":
                st.markdown(f"<span class='timeline-dot' style='background:#2d3d4f'></span> In Progress", unsafe_allow_html=True)
            if status == "Resolved":
                st.markdown(f"<span class='timeline-dot' style='background:#3d5a4a'></span> Resolved ✓", unsafe_allow_html=True)
            if overdue:
                st.markdown(f"<span class='timeline-dot' style='background:#8b3a2a'></span> ⚠ Overdue — open for more than 24 hours", unsafe_allow_html=True)
            st.markdown("**Problem:**")
            st.markdown(f"<div class='answer-box'>{ticket_query}</div>", unsafe_allow_html=True)
            st.markdown("---")

            nc1, nc2 = st.columns(2)
            with nc1:
                new_status = st.selectbox("Update Status", ["Open","In Progress","Resolved"],
                    index=["Open","In Progress","Resolved"].index(status), key=f"admin_s_{tid}")
            with nc2:
                prefill_note = st.session_state.pop(f"admin_prefill_{tid}", None)
                default_note = prefill_note if prefill_note is not None else (t.get("admin_note") or "")
                note = st.text_area("Admin Note / Solution", value=default_note, key=f"admin_n_{tid}", height=100, placeholder="Write solution here…")

            bc1, bc2, _, _ = st.columns([1, 1, 1.5, 1])
            with bc1:
                if st.button("Save", key=f"admin_save_{tid}", use_container_width=True):
                    try:
                        db_update_ticket(tid, new_status, note)
                        if note.strip():
                            auto_save_note_to_resolved(ticket_query, note)
                        st.success("Ticket updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with bc2:
                if st.button("Delete", key=f"admin_del_{tid}", use_container_width=True):
                    try:
                        db_delete_ticket(tid)
                        st.warning("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))


# ════════════════════════════════════════════════════════
#  TAB 2 — ANALYTICS
# ════════════════════════════════════════════════════════
def _admin_analytics():
    try:
        import plotly.express as px
        import pandas as pd
    except ImportError:
        st.error("Please install plotly and pandas.")
        return

    tickets = db_get_tickets()
    if not tickets:
        st.info("No ticket data yet.")
        return

    df = pd.DataFrame(tickets)
    df["created_at"]     = pd.to_datetime(df["created_at"], utc=True)
    df["created_at_ist"] = df["created_at"] + pd.Timedelta(hours=5, minutes=30)
    df["date"]           = df["created_at_ist"].dt.strftime("%d %b %Y")

    col1, col2, col3, col4 = st.columns(4)
    resolved        = df[df["status"] == "Resolved"]
    resolution_rate = round(len(resolved) / len(df) * 100, 1) if len(df) else 0

    with col1: st.markdown(f"<div class='metric-card'><div class='metric-number'>{len(df)}</div><div class='metric-label'>Total Tickets</div></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><div class='metric-number'>{resolution_rate}%</div><div class='metric-label'>Resolution Rate</div></div>", unsafe_allow_html=True)
    with col3:
        open_count = len(df[df["status"] == "Open"])
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{open_count}</div><div class='metric-label'>Open Tickets</div></div>", unsafe_allow_html=True)
    with col4:
        high_prio = len(df[df["priority"] == "High"])
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{high_prio}</div><div class='metric-label'>High Priority</div></div>", unsafe_allow_html=True)

    RUST = "#8b3a2a"; SAGE = "#3d5a4a"; AMBER = "#8b6914"; SLATE = "#2d3d4f"
    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### Tickets Per Day")
        daily = df.groupby("date").size().reset_index(name="count")
        fig1  = px.bar(daily, x="date", y="count", color_discrete_sequence=[RUST], text="count")
        fig1.update_layout(xaxis_title="", yaxis_title="", plot_bgcolor="#faf7f2", paper_bgcolor="#faf7f2",
            margin=dict(t=20, b=80), bargap=0.4, font=dict(family="EB Garamond", color="#3d3530", size=18),
            xaxis=dict(tickangle=-35, type="category", tickfont=dict(size=16), gridcolor="#e8e0d0"),
            yaxis=dict(tickformat="d", dtick=1, gridcolor="#e8e0d0"))
        fig1.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.markdown("### Ticket Status Breakdown")
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status","count"]
        fig2 = px.pie(status_counts, names="status", values="count", color="status",
            color_discrete_map={"Open": AMBER, "In Progress": SLATE, "Resolved": SAGE}, hole=0.4)
        fig2.update_traces(textinfo="label+percent", textfont_size=18)
        fig2.update_layout(margin=dict(t=20), paper_bgcolor="#faf7f2",
            font=dict(family="EB Garamond", color="#3d3530", size=18),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("### Tickets by Priority")
        prio_order  = ["High","Medium","Low"]
        prio_counts = df["priority"].value_counts().reindex(prio_order, fill_value=0).reset_index()
        prio_counts.columns = ["priority","count"]
        fig3 = px.bar(prio_counts, x="priority", y="count", color="priority",
            color_discrete_map={"High": RUST, "Medium": AMBER, "Low": SAGE},
            text="count", category_orders={"priority": prio_order})
        fig3.update_layout(showlegend=False, plot_bgcolor="#faf7f2", paper_bgcolor="#faf7f2",
            margin=dict(t=20), bargap=0.45, font=dict(family="EB Garamond", color="#3d3530", size=18),
            xaxis=dict(title="", gridcolor="#e8e0d0"), yaxis=dict(title="", tickformat="d", dtick=1, gridcolor="#e8e0d0"))
        fig3.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown("### Tickets by Job Role")
        role_counts = df["job_role"].value_counts().reset_index()
        role_counts.columns = ["role","count"]
        fig4 = px.bar(role_counts, x="count", y="role", orientation="h", color_discrete_sequence=[SLATE], text="count")
        fig4.update_layout(xaxis=dict(title="", tickformat="d", dtick=1, gridcolor="#e8e0d0"),
            yaxis_title="", plot_bgcolor="#faf7f2", paper_bgcolor="#faf7f2",
            margin=dict(t=20, l=140), bargap=0.35,
            font=dict(family="EB Garamond", color="#3d3530", size=18),
            height=max(300, len(role_counts) * 50))
        fig4.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("---")
    csv_bytes = tickets_to_csv(tickets)
    st.download_button("⬇ Download All Tickets as CSV", data=csv_bytes, file_name="helpdesk_tickets.csv", mime="text/csv", key="analytics_download_csv")


# ════════════════════════════════════════════════════════
#  TAB 3 — KNOWLEDGE GAP
# ════════════════════════════════════════════════════════
def _admin_knowledge_gap():
    st.markdown("<p style='color:#6b5f55;font-size:26px;font-family:EB Garamond,serif;'>Questions employees asked that the system couldn't answer.</p>", unsafe_allow_html=True)
    st.markdown("---")

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
        st.success("No knowledge gaps yet — every question has been answered.", icon="✅")
        return

    queries = [r["query"] for r in rows]
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{len(queries)}</div><div class='metric-label'>Total Unanswered</div></div>", unsafe_allow_html=True)
    with col2:
        unique = len(set(q.lower().strip() for q in queries))
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{unique}</div><div class='metric-label'>Unique Questions</div></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### All Unanswered Questions")
    for i, row in enumerate(rows, 1):
        try:
            date_fmt = _to_ist(row.get("created_at", ""))
        except Exception:
            date_fmt = row.get("created_at", "")
        st.markdown(f"<div class='gap-card'><span class='gap-count'>#{i:02d}</span> &nbsp;<strong style='font-family:EB Garamond,serif;font-size:24px;'>{row['query']}</strong><br><small style='color:#9c8e82;font-family:DM Mono,monospace;font-size:17px;'>Asked {date_fmt}</small></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Most Requested Missing Topics")
    all_words = []
    for q in queries:
        all_words.extend(_content_words(q))
    word_freq = Counter(all_words).most_common(15)

    if word_freq:
        try:
            import plotly.express as px
            import pandas as pd
            wdf = pd.DataFrame(word_freq, columns=["keyword","count"])
            fig = px.bar(wdf, x="count", y="keyword", orientation="h", color_discrete_sequence=["#8b3a2a"], text="count")
            fig.update_layout(xaxis=dict(title="", tickformat="d", dtick=1, gridcolor="#e8e0d0"),
                yaxis_title="", plot_bgcolor="#faf7f2", paper_bgcolor="#faf7f2",
                margin=dict(t=10, l=120), font=dict(family="EB Garamond", color="#3d3530", size=18),
                height=max(300, len(wdf) * 40), bargap=0.35)
            fig.update_traces(textposition="outside", marker_line_width=0)
            fig.update_yaxes(autorange="reversed", tickfont=dict(size=17))
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            for word, count in word_freq:
                st.markdown(f"**{word}** — {count} time(s)")

    st.markdown("---")
    if st.button("Clear All Failed Queries", key="gap_clear_btn"):
        try:
            db.table("failed_queries").delete().neq("id", 0).execute()
            st.toast("Cleared all failed queries", icon="✅")
            st.success("Cleared.")
            st.rerun()
        except Exception as e:
            st.error(str(e))


# ════════════════════════════════════════════════════════
#  TAB 4 — DOC VISIBILITY (full admin view)
# ════════════════════════════════════════════════════════
def _admin_doc_visibility():
    st.markdown("<p style='color:#6b5f55;font-size:26px;font-family:EB Garamond,serif;'>Role-based document library. Manage documents and review access requests.</p>", unsafe_allow_html=True)

    st.markdown("""
    <div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:20px;padding:16px 20px;background:var(--paper);border:1px solid var(--border);border-radius:3px;'>
        <span style='font-family:DM Mono,monospace;font-size:14px;color:var(--ink-faint);letter-spacing:0.1em;text-transform:uppercase;margin-right:4px;'>Hierarchy</span>
        <span class='role-badge role-emp'>Employee</span><span style='color:var(--ink-faint);'>→</span>
        <span class='role-badge role-mgr'>Manager</span><span style='color:var(--ink-faint);'>→</span>
        <span class='role-badge role-tech'>Tech Manager</span><span style='color:var(--ink-faint);'>→</span>
        <span class='role-badge role-cto'>CTO</span><span style='color:var(--ink-faint);'>→</span>
        <span class='role-badge role-ceo'>CEO</span>
        &nbsp;&nbsp;<span style='font-family:DM Mono,monospace;font-size:15px;color:#3d5a4a;letter-spacing:0.06em;'>CTO &amp; CEO: instant access · Others: request required for restricted docs</span>
    </div>
    """, unsafe_allow_html=True)

    dv_lib1, dv_lib2, dv_lib3 = st.tabs(["Add Document","All Documents","Access Requests"])

    with dv_lib1:
        st.markdown("#### Add a New Document")
        with st.form("add_doc_form", clear_on_submit=True):
            fa1, fa2 = st.columns(2)
            with fa1:
                doc_title    = st.text_input("Document Title *", placeholder="e.g. VPN Access Policy")
                doc_cat      = st.selectbox("Category", ["General","Security","HR","Finance","Engineering","Legal","Operations"])
                doc_sens     = st.selectbox("Sensitivity Level", ["Normal","Restricted","Confidential","Top Secret"])
            with fa2:
                doc_min_role = st.selectbox("Minimum Role to View", ROLE_HIERARCHY, index=0)
                doc_owner    = st.text_input("Owner ID", placeholder="e.g. EMP-0001")
                doc_url      = st.text_input("File URL (optional)", placeholder="https://…")
            doc_desc    = st.text_area("Description", placeholder="What does this document cover?", height=80)
            doc_preview = st.text_area("Content Preview (shown to authorised users)", placeholder="A summary or excerpt…", height=100)
            submit_doc  = st.form_submit_button("Add Document →", type="primary")

        if submit_doc:
            if not doc_title.strip():
                st.warning("Document title is required.")
            else:
                try:
                    added = db_add_document(doc_title.strip(), doc_desc.strip(), doc_cat,
                                            doc_sens, doc_min_role, doc_owner.strip(),
                                            doc_url.strip(), doc_preview.strip())
                    st.success(f"Document '{added['title']}' added (ID #{added['id']}).")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed: {ex}")

    with dv_lib2:
        st.markdown("#### All Documents in Library")
        docs = db_get_documents()
        if not docs:
            st.info("No documents yet.")
        else:
            st.markdown(f"<p style='font-family:DM Mono,monospace;font-size:16px;color:#9c8e82;letter-spacing:0.06em;text-transform:uppercase;'>{len(docs)} document(s)</p>", unsafe_allow_html=True)
            for doc in docs:
                doc_id      = doc["id"]
                sensitivity = doc.get("sensitivity","Normal")
                min_role    = doc.get("min_role","Employee")
                role_cls    = _role_badge_class(min_role)
                s_color     = _sensitivity_color(sensitivity)
                s_bg        = _sensitivity_bg(sensitivity)

                with st.expander(f"#{doc_id} — {doc['title']}  ·  {doc.get('category','General')}  ·  {min_role}+  ·  {sensitivity}"):
                    st.markdown(f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;'><span class='role-badge {role_cls}'>{min_role}+</span><span style='display:inline-block;background:{s_bg};color:{s_color};border-radius:2px;padding:2px 10px;font-size:14px;font-family:DM Mono,monospace;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;'>{sensitivity}</span></div>", unsafe_allow_html=True)
                    if doc.get("description"): st.markdown(f"**Description:** {doc['description']}")
                    if doc.get("content_preview"): st.markdown(f"**Preview:** {doc['content_preview'][:200]}…")
                    if doc.get("file_url"): st.markdown(f"📎 **URL:** {doc['file_url']}")
                    st.markdown(f"<small style='color:#9c8e82;font-family:DM Mono,monospace;'>Owner: {doc.get('owner_id','—')} · Added: {_to_ist(doc.get('created_at',''))}</small>", unsafe_allow_html=True)

                    # Active grants
                    grants_for_doc = db_get_access_grants(doc_id=doc_id)
                    now            = datetime.now(timezone.utc)
                    active_here    = []
                    for g in grants_for_doc:
                        if g.get("status") != "Approved": continue
                        try:
                            exp = datetime.fromisoformat(g["expires_at"].replace("Z","+00:00"))
                            if exp > now: active_here.append((g, exp))
                        except Exception: pass

                    if active_here:
                        st.markdown(f"**Active grants ({len(active_here)}):**")
                        for g, exp in active_here:
                            days_left = (exp - now).days
                            gc1, gc2  = st.columns([4, 1])
                            with gc1:
                                st.markdown(f"<small style='font-family:DM Mono,monospace;font-size:17px;'>👤 {g['user_id']} ({g['user_role']}) — {days_left}d left — granted by {g.get('granted_by','—')}</small>", unsafe_allow_html=True)
                            with gc2:
                                if st.button("Revoke", key=f"revoke_{g['id']}", use_container_width=True):
                                    db_revoke_access(g["id"]); st.rerun()

                    dc1, _ = st.columns([1, 5])
                    with dc1:
                        if st.button("Delete Document", key=f"del_doc_{doc_id}", use_container_width=True):
                            try:
                                db_delete_document(doc_id)
                                st.warning("Deleted.")
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))

    with dv_lib3:
        st.markdown("#### Document Access Requests")
        rf1, rf2 = st.columns(2)
        with rf1:
            req_status_filter = st.selectbox("Filter by Status", ["All","Pending","Approved","Rejected"], key="req_status_filter")
        with rf2:
            reviewer_id = st.text_input("Reviewer ID (your ID)", placeholder="e.g. CTO-001", key="reviewer_id")

        reqs     = db_get_access_requests(status_filter=req_status_filter)
        docs_map = {d["id"]: d for d in db_get_documents()}

        if not reqs:
            st.info("No access requests found.")
        else:
            pending_reqs = [r for r in reqs if r["status"] == "Pending"]
            other_reqs   = [r for r in reqs if r["status"] != "Pending"]

            if pending_reqs:
                st.markdown(f"<p style='font-family:DM Mono,monospace;font-size:16px;color:#8b6914;letter-spacing:0.06em;'>{len(pending_reqs)} pending request(s) awaiting review</p>", unsafe_allow_html=True)
                for req in pending_reqs:
                    doc       = docs_map.get(req["doc_id"])
                    doc_title = doc["title"] if doc else f"Doc #{req['doc_id']}"
                    req_id    = req["id"]
                    with st.expander(f"⏳ #{req_id} — {req['user_id']} ({req['user_role']}) → {doc_title}"):
                        st.markdown(f"**Employee:** {req['user_id']} &nbsp;·&nbsp; **Role:** {req['user_role']}")
                        st.markdown(f"**Document:** {doc_title} &nbsp;·&nbsp; Min role: {doc.get('min_role','?') if doc else '?'}")
                        st.markdown(f"**Reason:** {req.get('reason','—')}")
                        st.markdown(f"**Requested:** {_to_ist(req.get('created_at',''))}")
                        if doc:
                            sens = doc.get("sensitivity","Normal"); min_r = doc.get("min_role","Employee")
                            s_color = _sensitivity_color(sens); s_bg = _sensitivity_bg(sens)
                            st.markdown(f"<div style='margin:8px 0;display:flex;gap:8px;'><span class='role-badge {_role_badge_class(min_r)}'>{min_r}+</span><span style='background:{s_bg};color:{s_color};border-radius:2px;padding:2px 10px;font-size:14px;font-family:DM Mono,monospace;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;'>{sens}</span></div>", unsafe_allow_html=True)
                        ac1, ac2, _ = st.columns([1, 1, 4])
                        with ac1:
                            if st.button("Approve — Grant 7-day Access", key=f"approve_{req_id}", use_container_width=True):
                                if not reviewer_id.strip():
                                    st.warning("Enter your Reviewer ID first.")
                                else:
                                    db_review_access_request(req_id, "Approved", reviewer_id.strip(),
                                        doc_id=req["doc_id"], user_id=req["user_id"], user_role=req["user_role"])
                                    st.success(f"Access approved. {req['user_id']} has 7-day access.")
                                    st.rerun()
                        with ac2:
                            if st.button("Reject", key=f"reject_{req_id}", use_container_width=True):
                                if not reviewer_id.strip():
                                    st.warning("Enter your Reviewer ID first.")
                                else:
                                    db_review_access_request(req_id, "Rejected", reviewer_id.strip())
                                    st.warning("Request rejected.")
                                    st.rerun()

            if other_reqs and req_status_filter != "Pending":
                st.markdown("---")
                st.markdown("#### Past Requests")
                for req in other_reqs:
                    doc       = docs_map.get(req["doc_id"])
                    doc_title = doc["title"] if doc else f"Doc #{req['doc_id']}"
                    status    = req["status"]
                    s_color   = {"Approved":"#3d5a4a","Rejected":"#8b3a2a"}.get(status, "#6b5f55")
                    st.markdown(f"<div class='doc-card' style='padding:12px 16px;'>#{req['id']} &nbsp;·&nbsp; <strong>{req['user_id']}</strong> ({req['user_role']}) → {doc_title} &nbsp;&nbsp;<span style='color:{s_color};font-family:DM Mono,monospace;font-size:15px;text-transform:uppercase;'>{status}</span><br><small style='color:#9c8e82;font-family:DM Mono,monospace;font-size:17px;'>Reviewed by {req.get('reviewed_by','—')} on {_to_ist(req.get('reviewed_at',''))}</small></div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  TAB 5 — APPROVAL PIPELINE (Approver Review)
# ════════════════════════════════════════════════════════
def _admin_approval_pipeline():
    if not PIPELINE_AVAILABLE:
        st.error("`approval_pipeline.py` is missing. Please add it to your project folder.")
        return

    st.markdown("<p style='color:#6b5f55;font-size:24px;font-family:EB Garamond,serif;'>Review and action all document approval requests. Each approver logs in to their role tab below.</p>", unsafe_allow_html=True)

    # ── Init + load ───────────────────────────────────────────────────────────
    _ap_init()
    if not st.session_state.ap_loaded:
        _ap_load_requests()

    # ── Migrate stale chains ──────────────────────────────────────────────────
    for r in st.session_state.ap_requests:
        if _migrate_chain(r):
            _ap_db_update(r)

    # ── Auto-escalation ───────────────────────────────────────────────────────
    escalated = []
    for r in st.session_state.ap_requests:
        bi, bd = r.get("stage_idx", 0), r.get("done", False)
        _check_expiry(r)
        if r.get("stage_idx", 0) != bi or (r.get("done") and not bd):
            escalated.append(r)

    if escalated:
        msgs = []
        for r in escalated:
            last = r["history"][-1] if r["history"] else {}
            msgs.append(f"⚠️ **Auto-escalated {r['id']}: {r['title']}** — {last.get('action','')}")
        st.session_state.ap_escalation_msgs = msgs
        st.rerun()

    for msg in st.session_state.get("ap_escalation_msgs", []):
        st.markdown(f"<div class='ap-escalation-banner'>{msg}</div>", unsafe_allow_html=True)
    st.session_state.ap_escalation_msgs = []

    # ── Refresh button ────────────────────────────────────────────────────────
    rc1, rc2 = st.columns([5, 1])
    with rc2:
        if st.button("🔄 Refresh", use_container_width=True, key="admin_ap_refresh"):
            _ap_load_requests(); st.rerun()

    st.markdown("---")

    # ── Policy box ────────────────────────────────────────────────────────────
    try:
        esc_label = _escalation_label()
    except Exception:
        esc_label = "1 week (168h)"

    st.markdown(f"""
    <div class="ap-policy-box">
      <div style="font-size:15px;font-weight:700;color:#92400e;margin-bottom:8px;">⏳ Auto-Escalation Policy — {esc_label} per approver, then moves to the next level</div>
      <p style="font-size:13px;color:#92400e;margin:0 0 10px;">
        Each approver has <strong>{esc_label}</strong> to respond.
        If they don't, the request <strong>moves up one level</strong> automatically.
        If the final approver also times out, the request is <strong>Expired</strong>.
      </p>
      <table style="font-size:13px;color:#92400e;border-collapse:collapse;width:100%">
        <tr style="border-bottom:1px solid #fcd34d">
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">⚙️ Technical</td>
          <td style="padding:6px 10px;">
            <span class="ap-chain-role">Team Lead</span><span class="ap-chain-arrow">→</span>
            <span class="ap-timer-chip">⏳ {esc_label}</span><span class="ap-chain-arrow">→</span>
            <span class="ap-chain-role">Tech Manager</span><span class="ap-chain-arrow">→</span>
            <span class="ap-timer-chip">⏳ {esc_label}</span><span class="ap-chain-arrow">→</span>
            <span class="ap-chain-role">CTO</span>
          </td>
        </tr>
        <tr style="border-bottom:1px solid #fcd34d">
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">🔧 Operations</td>
          <td style="padding:6px 10px;">
            <span class="ap-chain-role">Team Lead</span><span class="ap-chain-arrow">→</span>
            <span class="ap-timer-chip">⏳ {esc_label}</span><span class="ap-chain-arrow">→</span>
            <span class="ap-chain-role">Tech Manager</span>
          </td>
        </tr>
        <tr style="border-bottom:1px solid #fcd34d">
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">🔒 Security</td>
          <td style="padding:6px 10px;">
            <span class="ap-chain-role">Team Lead</span><span class="ap-chain-arrow">→</span>
            <span class="ap-timer-chip">⏳ {esc_label}</span><span class="ap-chain-arrow">→</span>
            <span class="ap-chain-role">Tech Manager</span><span class="ap-chain-arrow">→</span>
            <span class="ap-timer-chip">⏳ {esc_label}</span><span class="ap-chain-arrow">→</span>
            <span class="ap-chain-role">CTO</span><span class="ap-chain-arrow">→</span>
            <span class="ap-timer-chip">⏳ {esc_label}</span><span class="ap-chain-arrow">→</span>
            <span class="ap-chain-role">CEO</span>
          </td>
        </tr>
        <tr>
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">👥 Team</td>
          <td style="padding:6px 10px;">
            <span class="ap-chain-role">Team Lead</span>
            <span style="font-size:11px;color:#b45309;margin-left:8px;">Single approver — expires if no response</span>
          </td>
        </tr>
      </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Pipeline summary stats ────────────────────────────────────────────────
    all_reqs = st.session_state.ap_requests
    if all_reqs:
        counts = {"Pending": 0, "Approved": 0, "Rejected": 0, "Expired": 0}
        for r in all_reqs:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("🟡 Pending",  counts["Pending"])
        mc2.metric("🟢 Approved", counts["Approved"])
        mc3.metric("🔴 Rejected", counts["Rejected"])
        mc4.metric("⏰ Expired",  counts["Expired"])
        st.markdown("---")

    # ── Role tabs with live pending counts ────────────────────────────────────
    def _n(role):
        return sum(1 for r in st.session_state.ap_requests
                   if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role)

    role_tabs = st.tabs([
        f"👨‍💼 Team Lead ({_n('Team Lead')})",
        f"👩‍💻 Tech Manager ({_n('Tech Manager')})",
        f"🧑‍🔬 CTO ({_n('CTO')})",
        f"👑 CEO ({_n('CEO')})",
    ])
    with role_tabs[0]: _view_role("Team Lead")
    with role_tabs[1]: _view_role("Tech Manager")
    with role_tabs[2]: _view_role("CTO")
    with role_tabs[3]: _view_role("CEO")


# ════════════════════════════════════════════════════════
#  SETUP PAGE
# ════════════════════════════════════════════════════════
def page_setup():
    st.markdown("# Setup & Configuration")
    with st.expander("Streamlit Secrets", expanded=True):
        st.code('[secrets]\nSUPABASE_URL   = "https://xxxx.supabase.co"\nSUPABASE_KEY   = "eyJ..."\nADMIN_PASSWORD = "your_password"', language="toml")
    with st.expander("Create Supabase Tables (run all)", expanded=True):
        st.code(SCHEMA_SQL, language="sql")
    with st.expander("Install Dependencies"):
        st.code("pip install streamlit supabase pdfplumber sentence-transformers requests torch plotly pandas", language="bash")

    st.markdown("---")
    st.markdown("### Connection Status")
    c1, c2 = st.columns(2)
    with c1:
        if st.secrets.get("SUPABASE_URL", ""): st.success("Supabase URL configured")
        else: st.error("Supabase URL missing")
    with c2:
        if st.secrets.get("SUPABASE_KEY", ""): st.success("Supabase Key configured")
        else: st.error("Supabase Key missing")

    st.markdown("---")
    if st.button("Test Database Connection", key="setup_test_db"):
        try:
            db = get_db()
            if db is None: st.error("Not configured.")
            else:
                db.table("tickets").select("id").limit(1).execute()
                st.success("Database connected!")
        except Exception as e:
            st.error(f"Failed: {e}")


# ════════════════════════════════════════════════════════
#  SIDEBAR + ROUTING  (only 2 main pages + setup)
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='padding: 8px 0 20px;'>
        <div style='display: flex; align-items: center; gap: 10px;'>
            <div style='width: 34px; height: 34px; background: #8b3a2a; border-radius: 2px;
                        display: flex; align-items: center; justify-content: center;'>
                <span style='color: white; font-size: 18px; font-weight: 700; font-family: Playfair Display, serif;'>H</span>
            </div>
            <div>
                <p style='margin:0; font-family: Playfair Display, serif; font-size:20px; font-weight:700; color: #f5f0e8; letter-spacing: -0.01em;'>HelpDesk Pro</p>
                <p style='margin:0; font-family: DM Mono, monospace; font-size:12px; color: #6b5f55; letter-spacing: 0.1em; text-transform: uppercase;'>Knowledge · Support</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<p style='font-family:DM Mono,monospace;font-size:13px;color:#3a3028;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px;'>Navigate</p>", unsafe_allow_html=True)

    page = st.radio("Navigation", [
        "🔍 Employee Portal",
        "🛡️ Admin Panel",
        "⚙️ Setup / Config",
    ], label_visibility="collapsed")

    st.markdown("---")

    # Show admin capabilities hint if admin is logged in
    if st.session_state.get("admin_logged_in"):
        st.markdown("""
        <div style='margin-top:8px;'>
            <p style='font-family:DM Mono,monospace;font-size:11px;color:#3a3028;letter-spacing:0.10em;text-transform:uppercase;margin-bottom:8px;'>Admin Capabilities</p>
        """, unsafe_allow_html=True)
        capabilities = [
            "View & manage all tickets",
            "Update ticket status",
            "Add solutions & notes",
            "Export data as CSV",
            "Monitor analytics",
            "Manage document library",
            "Review access requests",
            "Approve pipeline requests",
            "Track request history",
        ]
        for cap in capabilities:
            st.markdown(f"<p style='font-family:EB Garamond,serif;font-size:14px;color:#6b5f55;margin:3px 0;padding-left:8px;border-left:2px solid #8b3a2a;'>{'  ' + cap}</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if not PIPELINE_AVAILABLE:
        st.markdown("---")
        st.warning("approval_pipeline.py not found.", icon="⚠️")

    st.markdown("<p style='font-family:DM Mono,monospace;font-size:13px;color:#3a3028;letter-spacing:0.06em;margin-top:16px;'>Powered by Supabase + pdfplumber</p>", unsafe_allow_html=True)


# ── Routing ───────────────────────────────────────────────────────────────────
if page == "🔍 Employee Portal":
    page_employee()
elif page == "🛡️ Admin Panel":
    page_admin()
elif page == "⚙️ Setup / Config":
    page_setup()
