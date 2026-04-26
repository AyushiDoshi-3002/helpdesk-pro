import streamlit as st
import re
import io
import requests
from datetime import datetime

st.set_page_config(
    page_title="HelpDesk Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f0c29, #302b63, #24243e); }
section[data-testid="stSidebar"] * { color: white !important; }
.main { background: #f8f7ff; }
.answer-box {
    background: linear-gradient(135deg, #ede9fe, #ddd6fe);
    border-radius: 12px; padding: 20px;
    border-left: 4px solid #7c3aed;
    font-size: 15px; line-height: 1.7; color: #1e1b4b;
}
.no-answer-box {
    background: #fff7ed; border-radius: 12px; padding: 16px 20px;
    border-left: 4px solid #f97316; color: #7c2d12; font-size: 14px;
}
.badge-open { background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-inprogress { background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-resolved { background:#d1fae5;color:#065f46;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.prio-high { background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-medium { background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-low { background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
div.stButton > button {
    background: linear-gradient(135deg, #7c3aed, #5b21b6);
    color: white; border: none; border-radius: 10px;
    padding: 10px 24px; font-weight: 600; font-size: 14px;
}
div.stButton > button:hover { background: linear-gradient(135deg, #6d28d9, #4c1d95); }
.metric-card { background:white;border-radius:14px;padding:20px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,0.06); }
.metric-number { font-family:'Syne',sans-serif;font-size:36px;font-weight:800;color:#7c3aed; }
.metric-label { font-size:13px;color:#6b7280;margin-top:4px; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  SUPABASE CONFIG
# ════════════════════════════════════════════════════════
SUPABASE_URL = "https://jvulbphmksdebkkkhgvh.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dWxicGhta3NkZWJra2toZ3ZoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxOTg4ODQsImV4cCI6MjA5Mjc3NDg4NH0"
    ".REhaZ0M8pg_9hkaIJxYNmErIsy6UARTYyzYkQbr0pT4"
)
ADMIN_PASSWORD = "admin123"


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
    priority    TEXT NOT NULL CHECK (priority IN ('High','Medium','Low')),
    status      TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','In Progress','Resolved')),
    admin_note  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

@st.cache_resource(show_spinner=False)
def get_db():
    if not SUPABASE_OK:
        st.error("❌ supabase-py not installed. Run: pip install supabase")
        return None
    # Try secrets first, fall back to hardcoded constants
    url = st.secrets.get("SUPABASE_URL", SUPABASE_URL).strip()
    key = st.secrets.get("SUPABASE_KEY", SUPABASE_KEY).strip()
    if not url or not key:
        st.error("❌ Supabase URL or Key is empty.")
        return None
    try:
        client = create_client(url, key)
        return client
    except Exception as e:
        st.error(f"❌ Failed to create Supabase client: {e}")
        return None

def db_create_ticket(user_id, job_role, query, priority):
    db = get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    row = {
        "user_id": user_id,
        "job_role": job_role,
        "query": query,
        "priority": priority,
        "status": "Open",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    result = db.table("tickets").insert(row).execute()
    return result.data[0] if result.data else {}

def db_get_tickets(status_filter=None):
    db = get_db()
    if db is None:
        return []
    q = db.table("tickets").select("*").order("created_at", desc=True)
    if status_filter and status_filter != "All":
        q = q.eq("status", status_filter)
    return q.execute().data or []

def db_update_ticket(tid, status, note):
    db = get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    db.table("tickets").update({
        "status": status,
        "admin_note": note,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", tid).execute()

def db_delete_ticket(tid):
    db = get_db()
    if db:
        db.table("tickets").delete().eq("id", tid).execute()

def db_stats():
    tickets = db_get_tickets()
    return {
        "total": len(tickets),
        "open": sum(1 for t in tickets if t["status"] == "Open"),
        "in_progress": sum(1 for t in tickets if t["status"] == "In Progress"),
        "resolved": sum(1 for t in tickets if t["status"] == "Resolved"),
    }


# ════════════════════════════════════════════════════════
#  Q&A ENGINE
# ════════════════════════════════════════════════════════
_GDRIVE_FILE_ID = "1cUagShzCe0XsCbF5NEU9T62ICcU2I5AO"
PDF_URL = f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}"

@st.cache_resource(show_spinner="📄 Loading knowledge base…")
def load_qa_pairs():
    text = _fetch_pdf()
    return _parse_qa(text)

def _fetch_pdf():
    try:
        import PyPDF2
        resp = requests.get(PDF_URL, timeout=30)
        resp.raise_for_status()
        reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception as e:
        st.warning(f"Using built-in Q&A ({e})")
        return _fallback_text()

def _parse_qa(text):
    parts = re.split(r'\n\s*(\d{1,3})\.\s+', text)
    pairs = []
    i = 1
    while i < len(parts) - 1:
        num = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        i += 2
        if not content:
            continue
        lines = content.split('\n')
        q_lines, a_lines, in_q = [], [], True
        for line in lines:
            line = line.strip()
            if not line:
                in_q = False
                continue
            if in_q and (line.endswith('?') or len(q_lines) > 2):
                q_lines.append(line)
                in_q = False
            elif in_q:
                q_lines.append(line)
            else:
                a_lines.append(line)
        q = " ".join(q_lines).strip()
        a = " ".join(a_lines).strip()
        if len(q) >= 5 and a:
            pairs.append({"num": num, "question": q, "answer": a})
    return pairs if pairs else _parse_qa(_fallback_text())

def answer_question(query):
    pairs = load_qa_pairs()
    q_lower = query.lower()
    q_words = set(re.findall(r'\b\w{3,}\b', q_lower))
    best_score, best = 0, None
    tech = {
        'list', 'tuple', 'dict', 'dictionary', 'set', 'function', 'class', 'object',
        'lambda', 'decorator', 'generator', 'iterator', 'exception', 'module',
        'package', 'inheritance', 'polymorphism', 'encapsulation', 'gil', 'pep8',
        'comprehension', 'thread', 'process', 'async'
    }
    for p in pairs:
        ql = p["question"].lower()
        al = p["answer"].lower()
        score = 20 if q_lower in ql else 0
        qw = set(re.findall(r'\b\w{3,}\b', ql))
        aw = set(re.findall(r'\b\w{3,}\b', al))
        score += len(q_words & qw) * 3 + len(q_words & aw)
        score += len((q_words & tech) & (qw & tech)) * 5
        if score > best_score:
            best_score, best = score, p
    if best and best_score >= 4:
        return {"found": True, "answer": best["answer"], "matched": best["question"]}
    return {"found": False, "answer": "", "matched": ""}

def _fallback_text():
    return """
1. What is Python?
Python is a high-level interpreted general-purpose programming language known for simplicity and readability.
2. What are Python key features?
Dynamic typing, interpreted execution, object-oriented design, large standard library, cross-platform support.
3. What is PEP 8?
PEP 8 is Python official style guide defining conventions for writing clean readable code.
4. What is the difference between a list and a tuple?
Lists are mutable ordered collections. Tuples are immutable ordered collections defined with parentheses.
5. What is a dictionary in Python?
A dictionary is an unordered key-value mapping. Keys must be unique and hashable.
6. What is a lambda function?
A lambda is an anonymous single-expression function: lambda x: x times 2.
7. What is a decorator?
A decorator wraps a function to extend its behavior without modifying its code.
8. What is the GIL?
The Global Interpreter Lock prevents multiple native threads from executing Python bytecode simultaneously.
9. What is a class in Python?
A class is a blueprint for creating objects defining attributes and methods shared by all instances.
10. What is inheritance?
Inheritance lets a child class acquire attributes and methods from a parent class.
"""


# ════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("# 🔍 Employee Help Portal")
    st.markdown("<p style='color:#6b7280'>Ask any Python-related question. If no answer found, raise a support ticket.</p>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 💬 Ask a Question")

    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("", placeholder="e.g. What is the difference between a list and a tuple?", label_visibility="collapsed")
    with col2:
        search = st.button("🔎 Search", use_container_width=True)

    if search and question.strip():
        with st.spinner("🔍 Searching knowledge base…"):
            result = answer_question(question.strip())
        if result["found"]:
            st.markdown("#### ✅ Answer Found")
            st.markdown(f"<small style='color:#7c3aed'>📌 Matched: <em>{result['matched']}</em></small>", unsafe_allow_html=True)
            st.markdown(f"<div class='answer-box'>{result['answer']}</div>", unsafe_allow_html=True)
            st.success("Answer from Python Knowledge Base.", icon="📚")
        else:
            st.markdown("#### ❌ No Answer Found")
            st.markdown("<div class='no-answer-box'>⚠️ No answer found. Please raise a support ticket below.</div>", unsafe_allow_html=True)
            st.session_state["prefill_query"] = question.strip()
            st.session_state["show_ticket"] = True
    elif search:
        st.warning("Please enter a question.")

    st.markdown("---")
    show = st.session_state.get("show_ticket", False)
    with st.expander("📝 Raise a Support Ticket", expanded=show):
        prefill = st.session_state.get("prefill_query", "")
        c1, c2 = st.columns(2)
        with c1:
            user_id = st.text_input("👤 Employee ID *", placeholder="e.g. EMP-1042")
            job_role = st.selectbox("💼 Job Role *", [
                "Select…", "Software Engineer", "Data Analyst", "QA Engineer",
                "DevOps Engineer", "Product Manager", "HR / Operations", "Other"
            ])
        with c2:
            priority = st.selectbox("🚨 Priority *", ["Medium", "High", "Low"])
        query_text = st.text_area("📋 Describe your problem *", value=prefill, placeholder="Describe the issue in detail…", height=120)
        if st.button("🚀 Submit Ticket", use_container_width=False):
            errors = []
            if not user_id.strip():
                errors.append("Employee ID required.")
            if job_role == "Select…":
                errors.append("Select your job role.")
            if not query_text.strip():
                errors.append("Problem description required.")
            for e in errors:
                st.error(e)
            if not errors:
                try:
                    t = db_create_ticket(user_id.strip(), job_role, query_text.strip(), priority)
                    st.success(f"✅ Ticket #{t.get('id', '–')} submitted! Our team will respond shortly.", icon="🎉")
                    st.session_state.pop("prefill_query", None)
                    st.session_state["show_ticket"] = False
                except Exception as ex:
                    st.error(f"Failed: {ex}")


def page_admin():
    admin_pwd = st.secrets.get("ADMIN_PASSWORD", ADMIN_PASSWORD)
    if not st.session_state.get("admin_logged_in"):
        st.markdown("# 🛡️ Admin Panel")
        st.markdown("---")
        col, _ = st.columns([1.5, 2.5])
        with col:
            pwd = st.text_input("Password", type="password")
            if st.button("Login →", use_container_width=True):
                if pwd == admin_pwd:
                    st.session_state["admin_logged_in"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown("# 🛡️ Admin Dashboard")
    with c2:
        if st.button("Logout"):
            st.session_state["admin_logged_in"] = False
            st.rerun()

    try:
        stats = db_stats()
        cols = st.columns(4)
        for col, val, label, icon in zip(
            cols,
            [stats["total"], stats["open"], stats["in_progress"], stats["resolved"]],
            ["Total", "Open", "In Progress", "Resolved"],
            ["📋", "🟡", "🔵", "🟢"]
        ):
            with col:
                st.markdown(
                    f"<div class='metric-card'><div style='font-size:28px'>{icon}</div>"
                    f"<div class='metric-number'>{val}</div>"
                    f"<div class='metric-label'>{label}</div></div>",
                    unsafe_allow_html=True
                )
    except Exception as e:
        st.error(f"Stats error: {e}")

    st.markdown("---")
    c1, c2, _ = st.columns([1.5, 1.5, 3])
    with c1:
        sf = st.selectbox("Status", ["All", "Open", "In Progress", "Resolved"])
    with c2:
        pf = st.selectbox("Priority", ["All", "High", "Medium", "Low"])

    try:
        tickets = db_get_tickets(sf if sf != "All" else None)
    except Exception as e:
        st.error(f"DB error: {e}")
        return

    if pf != "All":
        tickets = [t for t in tickets if t.get("priority") == pf]

    if not tickets:
        st.info("No tickets found.", icon="📭")
        return

    st.markdown(f"**{len(tickets)} ticket(s)**")
    for t in tickets:
        tid = t.get("id")
        status = t.get("status", "Open")
        priority = t.get("priority", "Medium")
        created = t.get("created_at", "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            created_fmt = dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            created_fmt = created

        badge = {"Open": "badge-open", "In Progress": "badge-inprogress", "Resolved": "badge-resolved"}.get(status, "badge-open")
        prio = {"High": "prio-high", "Medium": "prio-medium", "Low": "prio-low"}.get(priority, "prio-medium")

        with st.expander(f"🎫 #{tid} — {t.get('user_id', '?')} ({t.get('job_role', '?')}) | {status} | {priority} | {created_fmt}"):
            st.markdown(f"<span class='{badge}'>{status}</span>&nbsp;<span class='{prio}'>{priority}</span>", unsafe_allow_html=True)
            st.markdown(f"**Employee:** {t.get('user_id', '–')} &nbsp;|&nbsp; **Role:** {t.get('job_role', '–')} &nbsp;|&nbsp; **Submitted:** {created_fmt}")
            st.markdown("**Problem:**")
            st.markdown(f"<div class='answer-box'>{t.get('query', '–')}</div>", unsafe_allow_html=True)
            st.markdown("---")
            nc1, nc2 = st.columns(2)
            with nc1:
                new_status = st.selectbox(
                    "Update Status", ["Open", "In Progress", "Resolved"],
                    index=["Open", "In Progress", "Resolved"].index(status),
                    key=f"s_{tid}"
                )
            with nc2:
                note = st.text_area("Admin Note", value=t.get("admin_note") or "", key=f"n_{tid}", height=100)
            bc1, bc2, _ = st.columns([1, 1, 3])
            with bc1:
                if st.button("💾 Save", key=f"save_{tid}", use_container_width=True):
                    try:
                        db_update_ticket(tid, new_status, note)
                        st.success("Updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with bc2:
                if st.button("🗑️ Delete", key=f"del_{tid}", use_container_width=True):
                    try:
                        db_delete_ticket(tid)
                        st.warning("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))


def page_setup():
    st.markdown("# ⚙️ Setup & Configuration")

    with st.expander("📁 Secrets (Streamlit Cloud) — optional if using hardcoded values", expanded=True):
        st.code(
            '[secrets]\n'
            'SUPABASE_URL   = "https://jvulbphmksdebkkkhgvh.supabase.co"\n'
            'SUPABASE_KEY   = "eyJhbGci..."\n'
            'ADMIN_PASSWORD = "admin123"',
            language="toml"
        )

    with st.expander("🗄️ Create Supabase Table", expanded=True):
        st.code(SCHEMA_SQL, language="sql")

    with st.expander("📦 Install Dependencies"):
        st.code("pip install streamlit supabase PyPDF2 requests", language="bash")

    st.markdown("---")
    st.markdown("### 🔌 Connection Status")
    c1, c2 = st.columns(2)
    with c1:
        url_val = st.secrets.get("SUPABASE_URL", SUPABASE_URL)
        if url_val:
            st.success("✅ Supabase URL configured")
        else:
            st.error("❌ Supabase URL missing")
    with c2:
        key_val = st.secrets.get("SUPABASE_KEY", SUPABASE_KEY)
        if key_val:
            st.success("✅ Supabase Key configured")
        else:
            st.error("❌ Supabase Key missing")

    st.markdown("---")
    if st.button("🧪 Test Database"):
        try:
            db = get_db()
            if db is None:
                st.error("Not configured.")
            else:
                db.table("tickets").select("id").limit(1).execute()
                st.success("✅ Database connected!")
        except Exception as e:
            st.error(f"Failed: {e}")

    if st.button("📄 Test Knowledge Base"):
        pairs = load_qa_pairs()
        if pairs:
            st.success(f"✅ {len(pairs)} Q&A pairs loaded!")
            with st.expander("Preview"):
                for p in pairs[:5]:
                    st.markdown(f"**Q{p['num']}.** {p['question']}")
        else:
            st.error("No pairs loaded.")


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🤖 HelpDesk Pro")
    st.markdown("---")
    page = st.radio("Navigation", ["🔍 Employee Portal", "🛡️ Admin Panel", "⚙️ Setup / Config"])
    st.markdown("---")
    st.markdown("<small style='opacity:0.6'>Powered by Supabase</small>", unsafe_allow_html=True)

if page == "🔍 Employee Portal":
    page_employee()
elif page == "🛡️ Admin Panel":
    page_admin()
elif page == "⚙️ Setup / Config":
    page_setup()
