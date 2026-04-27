import streamlit as st
import re
import io
import requests
from datetime import datetime

st.set_page_config(page_title="HelpDesk Pro", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f0c29, #302b63, #24243e); }
section[data-testid="stSidebar"] * { color: white !important; }
.main { background: #f8f7ff; }
.answer-box { background: linear-gradient(135deg, #ede9fe, #ddd6fe); border-radius: 12px; padding: 20px; border-left: 4px solid #7c3aed; font-size: 15px; line-height: 1.7; color: #1e1b4b; }
.no-answer-box { background: #fff7ed; border-radius: 12px; padding: 16px 20px; border-left: 4px solid #f97316; color: #7c2d12; font-size: 14px; }
.badge-open { background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-inprogress { background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-resolved { background:#d1fae5;color:#065f46;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.prio-high { background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-medium { background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-low { background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
div.stButton > button { background: linear-gradient(135deg, #7c3aed, #5b21b6); color: white; border: none; border-radius: 10px; padding: 10px 24px; font-weight: 600; font-size: 14px; }
div.stButton > button:hover { background: linear-gradient(135deg, #6d28d9, #4c1d95); }
.metric-card { background:white;border-radius:14px;padding:20px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,0.06); }
.metric-number { font-family:'Syne',sans-serif;font-size:36px;font-weight:800;color:#7c3aed; }
.metric-label { font-size:13px;color:#6b7280;margin-top:4px; }
</style>
""", unsafe_allow_html=True)


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
    if not SUPABASE_OK: return None
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if url and key:
        return create_client(url, key)
    return None

def db_create_ticket(user_id, job_role, query, priority):
    db = get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    row = {"user_id": user_id, "job_role": job_role, "query": query, "priority": priority,
           "status": "Open", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()}
    result = db.table("tickets").insert(row).execute()
    return result.data[0] if result.data else {}

def db_get_tickets(status_filter=None):
    db = get_db()
    if db is None: return []
    q = db.table("tickets").select("*").order("created_at", desc=True)
    if status_filter and status_filter != "All": q = q.eq("status", status_filter)
    return q.execute().data or []

def db_update_ticket(tid, status, note):
    db = get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    db.table("tickets").update({"status": status, "admin_note": note, "updated_at": datetime.utcnow().isoformat()}).eq("id", tid).execute()

def db_delete_ticket(tid):
    db = get_db()
    if db: db.table("tickets").delete().eq("id", tid).execute()

def db_stats():
    tickets = db_get_tickets()
    return {"total": len(tickets), "open": sum(1 for t in tickets if t["status"]=="Open"),
            "in_progress": sum(1 for t in tickets if t["status"]=="In Progress"),
            "resolved": sum(1 for t in tickets if t["status"]=="Resolved")}


# ════════════════════════════════════════════════════════
#  Q&A ENGINE — extracts directly from PDF, no hardcoded Q&A
# ════════════════════════════════════════════════════════
_GDRIVE_FILE_ID = "1cUagShzCe0XsCbF5NEU9T62ICcU2I5AO"


@st.cache_resource(show_spinner="📄 Loading knowledge base from PDF…")
def load_qa_pairs():
    """Download PDF and extract Q&A pairs. Returns empty list if PDF unreachable."""
    text = _fetch_pdf()
    if not text:
        return []
    pairs = _parse_qa(text)
    return pairs


def _fetch_pdf():
    """Download PDF from Google Drive handling the virus-scan confirm page."""
    try:
        import PyPDF2
        session = requests.Session()

        # Attempt 1: direct download
        url1 = f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}"
        resp = session.get(url1, timeout=30)

        # Attempt 2: usercontent URL (more reliable for public files)
        if "text/html" in resp.headers.get("content-type", ""):
            url2 = f"https://drive.usercontent.google.com/download?id={_GDRIVE_FILE_ID}&export=download&confirm=t"
            resp = session.get(url2, timeout=30)

        # Attempt 3: extract confirm token from HTML and retry
        if "text/html" in resp.headers.get("content-type", ""):
            token_match = re.search(r'confirm=([0-9A-Za-z_\-]+)', resp.text)
            if token_match:
                url3 = f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}&confirm={token_match.group(1)}"
                resp = session.get(url3, timeout=30)

        resp.raise_for_status()

        if "text/html" in resp.headers.get("content-type", ""):
            return None  # Could not get the PDF

        reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    except Exception:
        return None


def _parse_qa(text):
    """Parse numbered Q&A pairs from raw PDF text."""
    pairs = []
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Split on numbered items like "1.", "2.", "10."
    parts = re.split(r'\n(\d{1,3})[.)]\s+', text)

    if len(parts) > 3:
        i = 1
        while i < len(parts) - 1:
            num = parts[i].strip()
            content = parts[i+1].strip() if i+1 < len(parts) else ""
            i += 2
            if not content or len(content) < 10:
                continue

            lines = content.split('\n')
            q_lines, a_lines, found_q_end = [], [], False

            for line in lines:
                line = line.strip()
                if not line:
                    if q_lines: found_q_end = True
                    continue
                if not found_q_end:
                    q_lines.append(line)
                    if line.endswith('?'): found_q_end = True
                else:
                    a_lines.append(line)

            # If no blank-line separator, split at '?'
            if not a_lines and q_lines:
                full = " ".join(q_lines)
                idx = full.find('?')
                if idx != -1:
                    q_lines = [full[:idx+1]]
                    a_lines = [full[idx+1:].strip()]

            q = re.sub(r'\s+', ' ', " ".join(q_lines)).strip()
            a = re.sub(r'\s+', ' ', " ".join(a_lines)).strip()

            if len(q) >= 8 and len(a) >= 5:
                pairs.append({"num": num, "question": q, "answer": a})

    # Fallback: Q: / A: format
    if len(pairs) < 5:
        pairs = []
        for block in re.split(r'\n(?=Q\d*[.:)]?\s)', text):
            qm = re.search(r'Q\d*[.:)]?\s*(.+?\?)', block, re.DOTALL)
            am = re.search(r'A[.:)]?\s*(.+?)(?=\n\n|$)', block, re.DOTALL)
            if qm and am:
                q = re.sub(r'\s+', ' ', qm.group(1)).strip()
                a = re.sub(r'\s+', ' ', am.group(1)).strip()
                if len(q) >= 8 and len(a) >= 5:
                    pairs.append({"num": str(len(pairs)+1), "question": q, "answer": a})

    return pairs


def answer_question(query):
    """Score Q&A pairs from the PDF and return the best match."""
    pairs = load_qa_pairs()

    # PDF could not be loaded at all
    if pairs is None or len(pairs) == 0:
        return {"found": False, "answer": "", "matched": "", "pdf_error": True}

    stop = {'what','which','when','where','how','why','does','did','can','the',
            'and','for','are','was','were','has','have','had','its','this','that',
            'with','from','they','them','their','there','been','being','would','you',
            'about','tell','explain','mean','means','define','difference','between',
            'python','give','please','write'}

    tech_terms = {
        'list','tuple','dict','dictionary','set','function','class','object',
        'lambda','decorator','generator','iterator','exception','module','package',
        'inheritance','polymorphism','encapsulation','abstraction','gil','pep8','pep',
        'comprehension','thread','process','async','await','coroutine','closure',
        'mutable','immutable','scope','namespace','metaclass','dataclass','typing',
        'args','kwargs','overloading','overriding','string','integer','float',
        'boolean','none','bytes','map','filter','reduce','zip','enumerate',
        'import','pip','virtualenv','unittest','pytest','assert','debug','logging',
        'oop','solid','algorithm','recursion','binary','tree','graph',
        'stack','queue','sort','search','variable','operator','loop',
        'condition','statement','expression','syntax','error','index',
    }

    query_clean = query.lower().strip()
    query_words = set(re.findall(r'\b\w{3,}\b', query_clean)) - stop
    best_score, best_match = 0, None

    for p in pairs:
        ql = p["question"].lower()
        al = p["answer"].lower()
        qw = set(re.findall(r'\b\w{3,}\b', ql)) - stop
        aw = set(re.findall(r'\b\w{3,}\b', al)) - stop
        score = 0

        if query_clean in ql: score += 50
        score += len(query_words & qw) * 4
        score += len(query_words & aw) * 1
        score += len((query_words & tech_terms) & (qw & tech_terms)) * 6

        # Partial word match (e.g. "inherit" → "inheritance")
        for qword in query_words:
            for pword in qw:
                if len(qword) >= 4 and len(pword) >= 4 and (qword in pword or pword in qword):
                    score += 2

        if len(p["answer"]) < 20: score -= 3

        if score > best_score:
            best_score, best_match = score, p

    threshold = max(4, len(query_words) * 2)

    if best_match and best_score >= threshold:
        return {"found": True, "answer": best_match["answer"], "matched": best_match["question"], "pdf_error": False}

    return {"found": False, "answer": "", "matched": "", "pdf_error": False}


# ════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("# 🔍 Employee Help Portal")
    st.markdown("<p style='color:#6b7280'>Ask any Python-related question. If no answer is found, raise a support ticket.</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Show PDF load status
    pairs = load_qa_pairs()
    if len(pairs) == 0:
        st.error("⚠️ Knowledge base PDF could not be loaded. Please contact admin or raise a ticket directly.")
    else:
        st.info(f"📚 Knowledge base loaded — {len(pairs)} Q&A pairs from PDF.", icon="✅")

    st.markdown("### 💬 Ask a Question")
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("", placeholder="e.g. What is the difference between a list and a tuple?", label_visibility="collapsed")
    with col2:
        search = st.button("🔎 Search", use_container_width=True)

    if search and question.strip():
        with st.spinner("🔍 Searching PDF knowledge base…"):
            result = answer_question(question.strip())

        if result.get("pdf_error"):
            st.error("❌ PDF knowledge base is unavailable. Please raise a ticket and our team will assist you.")
            st.session_state["prefill_query"] = question.strip()
            st.session_state["show_ticket"] = True

        elif result["found"]:
            st.markdown("#### ✅ Answer Found")
            st.markdown(f"<small style='color:#7c3aed'>📌 Matched: <em>{result['matched']}</em></small>", unsafe_allow_html=True)
            st.markdown(f"<div class='answer-box'>{result['answer']}</div>", unsafe_allow_html=True)
            st.success("Answer extracted from the PDF knowledge base.", icon="📚")

        else:
            st.markdown("#### ❌ No Answer Found in Knowledge Base")
            st.markdown("<div class='no-answer-box'>⚠️ This question is not covered in our knowledge base. Please raise a support ticket and our team will help you.</div>", unsafe_allow_html=True)
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
            job_role = st.selectbox("💼 Job Role *", ["Select…","Software Engineer","Data Analyst","QA Engineer","DevOps Engineer","Product Manager","HR / Operations","Other"])
        with c2:
            priority = st.selectbox("🚨 Priority *", ["Medium","High","Low"])
        query_text = st.text_area("📋 Describe your problem *", value=prefill, placeholder="Describe the issue in detail…", height=120)
        if st.button("🚀 Submit Ticket"):
            errors = []
            if not user_id.strip(): errors.append("Employee ID required.")
            if job_role == "Select…": errors.append("Select your job role.")
            if not query_text.strip(): errors.append("Problem description required.")
            for e in errors: st.error(e)
            if not errors:
                try:
                    t = db_create_ticket(user_id.strip(), job_role, query_text.strip(), priority)
                    st.success(f"✅ Ticket #{t.get('id','–')} submitted! Our team will respond shortly.", icon="🎉")
                    st.session_state.pop("prefill_query", None)
                    st.session_state["show_ticket"] = False
                except Exception as ex:
                    st.error(f"Failed: {ex}")


def page_admin():
    ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")
    if not st.session_state.get("admin_logged_in"):
        st.markdown("# 🛡️ Admin Panel")
        st.markdown("---")
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

    c1, c2 = st.columns([5,1])
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
    c1, c2, _ = st.columns([1.5,1.5,3])
    with c1: sf = st.selectbox("Status", ["All","Open","In Progress","Resolved"])
    with c2: pf = st.selectbox("Priority", ["All","High","Medium","Low"])

    try:
        tickets = db_get_tickets(sf if sf != "All" else None)
    except Exception as e:
        st.error(f"DB error: {e}"); return

    if pf != "All":
        tickets = [t for t in tickets if t.get("priority") == pf]

    if not tickets:
        st.info("No tickets found.", icon="📭"); return

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
        prio  = {"High":"prio-high","Medium":"prio-medium","Low":"prio-low"}.get(priority,"prio-medium")
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
                note = st.text_area("Admin Note", value=t.get("admin_note") or "", key=f"n_{tid}", height=100)
            bc1, bc2, _ = st.columns([1,1,3])
            with bc1:
                if st.button("💾 Save", key=f"save_{tid}", use_container_width=True):
                    try: db_update_ticket(tid, new_status, note); st.success("Updated!"); st.rerun()
                    except Exception as e: st.error(str(e))
            with bc2:
                if st.button("🗑️ Delete", key=f"del_{tid}", use_container_width=True):
                    try: db_delete_ticket(tid); st.warning("Deleted."); st.rerun()
                    except Exception as e: st.error(str(e))


def page_setup():
    st.markdown("# ⚙️ Setup & Configuration")
    with st.expander("📁 Streamlit Secrets", expanded=True):
        st.code('[secrets]\nSUPABASE_URL   = "https://xxxx.supabase.co"\nSUPABASE_KEY   = "eyJ..."\nADMIN_PASSWORD = "your_password"', language="toml")
    with st.expander("🗄️ Create Supabase Table", expanded=True):
        st.code(SCHEMA_SQL, language="sql")
    with st.expander("📦 Install Dependencies"):
        st.code("pip install streamlit supabase PyPDF2 requests", language="bash")
    st.markdown("---")
    st.markdown("### 🔌 Connection Status")
    c1, c2 = st.columns(2)
    with c1:
        if st.secrets.get("SUPABASE_URL",""): st.success("✅ Supabase URL configured")
        else: st.error("❌ Supabase URL missing")
    with c2:
        if st.secrets.get("SUPABASE_KEY",""): st.success("✅ Supabase Key configured")
        else: st.error("❌ Supabase Key missing")
    st.markdown("---")
    if st.button("🧪 Test Database"):
        try:
            db = get_db()
            if db is None: st.error("Not configured.")
            else:
                db.table("tickets").select("id").limit(1).execute()
                st.success("✅ Database connected!")
        except Exception as e: st.error(f"Failed: {e}")
    if st.button("📄 Test Knowledge Base (PDF)"):
        pairs = load_qa_pairs()
        if pairs:
            st.success(f"✅ {len(pairs)} Q&A pairs extracted from PDF!")
            with st.expander("Preview first 5"):
                for p in pairs[:5]:
                    st.markdown(f"**Q{p['num']}.** {p['question']}")
                    st.markdown(f"*A: {p['answer'][:150]}…*")
                    st.markdown("---")
        else:
            st.error("❌ Could not extract Q&A from PDF. Check that your Google Drive file is publicly shared.")


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
