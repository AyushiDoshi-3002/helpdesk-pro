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
.learned-box { background: linear-gradient(135deg, #d1fae5, #a7f3d0); border-radius: 12px; padding: 20px; border-left: 4px solid #059669; font-size: 15px; line-height: 1.7; color: #064e3b; }
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
-- Run this in Supabase SQL Editor

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

-- Disable RLS so inserts/updates work without auth policies
ALTER TABLE tickets DISABLE ROW LEVEL SECURITY;
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
    row = {"user_id": user_id, "job_role": job_role, "query": query, "priority": priority, "status": "Open"}
    try:
        result = db.table("tickets").insert(row).execute()
        if result.data:
            return result.data[0]
        raise Exception("No data returned from insert")
    except Exception as e:
        raise Exception(f"Insert failed: {e}")

def db_get_tickets(status_filter=None):
    db = get_db()
    if db is None: return []
    try:
        q = db.table("tickets").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All": q = q.eq("status", status_filter)
        return q.execute().data or []
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return []

def db_update_ticket(tid, status, note):
    db = get_db()
    if db is None: raise ConnectionError("Supabase not configured.")
    try:
        db.table("tickets").update({"status": status, "admin_note": note}).eq("id", tid).execute()
    except Exception as e:
        raise Exception(f"Update failed: {e}")

def db_delete_ticket(tid):
    db = get_db()
    if db:
        try:
            db.table("tickets").delete().eq("id", tid).execute()
        except Exception as e:
            raise Exception(f"Delete failed: {e}")

def db_stats():
    tickets = db_get_tickets()
    return {
        "total": len(tickets),
        "open": sum(1 for t in tickets if t["status"] == "Open"),
        "in_progress": sum(1 for t in tickets if t["status"] == "In Progress"),
        "resolved": sum(1 for t in tickets if t["status"] == "Resolved")
    }


# ════════════════════════════════════════════════════════
#  LEARNED ANSWERS LOOKUP
# ════════════════════════════════════════════════════════

_STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "of", "in", "on", "at",
    "to", "for", "and", "or", "how", "why", "when", "where", "who",
    "does", "do", "can", "could", "would", "should", "explain",
    "tell", "me", "about", "difference", "between", "use", "using"
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
    intersection = q_words & s_words
    union = q_words | s_words
    return len(intersection) / len(union)

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
            if not note or not q: continue
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
            if not sol or not q: continue
            score = _keyword_score(query, q)
            if score > best_score:
                best_score, best_solution, best_matched = score, sol, q
    except Exception:
        pass
    if best_solution and best_score >= _LEARNED_THRESHOLD:
        return {"solution": best_solution, "matched_query": best_matched, "score": best_score}
    return None


# ════════════════════════════════════════════════════════
#  PDF DOWNLOAD
# ════════════════════════════════════════════════════════
_GDRIVE_FILE_ID = "1cUagShzCe0XsCbF5NEU9T62ICcU2I5AO"

@st.cache_resource(show_spinner="📄 Downloading PDF…")
def get_pdf_bytes():
    try:
        session = requests.Session()
        url1 = f"https://drive.usercontent.google.com/download?id={_GDRIVE_FILE_ID}&export=download&confirm=t&uuid=1"
        resp = session.get(url1, timeout=30)
        if "text/html" in resp.headers.get("content-type", ""):
            url2 = f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}"
            resp = session.get(url2, timeout=30)
            token_match = re.search(r'confirm=([0-9A-Za-z_\-]+)', resp.text)
            if token_match:
                resp = session.get(
                    f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}&confirm={token_match.group(1)}",
                    timeout=30
                )
        resp.raise_for_status()
        if "text/html" in resp.headers.get("content-type", ""):
            return None
        return resp.content
    except Exception:
        return None


# ════════════════════════════════════════════════════════
#  Q&A EXTRACTION FROM PDF
# ════════════════════════════════════════════════════════
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
@st.cache_resource(show_spinner="🧠 Loading semantic search model…")
def load_model_and_embeddings():
    try:
        from sentence_transformers import SentenceTransformer, util
        pairs = load_qa_pairs()
        if not pairs:
            return None, None, None, None
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode([q for q, a in pairs], convert_to_tensor=True)
        return model, embeddings, pairs, util
    except Exception as e:
        st.warning(f"Semantic model error: {e}")
        return None, None, None, None


# ════════════════════════════════════════════════════════
#  ANSWER LOOKUP
# ════════════════════════════════════════════════════════
def answer_question(query: str) -> dict:

    # ── Step 1: PDF semantic search (PRIMARY) ────────────────────────────────
    model, embeddings, pairs, util = load_model_and_embeddings()

    if model is not None and embeddings is not None and pairs is not None and util is not None:
        try:
            query_embedding = model.encode(query.lower(), convert_to_tensor=True)
            scores = util.cos_sim(query_embedding, embeddings)[0]
            best_idx = int(scores.argmax())
            best_score = float(scores[best_idx])
            if best_score >= 0.4:
                question, answer = pairs[best_idx]
                return {
                    "found": True,
                    "answer": answer.strip(),
                    "matched": question.strip(),
                    "score": best_score,
                    "pdf_error": False,
                    "source": "pdf"
                }
        except Exception:
            pass

    # ── Step 2: Supabase learned answers (FALLBACK) ──────────────────────────
    learned = check_learned_answers(query)
    if learned:
        return {
            "found": True,
            "answer": learned["solution"],
            "matched": learned["matched_query"],
            "score": learned["score"],
            "pdf_error": False,
            "source": "learned"
        }

    # ── Step 3: Nothing found ────────────────────────────────────────────────
    pdf_unavailable = (model is None or embeddings is None)
    return {
        "found": False,
        "answer": "",
        "matched": "",
        "score": 0,
        "pdf_error": pdf_unavailable,
        "source": "none"
    }


# ════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("# 🔍 Employee Help Portal")
    st.markdown("<p style='color:#6b7280'>Ask any question. If no answer is found in the knowledge base, raise a support ticket.</p>", unsafe_allow_html=True)
    st.markdown("---")

    pairs = load_qa_pairs()
    if len(pairs) == 0:
        st.error("⚠️ Knowledge base could not be loaded from PDF. Please contact admin or raise a ticket directly.")
    else:
        st.success(f"📚 Knowledge base ready — {len(pairs)} Q&A pairs extracted from PDF.", icon="✅")

    st.markdown("### 💬 Ask a Question")
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("", placeholder="e.g. What is the difference between a list and a tuple?", label_visibility="collapsed")
    with col2:
        search = st.button("🔎 Search", use_container_width=True)

    if search and question.strip():
        with st.spinner("🧠 Searching knowledge base…"):
            result = answer_question(question.strip())

        if result.get("pdf_error"):
            st.error("❌ Knowledge base unavailable. Please raise a ticket.")
            st.session_state["show_ticket"] = True
            st.session_state["ticket_query"] = question.strip()

        elif result["found"]:
            source = result.get("source", "pdf")

            if source == "learned":
                st.markdown("#### ✅ Answer Found")
                st.markdown(
                    "<small style='color:#059669'>💡 <strong>Source: Previously resolved support ticket</strong></small>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<small style='color:#6b7280'>📌 Similar question: <em>{result['matched'][:160]}</em> "
                    f"(similarity: {result['score']:.0%})</small>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"<div class='learned-box'>{result['answer']}</div>", unsafe_allow_html=True)
            else:
                st.markdown("#### ✅ Answer Found")
                st.markdown(
                    "<small style='color:#7c3aed'>📚 <strong>Source: PDF Knowledge Base</strong></small>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<small style='color:#6b7280'>📌 Matched: <em>{result['matched'][:120]}</em> "
                    f"(score: {result['score']:.2f})</small>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"<div class='answer-box'>{result['answer']}</div>", unsafe_allow_html=True)

            st.markdown("---")
            col_a, col_b, _ = st.columns([1, 1, 4])
            with col_a:
                if st.button("👍 Helpful"):
                    st.success("Great! Glad it helped.")
            with col_b:
                if st.button("👎 Not helpful"):
                    st.session_state["show_ticket"] = True
                    st.session_state["ticket_query"] = question.strip()
                    st.warning("Sorry! Please raise a ticket below.")

        else:
            st.markdown("#### ❌ No Answer Found")
            st.markdown(
                "<div class='no-answer-box'>⚠️ No answer found in the knowledge base. "
                "Please fill in the ticket details below and our team will help you.</div>",
                unsafe_allow_html=True,
            )
            st.session_state["show_ticket"] = True
            st.session_state["ticket_query"] = question.strip()

    elif search:
        st.warning("Please enter a question.")

    st.markdown("---")

    if st.session_state.get("show_ticket", False):
        st.markdown("### 📝 Support Ticket")
        c1, c2 = st.columns(2)
        with c1:
            user_id = st.text_input("👤 Employee ID *", placeholder="e.g. EMP-1042")
            job_role = st.selectbox("💼 Job Role *", ["Select…", "Software Engineer", "Data Analyst", "QA Engineer", "DevOps Engineer", "Product Manager", "HR / Operations", "Other"])
        with c2:
            priority = st.selectbox("🚨 Priority *", ["Medium", "High", "Low"])

        original_question = st.session_state.get("ticket_query", "")
        if original_question:
            st.markdown(f"<small style='color:#7c3aed'>🔍 Your search question: <strong>{original_question}</strong></small>", unsafe_allow_html=True)
        query_text = st.text_area("📋 Describe your problem in detail *", value="", placeholder="Add more details about your issue…", height=120)

        submit_clicked = False
        cancel_clicked = False
        col_sub, col_cancel, _ = st.columns([1, 1, 4])
        with col_sub:
            if st.button("🚀 Submit Ticket", use_container_width=True):
                submit_clicked = True
        with col_cancel:
            if st.button("✖ Cancel", use_container_width=True):
                cancel_clicked = True

        if submit_clicked:
            errors = []
            if not user_id.strip(): errors.append("Employee ID required.")
            if job_role == "Select…": errors.append("Select your job role.")
            if not original_question and not query_text.strip(): errors.append("Problem description required.")
            for e in errors: st.error(e)
            if not errors:
                final_query = original_question if original_question else query_text.strip()
                try:
                    t = db_create_ticket(user_id.strip(), job_role, final_query, priority)
                    st.success(f"✅ Ticket #{t.get('id', '–')} submitted! Our team will respond shortly.", icon="🎉")
                    st.session_state["show_ticket"] = False
                except Exception as ex:
                    st.error(f"Failed: {ex}")

        if cancel_clicked:
            st.session_state["show_ticket"] = False
            st.rerun()


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

    c1, c2 = st.columns([5, 1])
    with c1: st.markdown("# 🛡️ Admin Dashboard")
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
    with c1: sf = st.selectbox("Status", ["All", "Open", "In Progress", "Resolved"])
    with c2: pf = st.selectbox("Priority", ["All", "High", "Medium", "Low"])

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
                note = st.text_area(
                    "Admin Note / Solution",
                    value=t.get("admin_note") or "",
                    key=f"n_{tid}",
                    height=100,
                    placeholder="Write solution here — it will be saved to the knowledge base for future queries."
                )

            save_clicked = False
            delete_clicked = False
            bc1, bc2, _, _ = st.columns([1, 1, 1.5, 1])
            with bc1:
                if st.button("💾 Save", key=f"save_{tid}", use_container_width=True):
                    save_clicked = True
            with bc2:
                if st.button("🗑️ Delete", key=f"del_{tid}", use_container_width=True):
                    delete_clicked = True

            if save_clicked:
                try:
                    db_update_ticket(tid, new_status, note)
                    if new_status == "Resolved" and note.strip():
                        db = get_db()
                        if db:
                            existing = db.table("resolved_issues").select("id").eq("query", t.get("query", "")).execute()
                            if not existing.data:
                                db.table("resolved_issues").insert({
                                    "query": t.get("query", ""),
                                    "solution": note.strip()
                                }).execute()
                                st.success("✅ Updated & solution saved to knowledge base!")
                            else:
                                db.table("resolved_issues").update({"solution": note.strip()}).eq("query", t.get("query", "")).execute()
                                st.success("✅ Updated & existing knowledge base entry refreshed!")
                    else:
                        st.success("Updated!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if delete_clicked:
                try:
                    db_delete_ticket(tid)
                    st.warning("Deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def page_setup():
    st.markdown("# ⚙️ Setup & Configuration")
    with st.expander("📁 Streamlit Secrets", expanded=True):
        st.code('[secrets]\nSUPABASE_URL   = "https://xxxx.supabase.co"\nSUPABASE_KEY   = "eyJ..."\nADMIN_PASSWORD = "your_password"', language="toml")
    with st.expander("🗄️ Create Supabase Tables", expanded=True):
        st.code(SCHEMA_SQL, language="sql")
    with st.expander("📦 Install Dependencies"):
        st.code("pip install streamlit supabase pdfplumber sentence-transformers requests torch", language="bash")

    st.markdown("---")
    st.markdown("### 🔌 Connection Status")
    c1, c2 = st.columns(2)
    with c1:
        if st.secrets.get("SUPABASE_URL", ""): st.success("✅ Supabase URL configured")
        else: st.error("❌ Supabase URL missing")
    with c2:
        if st.secrets.get("SUPABASE_KEY", ""): st.success("✅ Supabase Key configured")
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

    if st.button("📄 Test PDF + Q&A Extraction"):
        pdf_bytes = get_pdf_bytes()
        if not pdf_bytes:
            st.error("❌ Could not download PDF.")
        else:
            st.success(f"✅ PDF downloaded ({len(pdf_bytes) // 1024} KB)")
            pairs = load_qa_pairs()
            if pairs:
                st.success(f"✅ {len(pairs)} Q&A pairs extracted!")
                with st.expander("Preview first 5 pairs"):
                    for q, a in pairs[:5]:
                        st.markdown(f"**Q:** {q[:200]}")
                        st.markdown(f"**A:** {a[:200]}")
                        st.markdown("---")
            else:
                st.error("❌ No Q&A pairs found.")

    st.markdown("---")
    st.markdown("### 🧠 Learned Answers (from resolved tickets)")
    if st.button("📋 View All Learned Answers"):
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
                            st.markdown(f"<small style='color:#6b7280'>Saved: {row.get('created_at', '')[:10]}</small>", unsafe_allow_html=True)
                else:
                    st.info("No learned answers yet. Resolve tickets with a note to build the knowledge base.")
            except Exception as e:
                st.error(f"Error: {e}")


# ════════════════════════════════════════════════════════
#  MAIN — SIDEBAR + ROUTING
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🤖 HelpDesk Pro")
    st.markdown("---")

    page = st.radio("Navigation", [
        "🔍 Employee Portal",
        "🛡️ Admin Panel",
        "📋 Approval Pipeline",
        "⚙️ Setup / Config",
    ])

    st.markdown("---")

    if not PIPELINE_AVAILABLE:
        st.warning("⚠️ approval_pipeline.py not found.", icon="⚠️")

    st.markdown("<small style='opacity:0.6'>Powered by Supabase + pdfplumber</small>", unsafe_allow_html=True)


if page == "🔍 Employee Portal":
    page_employee()

elif page == "🛡️ Admin Panel":
    page_admin()

elif page == "📋 Approval Pipeline":
    if PIPELINE_AVAILABLE:
        page_approval_pipeline()
    else:
        st.error("❌ `approval_pipeline.py` is missing from your project folder.")
        st.info("Make sure `approval_pipeline.py` is in the same directory as `app.py` and restart the app.")

elif page == "⚙️ Setup / Config":
    page_setup()
