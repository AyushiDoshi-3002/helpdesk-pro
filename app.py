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
    """Convert a UTC ISO string → formatted IST display string."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return dt_str

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
.kb-box { background: linear-gradient(135deg, #e0f2fe, #bae6fd); border-radius: 12px; padding: 20px; border-left: 4px solid #0284c7; font-size: 15px; line-height: 1.7; color: #0c4a6e; }
.similar-ticket-card { background: #f5f3ff; border-radius: 10px; padding: 14px 16px; border-left: 3px solid #7c3aed; margin-bottom: 10px; }
.badge-open { background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-inprogress { background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-resolved { background:#d1fae5;color:#065f46;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-overdue { background:#fee2e2;color:#991b1b;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.prio-high { background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-medium { background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-low { background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.kb-entry { background:white;border-radius:12px;padding:16px;margin-bottom:10px;border-left:4px solid #0284c7;box-shadow:0 2px 8px rgba(0,0,0,0.05); }
.kb-category { background:#e0f2fe;color:#0369a1;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
div.stButton > button { background: linear-gradient(135deg, #7c3aed, #5b21b6); color: white; border: none; border-radius: 10px; padding: 10px 24px; font-weight: 600; font-size: 14px; }
div.stButton > button:hover { background: linear-gradient(135deg, #6d28d9, #4c1d95); }
.metric-card { background:white;border-radius:14px;padding:20px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,0.06); }
.metric-number { font-family:'Syne',sans-serif;font-size:36px;font-weight:800;color:#7c3aed; }
.metric-label { font-size:13px;color:#6b7280;margin-top:4px; }
.gap-card { background:white;border-radius:12px;padding:16px;margin-bottom:10px;border-left:4px solid #f97316;box-shadow:0 2px 8px rgba(0,0,0,0.05); }
.gap-count { font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#f97316; }
.timeline-dot { width:12px;height:12px;border-radius:50%;display:inline-block;margin-right:8px; }
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

-- ✅ NEW: Manual Knowledge Base table
CREATE TABLE IF NOT EXISTS knowledge_base (
    id         BIGSERIAL PRIMARY KEY,
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    category   TEXT DEFAULT 'General',
    created_by TEXT DEFAULT 'admin',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE tickets DISABLE ROW LEVEL SECURITY;
ALTER TABLE resolved_issues DISABLE ROW LEVEL SECURITY;
ALTER TABLE failed_queries DISABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base DISABLE ROW LEVEL SECURITY;
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
            return result.data[0]
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
    except Exception as e:
        raise Exception(f"Update failed: {e}")

def db_delete_ticket(tid):
    db = get_db()
    if db:
        try:
            db.table("tickets").delete().eq("id", tid).execute()
        except Exception as e:
            raise Exception(f"Delete failed: {e}")

def db_log_failed_query(query: str):
    db = get_db()
    if db:
        try:
            db.table("failed_queries").insert({"query": query}).execute()
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


# ════════════════════════════════════════════════════════
#  KNOWLEDGE BASE (Manual) — CRUD
# ════════════════════════════════════════════════════════
def db_kb_get_all():
    db = get_db()
    if db is None:
        return []
    try:
        return db.table("knowledge_base").select("*").order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"KB fetch error: {e}")
        return []

def db_kb_add(question: str, answer: str, category: str = "General", created_by: str = "admin"):
    db = get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    try:
        result = db.table("knowledge_base").insert({
            "question": question, "answer": answer,
            "category": category, "created_by": created_by
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        raise Exception(f"KB insert failed: {e}")

def db_kb_update(kid: int, question: str, answer: str, category: str):
    db = get_db()
    if db is None:
        raise ConnectionError("Supabase not configured.")
    try:
        db.table("knowledge_base").update({
            "question": question, "answer": answer,
            "category": category, "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", kid).execute()
    except Exception as e:
        raise Exception(f"KB update failed: {e}")

def db_kb_delete(kid: int):
    db = get_db()
    if db:
        try:
            db.table("knowledge_base").delete().eq("id", kid).execute()
        except Exception as e:
            raise Exception(f"KB delete failed: {e}")

def db_kb_search(query: str):
    """Return best matching KB entry using keyword scoring."""
    entries = db_kb_get_all()
    if not entries:
        return None
    best_score, best_entry = 0.0, None
    for entry in entries:
        score = _keyword_score(query, entry.get("question", ""))
        if score > best_score:
            best_score, best_entry = score, entry
    if best_entry and best_score >= _LEARNED_THRESHOLD:
        return {"entry": best_entry, "score": best_score}
    return None


# ════════════════════════════════════════════════════════
#  AUTO-SAVE NOTE TO KNOWLEDGE BASE
# ════════════════════════════════════════════════════════
def auto_save_note_to_kb(ticket_query: str, note: str):
    """
    ✅ NEW: Auto-saves admin note to resolved_issues whenever note is non-empty.
    Called on every Save, regardless of ticket status.
    """
    db = get_db()
    if db is None or not note.strip() or not ticket_query.strip():
        return False
    try:
        existing = db.table("resolved_issues").select("id").eq("query", ticket_query).execute()
        if not existing.data:
            db.table("resolved_issues").insert({"query": ticket_query, "solution": note.strip()}).execute()
        else:
            db.table("resolved_issues").update({"solution": note.strip()}).eq("query", ticket_query).execute()
        return True
    except Exception:
        return False


# ════════════════════════════════════════════════════════
#  SIMILAR TICKETS SUGGESTION (for Admin)
# ════════════════════════════════════════════════════════
def find_similar_resolved_tickets(query: str, top_n: int = 3) -> list:
    """
    ✅ NEW: Find top N similar resolved tickets with notes.
    Used in admin panel to suggest solutions while typing.
    """
    db = get_db()
    if db is None:
        return []
    results = []
    try:
        resp = db.table("resolved_issues").select("query, solution").execute()
        for row in (resp.data or []):
            q = (row.get("query") or "").strip()
            sol = (row.get("solution") or "").strip()
            if not q or not sol:
                continue
            score = _keyword_score(query, q)
            if score > 0.3:
                results.append({"query": q, "solution": sol, "score": score})
    except Exception:
        pass
    try:
        resp2 = db.table("tickets").select("query, admin_note").not_.is_("admin_note", "null").execute()
        for row in (resp2.data or []):
            q = (row.get("query") or "").strip()
            note = (row.get("admin_note") or "").strip()
            if not q or not note:
                continue
            score = _keyword_score(query, q)
            if score > 0.3:
                results.append({"query": q, "solution": note, "score": score})
    except Exception:
        pass
    # Deduplicate by solution text, keep highest score
    seen = {}
    for r in results:
        key = r["solution"][:80]
        if key not in seen or r["score"] > seen[key]["score"]:
            seen[key] = r
    sorted_results = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return sorted_results[:top_n]


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
    return len(q_words & s_words) / len(q_words | s_words)

_LEARNED_THRESHOLD = 0.55

def check_learned_answers(query: str):
    db = get_db()
    if db is None:
        return None
    best_score, best_solution, best_matched = 0.0, None, None

    # ✅ NEW: Check manual knowledge_base table FIRST
    kb_result = db_kb_search(query)
    if kb_result:
        entry = kb_result["entry"]
        return {
            "solution": entry["answer"],
            "matched_query": entry["question"],
            "score": kb_result["score"],
            "source": "knowledge_base",
            "category": entry.get("category", "General")
        }

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


# ════════════════════════════════════════════════════════
#  ANSWER LOOKUP  (KB → PDF → Learned)
# ════════════════════════════════════════════════════════
def answer_question(query: str) -> dict:
    # ✅ Step 1: Check manual Knowledge Base FIRST
    kb_result = db_kb_search(query)
    if kb_result:
        entry = kb_result["entry"]
        return {
            "found": True,
            "answer": entry["answer"].strip(),
            "matched": entry["question"].strip(),
            "score": kb_result["score"],
            "match_src": "knowledge_base",
            "pdf_error": False,
            "source": "knowledge_base",
            "category": entry.get("category", "General")
        }

    # Step 2: Check PDF via semantic model
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

    # Step 3: Check learned answers (resolved tickets + admin notes)
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


# ════════════════════════════════════════════════════════
#  CSV EXPORT HELPER
# ════════════════════════════════════════════════════════
def tickets_to_csv(tickets: list) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "user_id", "job_role", "query", "priority", "status", "admin_note", "created_at"])
    writer.writeheader()
    for t in tickets:
        writer.writerow({k: t.get(k, "") for k in writer.fieldnames})
    return output.getvalue().encode("utf-8")


# ════════════════════════════════════════════════════════
#  PAGE: EMPLOYEE PORTAL
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("# 🔍 Employee Help Portal")
    st.markdown("<p style='color:#6b7280'>Ask any question. If no answer is found in the knowledge base, raise a support ticket.</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Show KB stats alongside PDF stats
    kb_entries = db_kb_get_all()
    pairs = load_qa_pairs()

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if len(pairs) == 0:
            st.error("⚠️ PDF knowledge base could not be loaded.")
        else:
            st.success(f"📚 PDF Knowledge Base: {len(pairs)} Q&A pairs", icon="✅")
    with col_s2:
        if kb_entries:
            st.info(f"📝 Manual Knowledge Base: {len(kb_entries)} entries added by admin", icon="✅")
        else:
            st.info("📝 Manual Knowledge Base: empty (admins can add entries)", icon="ℹ️")

    st.markdown("### 💬 Ask a Question")
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("", placeholder="e.g. What is the difference between a list and a tuple?", label_visibility="collapsed")
    with col2:
        search = st.button("🔎 Search", use_container_width=True)

    if search and question.strip():
        with st.spinner("🧠 Searching knowledge base…"):
            result = answer_question(question.strip())

        if result.get("pdf_error") and not result["found"]:
            st.error("❌ Knowledge base unavailable. Please raise a ticket.")
            db_log_failed_query(question.strip())
            st.session_state["show_ticket"] = True
            st.session_state["ticket_query"] = question.strip()

        elif result["found"]:
            source    = result.get("source", "pdf")
            match_src = result.get("match_src", "question")

            if source == "knowledge_base":
                st.markdown("#### ✅ Answer Found")
                cat = result.get("category", "General")
                st.markdown(f"<small style='color:#0284c7'>📝 <strong>Source: Manual Knowledge Base</strong> &nbsp;<span class='kb-category'>{cat}</span></small>", unsafe_allow_html=True)
                st.markdown(f"<small style='color:#6b7280'>📌 Matched: <em>{result['matched'][:120]}</em> (score: {result['score']:.2f})</small>", unsafe_allow_html=True)
                st.markdown(f"<div class='kb-box'>{result['answer']}</div>", unsafe_allow_html=True)

            elif source == "learned":
                st.markdown("#### ✅ Answer Found")
                st.markdown("<small style='color:#059669'>💡 <strong>Source: Previously resolved support ticket</strong></small>", unsafe_allow_html=True)
                st.markdown(f"<small style='color:#6b7280'>📌 Similar question: <em>{result['matched'][:160]}</em> (similarity: {result['score']:.0%})</small>", unsafe_allow_html=True)
                st.markdown(f"<div class='learned-box'>{result['answer']}</div>", unsafe_allow_html=True)

            else:
                st.markdown("#### ✅ Answer Found")
                match_label = "matched via question" if match_src == "question" else "matched via answer content"
                st.markdown(f"<small style='color:#7c3aed'>📚 <strong>Source: PDF Knowledge Base</strong> <span style='color:#9ca3af'>({match_label})</span></small>", unsafe_allow_html=True)
                st.markdown(f"<small style='color:#6b7280'>📌 Matched: <em>{result['matched'][:120]}</em> (score: {result['score']:.2f})</small>", unsafe_allow_html=True)
                st.markdown(f"<div class='answer-box'>{result['answer']}</div>", unsafe_allow_html=True)

            st.markdown("---")
            col_a, col_b, _ = st.columns([1, 1, 4])
            with col_a:
                if st.button("👍 Helpful"):
                    st.success("Great! Glad it helped.")
            with col_b:
                if st.button("👎 Not helpful"):
                    db_log_failed_query(question.strip())
                    st.session_state["show_ticket"] = True
                    st.session_state["ticket_query"] = question.strip()
                    st.warning("Sorry! Please raise a ticket below.")

        else:
            st.markdown("#### ❌ No Answer Found")
            st.markdown("<div class='no-answer-box'>⚠️ No answer found in the knowledge base. Please fill in the ticket details below and our team will help you.</div>", unsafe_allow_html=True)
            db_log_failed_query(question.strip())
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
            if not user_id.strip():
                errors.append("Employee ID required.")
            if job_role == "Select…":
                errors.append("Select your job role.")
            if not original_question and not query_text.strip():
                errors.append("Problem description required.")
            for e in errors:
                st.error(e)
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


# ════════════════════════════════════════════════════════
#  PAGE: ADMIN PANEL
# ════════════════════════════════════════════════════════
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
    with c1:
        st.markdown("# 🛡️ Admin Dashboard")
    with c2:
        if st.button("Logout"):
            st.session_state["admin_logged_in"] = False
            st.rerun()

    # ── Stats ──────────────────────────────────────────────────────────────────
    try:
        stats = db_stats()
        cols = st.columns(5)
        for col, val, label, icon in zip(
            cols,
            [stats["total"], stats["open"], stats["in_progress"], stats["resolved"], stats["overdue"]],
            ["Total", "Open", "In Progress", "Resolved", "🔴 Overdue"],
            ["📋", "🟡", "🔵", "🟢", "🔴"]
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

    # ── Filters + Export ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1])
    with c1:
        sf = st.selectbox("Status", ["All", "Open", "In Progress", "Resolved", "Overdue"])
    with c2:
        pf = st.selectbox("Priority", ["All", "High", "Medium", "Low"])
    with c3:
        search_term = st.text_input("🔍 Search tickets", placeholder="keyword / employee ID")
    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        export_btn = st.button("📥 Export CSV", use_container_width=True)

    try:
        tickets = db_get_tickets(sf if sf not in ["All", "Overdue"] else None)
    except Exception as e:
        st.error(f"DB error: {e}")
        return

    if sf == "Overdue":
        tickets = [t for t in tickets if t.get("status") == "Open" and is_overdue(t.get("created_at", ""))]
    if pf != "All":
        tickets = [t for t in tickets if t.get("priority") == pf]
    if search_term.strip():
        kw = search_term.strip().lower()
        tickets = [t for t in tickets if kw in t.get("query", "").lower() or kw in t.get("user_id", "").lower()]

    if export_btn:
        all_tickets = db_get_tickets()
        csv_bytes = tickets_to_csv(all_tickets)
        st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="helpdesk_tickets.csv", mime="text/csv")

    if not tickets:
        st.info("No tickets found.", icon="📭")
        return

    st.markdown(f"**{len(tickets)} ticket(s)**")

    for t in tickets:
        tid = t.get("id")
        status = t.get("status", "Open")
        priority = t.get("priority", "Medium")
        created = t.get("created_at", "")
        overdue = is_overdue(created) and status == "Open"
        ticket_query = t.get("query", "")

        try:
            created_fmt = _to_ist(created)
        except Exception:
            created_fmt = created

        badge_class = "badge-overdue" if overdue else {"Open": "badge-open", "In Progress": "badge-inprogress", "Resolved": "badge-resolved"}.get(status, "badge-open")
        display_status = "🔴 OVERDUE" if overdue else status
        prio_class = {"High": "prio-high", "Medium": "prio-medium", "Low": "prio-low"}.get(priority, "prio-medium")

        with st.expander(f"🎫 #{tid} — {t.get('user_id', '?')} ({t.get('job_role', '?')}) | {display_status} | {priority} | {created_fmt}"):
            st.markdown(f"<span class='{badge_class}'>{display_status}</span>&nbsp;<span class='{prio_class}'>{priority}</span>", unsafe_allow_html=True)
            st.markdown(f"**Employee:** {t.get('user_id', '–')} &nbsp;|&nbsp; **Role:** {t.get('job_role', '–')} &nbsp;|&nbsp; **Submitted:** {created_fmt}")

            st.markdown("**📅 Ticket Timeline:**")
            st.markdown(f"<span class='timeline-dot' style='background:#7c3aed'></span> **Opened** — {created_fmt}", unsafe_allow_html=True)
            if status == "In Progress":
                st.markdown(f"<span class='timeline-dot' style='background:#3b82f6'></span> **In Progress** — being worked on", unsafe_allow_html=True)
            if status == "Resolved":
                st.markdown(f"<span class='timeline-dot' style='background:#059669'></span> **Resolved** ✅", unsafe_allow_html=True)
            if overdue:
                st.markdown(f"<span class='timeline-dot' style='background:#dc2626'></span> **⚠️ Overdue — open for more than 24 hours**", unsafe_allow_html=True)

            st.markdown("**Problem:**")
            st.markdown(f"<div class='answer-box'>{ticket_query}</div>", unsafe_allow_html=True)

            # ✅ NEW: Similar tickets panel
            if ticket_query.strip():
                similar = find_similar_resolved_tickets(ticket_query)
                if similar:
                    st.markdown("---")
                    st.markdown("**🔍 Similar Resolved Tickets — click to use a solution:**")
                    for idx, sim in enumerate(similar):
                        with st.container():
                            st.markdown(
                                f"<div class='similar-ticket-card'>"
                                f"<small style='color:#7c3aed;font-weight:600'>Match: {sim['score']:.0%}</small><br>"
                                f"<strong>Q:</strong> {sim['query'][:120]}<br>"
                                f"<strong>A:</strong> {sim['solution'][:200]}…"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            if st.button(f"✅ Use This Solution", key=f"use_sol_{tid}_{idx}"):
                                st.session_state[f"prefill_note_{tid}"] = sim["solution"]
                                st.rerun()

            st.markdown("---")

            nc1, nc2 = st.columns(2)
            with nc1:
                new_status = st.selectbox(
                    "Update Status", ["Open", "In Progress", "Resolved"],
                    index=["Open", "In Progress", "Resolved"].index(status),
                    key=f"s_{tid}"
                )
            with nc2:
                prefill_note = st.session_state.pop(f"prefill_note_{tid}", None)
                default_note = prefill_note if prefill_note is not None else (t.get("admin_note") or "")
                note = st.text_area(
                    "Admin Note / Solution",
                    value=default_note,
                    key=f"n_{tid}",
                    height=100,
                    placeholder="Write solution here — auto-saved to knowledge base on Save."
                )

            # ✅ NEW: Show hint about auto-save
            if note.strip():
                st.markdown("<small style='color:#059669'>💡 <strong>Note will be auto-saved to knowledge base on Save</strong> (no manual step needed)</small>", unsafe_allow_html=True)

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

                    # ✅ NEW: Auto-save note to KB on ANY save (not just Resolved)
                    if note.strip():
                        saved = auto_save_note_to_kb(ticket_query, note)
                        if saved:
                            st.success("✅ Ticket updated & note auto-saved to knowledge base!")
                        else:
                            st.success("✅ Ticket updated!")
                    else:
                        st.success("✅ Ticket updated!")

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


# ════════════════════════════════════════════════════════
#  PAGE: KNOWLEDGE BASE EDITOR  ✅ NEW PAGE
# ════════════════════════════════════════════════════════
def page_knowledge_base():
    if not st.session_state.get("admin_logged_in"):
        st.warning("Please log in via the Admin Panel first.")
        return

    st.markdown("# 📚 Knowledge Base Editor")
    st.markdown("<p style='color:#6b7280'>Manually add, edit, or delete Q&A entries. These are checked <strong>before</strong> the PDF — no PDF edit needed.</p>", unsafe_allow_html=True)
    st.markdown("---")

    entries = db_kb_get_all()

    # ── Summary ───────────────────────────────────────────────────────────────
    categories = [e.get("category", "General") for e in entries]
    cat_counts = Counter(categories)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{len(entries)}</div><div class='metric-label'>Total KB Entries</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{len(cat_counts)}</div><div class='metric-label'>Categories</div></div>", unsafe_allow_html=True)
    with col3:
        most_common_cat = cat_counts.most_common(1)[0][0] if cat_counts else "—"
        st.markdown(f"<div class='metric-card'><div class='metric-number' style='font-size:22px'>{most_common_cat}</div><div class='metric-label'>Top Category</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Add New Entry ─────────────────────────────────────────────────────────
    st.markdown("### ➕ Add New Q&A Entry")
    with st.expander("Click to add a new entry", expanded=False):
        nq_col, nc_col = st.columns([3, 1])
        with nq_col:
            new_question = st.text_input("Question *", placeholder="e.g. How do I reset my password?", key="new_kb_q")
        with nc_col:
            new_category = st.selectbox("Category", [
                "General", "IT Support", "HR / Policies", "Software Engineering",
                "Data & Analytics", "DevOps", "Security", "Onboarding", "Finance", "Other"
            ], key="new_kb_cat")
        new_answer = st.text_area("Answer *", placeholder="Write the full answer here…", height=120, key="new_kb_a")

        if st.button("➕ Add to Knowledge Base", use_container_width=False):
            if not new_question.strip() or not new_answer.strip():
                st.error("Both Question and Answer are required.")
            else:
                try:
                    db_kb_add(new_question.strip(), new_answer.strip(), new_category, "admin")
                    st.success(f"✅ Entry added to Knowledge Base under '{new_category}'!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.markdown("---")

    # ── Search within KB ──────────────────────────────────────────────────────
    st.markdown("### 🔍 Browse & Edit Entries")
    scol1, scol2 = st.columns([3, 1])
    with scol1:
        kb_search = st.text_input("Search KB entries", placeholder="Filter by keyword…", label_visibility="collapsed")
    with scol2:
        cat_filter = st.selectbox("Filter by Category", ["All"] + sorted(set(e.get("category", "General") for e in entries)), label_visibility="collapsed")

    filtered = entries
    if kb_search.strip():
        kw = kb_search.strip().lower()
        filtered = [e for e in filtered if kw in e.get("question", "").lower() or kw in e.get("answer", "").lower()]
    if cat_filter != "All":
        filtered = [e for e in filtered if e.get("category") == cat_filter]

    st.markdown(f"**{len(filtered)} entr{'y' if len(filtered)==1 else 'ies'}**")

    if not filtered:
        st.info("No entries found. Add some above!", icon="📭")
        return

    for entry in filtered:
        kid = entry.get("id")
        question = entry.get("question", "")
        answer = entry.get("answer", "")
        category = entry.get("category", "General")
        created = entry.get("created_at", "")
        updated = entry.get("updated_at", "")

        try:
            created_fmt = _to_ist(created)
        except Exception:
            created_fmt = created

        try:
            updated_fmt = _to_ist(updated)
        except Exception:
            updated_fmt = updated

        with st.expander(f"📝 [{category}] {question[:90]}{'…' if len(question)>90 else ''} &nbsp;&nbsp;<small>Added {created_fmt}</small>"):
            st.markdown(f"<span class='kb-category'>{category}</span> &nbsp;<small style='color:#9ca3af'>Last updated: {updated_fmt}</small>", unsafe_allow_html=True)

            edit_col1, edit_col2 = st.columns([3, 1])
            with edit_col1:
                edit_q = st.text_input("Question", value=question, key=f"eq_{kid}")
            with edit_col2:
                edit_cat = st.selectbox("Category", [
                    "General", "IT Support", "HR / Policies", "Software Engineering",
                    "Data & Analytics", "DevOps", "Security", "Onboarding", "Finance", "Other"
                ], index=["General", "IT Support", "HR / Policies", "Software Engineering",
                    "Data & Analytics", "DevOps", "Security", "Onboarding", "Finance", "Other"].index(category) if category in ["General", "IT Support", "HR / Policies", "Software Engineering", "Data & Analytics", "DevOps", "Security", "Onboarding", "Finance", "Other"] else 0,
                key=f"ecat_{kid}")
            edit_a = st.text_area("Answer", value=answer, height=120, key=f"ea_{kid}")

            upd_col, del_col, _ = st.columns([1, 1, 4])
            with upd_col:
                if st.button("💾 Update", key=f"upd_{kid}", use_container_width=True):
                    if not edit_q.strip() or not edit_a.strip():
                        st.error("Question and Answer cannot be empty.")
                    else:
                        try:
                            db_kb_update(kid, edit_q.strip(), edit_a.strip(), edit_cat)
                            st.success("✅ Entry updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            with del_col:
                if st.button("🗑️ Delete", key=f"delkb_{kid}", use_container_width=True):
                    try:
                        db_kb_delete(kid)
                        st.warning("Entry deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    # ── Export KB ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Export Knowledge Base")
    if entries:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "question", "answer", "category", "created_by", "created_at", "updated_at"])
        writer.writeheader()
        for e in entries:
            writer.writerow({k: e.get(k, "") for k in writer.fieldnames})
        csv_data = output.getvalue().encode("utf-8")
        st.download_button("⬇️ Download Knowledge Base as CSV", data=csv_data, file_name="knowledge_base.csv", mime="text/csv")


# ════════════════════════════════════════════════════════
#  PAGE: ANALYTICS DASHBOARD
# ════════════════════════════════════════════════════════
def page_analytics():
    if not st.session_state.get("admin_logged_in"):
        st.warning("Please log in via the Admin Panel first.")
        return

    st.markdown("# 📊 Analytics Dashboard")
    st.markdown("---")

    try:
        import plotly.express as px
        import pandas as pd
    except ImportError:
        st.error("Please install plotly and pandas: `pip install plotly pandas`")
        return

    tickets = db_get_tickets()
    if not tickets:
        st.info("No ticket data yet.")
        return

    df = pd.DataFrame(tickets)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["date"] = df["created_at"].dt.tz_convert("Asia/Kolkata").dt.strftime("%d %b %Y")

    col1, col2, col3, col4 = st.columns(4)
    resolved = df[df["status"] == "Resolved"]
    resolution_rate = round(len(resolved) / len(df) * 100, 1) if len(df) else 0

    with col1:
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{len(df)}</div><div class='metric-label'>Total Tickets</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{resolution_rate}%</div><div class='metric-label'>Resolution Rate</div></div>", unsafe_allow_html=True)
    with col3:
        open_count = len(df[df["status"] == "Open"])
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{open_count}</div><div class='metric-label'>Open Tickets</div></div>", unsafe_allow_html=True)
    with col4:
        high_prio = len(df[df["priority"] == "High"])
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{high_prio}</div><div class='metric-label'>High Priority</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### 📅 Tickets Per Day")
        daily = df.groupby("date").size().reset_index(name="count")
        fig1 = px.bar(daily, x="date", y="count", color_discrete_sequence=["#7c3aed"], text="count")
        fig1.update_layout(xaxis_title="Date", yaxis_title="Number of Tickets", plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=20, b=80), bargap=0.4, xaxis=dict(tickangle=-35, type="category", tickfont=dict(size=11)), yaxis=dict(tickformat="d", dtick=1))
        fig1.update_traces(textposition="outside", marker_line_width=0, marker_color="#7c3aed")
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.markdown("### 🥧 Ticket Status Breakdown")
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig2 = px.pie(status_counts, names="status", values="count", color="status", color_discrete_map={"Open": "#f59e0b", "In Progress": "#3b82f6", "Resolved": "#10b981"}, hole=0.35)
        fig2.update_traces(textinfo="label+percent", textfont_size=13)
        fig2.update_layout(margin=dict(t=20), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("### 🚨 Tickets by Priority")
        prio_order = ["High", "Medium", "Low"]
        prio_counts = df["priority"].value_counts().reindex(prio_order, fill_value=0).reset_index()
        prio_counts.columns = ["priority", "count"]
        fig3 = px.bar(prio_counts, x="priority", y="count", color="priority", color_discrete_map={"High": "#ef4444", "Medium": "#f59e0b", "Low": "#10b981"}, text="count", category_orders={"priority": prio_order})
        fig3.update_layout(showlegend=False, plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=20), bargap=0.45, xaxis_title="Priority Level", yaxis=dict(title="Count", tickformat="d", dtick=1))
        fig3.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown("### 💼 Tickets by Job Role")
        role_counts = df["job_role"].value_counts().reset_index()
        role_counts.columns = ["role", "count"]
        fig4 = px.bar(role_counts, x="count", y="role", orientation="h", color_discrete_sequence=["#7c3aed"], text="count")
        fig4.update_layout(xaxis=dict(title="Number of Tickets", tickformat="d", dtick=1), yaxis_title="", plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=20, l=140), bargap=0.35, height=max(300, len(role_counts) * 50))
        fig4.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📥 Export Data")
    csv_bytes = tickets_to_csv(tickets)
    st.download_button("⬇️ Download All Tickets as CSV", data=csv_bytes, file_name="helpdesk_tickets.csv", mime="text/csv")


# ════════════════════════════════════════════════════════
#  PAGE: KNOWLEDGE GAP REPORT
# ════════════════════════════════════════════════════════
def page_knowledge_gap():
    if not st.session_state.get("admin_logged_in"):
        st.warning("Please log in via the Admin Panel first.")
        return

    st.markdown("# 🕳️ Knowledge Gap Report")
    st.markdown("<p style='color:#6b7280'>Questions employees asked that the system couldn't answer. Use this to improve your PDF knowledge base or add entries via the Knowledge Base Editor.</p>", unsafe_allow_html=True)
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
        st.success("🎉 No knowledge gaps yet! Every question has been answered.", icon="✅")
        return

    queries = [r["query"] for r in rows]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{len(queries)}</div><div class='metric-label'>Total Unanswered Questions</div></div>", unsafe_allow_html=True)
    with col2:
        unique = len(set(q.lower().strip() for q in queries))
        st.markdown(f"<div class='metric-card'><div class='metric-number'>{unique}</div><div class='metric-label'>Unique Questions</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    # ✅ NEW: Quick-add button for each gap question
    st.markdown("### 📋 All Unanswered Questions")
    st.caption("Add answers directly to the Knowledge Base — no PDF editing needed.")

    for i, row in enumerate(rows, 1):
        created = row.get("created_at", "")
        try:
            date_fmt = _to_ist(created)
        except Exception:
            date_fmt = created

        st.markdown(
            f"<div class='gap-card'>"
            f"<span class='gap-count'>#{i}</span> &nbsp;"
            f"<strong>{row['query']}</strong>"
            f"<br><small style='color:#9ca3af'>Asked on {date_fmt}</small>"
            f"</div>",
            unsafe_allow_html=True
        )
        # Quick add to KB
        if st.button(f"➕ Add to KB", key=f"gap_add_{i}"):
            st.session_state["kb_prefill_q"] = row["query"]
            st.session_state["nav_to_kb"] = True
            st.info("Go to the 📚 Knowledge Base page to complete this entry (question pre-filled).")

    st.markdown("---")
    st.markdown("### 🔑 Most Requested Missing Topics")
    all_words = []
    for q in queries:
        all_words.extend(_content_words(q))
    word_freq = Counter(all_words).most_common(15)

    if word_freq:
        try:
            import plotly.express as px
            import pandas as pd
            wdf = pd.DataFrame(word_freq, columns=["keyword", "count"])
            fig = px.bar(wdf, x="count", y="keyword", orientation="h", color_discrete_sequence=["#f97316"], text="count")
            fig.update_layout(xaxis=dict(title="Times Asked", tickformat="d", dtick=1), yaxis_title="", plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, l=120), height=max(300, len(wdf) * 40), bargap=0.35)
            fig.update_traces(textposition="outside", marker_line_width=0)
            fig.update_yaxes(autorange="reversed", tickfont=dict(size=12))
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            for word, count in word_freq:
                st.markdown(f"**{word}** — asked {count} time(s)")

    st.markdown("---")
    if st.button("🗑️ Clear All Failed Queries (after fixing KB)"):
        try:
            db.table("failed_queries").delete().neq("id", 0).execute()
            st.success("Cleared!")
            st.rerun()
        except Exception as e:
            st.error(str(e))


# ════════════════════════════════════════════════════════
#  PAGE: SETUP
# ════════════════════════════════════════════════════════
def page_setup():
    st.markdown("# ⚙️ Setup & Configuration")
    with st.expander("📁 Streamlit Secrets", expanded=True):
        st.code('[secrets]\nSUPABASE_URL   = "https://xxxx.supabase.co"\nSUPABASE_KEY   = "eyJ..."\nADMIN_PASSWORD = "your_password"', language="toml")
    with st.expander("🗄️ Create Supabase Tables (run all)", expanded=True):
        st.code(SCHEMA_SQL, language="sql")
    with st.expander("📦 Install Dependencies"):
        st.code("pip install streamlit supabase pdfplumber sentence-transformers requests torch plotly pandas", language="bash")

    st.markdown("---")
    st.markdown("### 🔌 Connection Status")
    c1, c2 = st.columns(2)
    with c1:
        if st.secrets.get("SUPABASE_URL", ""):
            st.success("✅ Supabase URL configured")
        else:
            st.error("❌ Supabase URL missing")
    with c2:
        if st.secrets.get("SUPABASE_KEY", ""):
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

    if st.button("🧪 Test Knowledge Base Table"):
        try:
            db = get_db()
            if db is None:
                st.error("Not configured.")
            else:
                db.table("knowledge_base").select("id").limit(1).execute()
                count = len(db_kb_get_all())
                st.success(f"✅ knowledge_base table OK — {count} entries")
        except Exception as e:
            st.error(f"Failed (did you run the CREATE TABLE SQL?): {e}")

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

    if st.button("🧠 Test Semantic Search Model"):
        model, q_emb, a_emb, pairs, util = load_model_and_embeddings()
        if model is None:
            st.error("❌ Model failed to load.")
        else:
            st.success("✅ Model loaded: multi-qa-mpnet-base-dot-v1")
            st.info(f"📊 {len(pairs)} Q embeddings + {len(pairs)} A embeddings ready.")

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
                    st.info("No learned answers yet.")
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
        "📊 Analytics",
        "🕳️ Knowledge Gap Report",
        "📚 Knowledge Base",
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
elif page == "📊 Analytics":
    page_analytics()
elif page == "🕳️ Knowledge Gap Report":
    page_knowledge_gap()
elif page == "📚 Knowledge Base":
    page_knowledge_base()
elif page == "📋 Approval Pipeline":
    if PIPELINE_AVAILABLE:
        page_approval_pipeline()
    else:
        st.error("❌ `approval_pipeline.py` is missing from your project folder.")
elif page == "⚙️ Setup / Config":
    page_setup()
