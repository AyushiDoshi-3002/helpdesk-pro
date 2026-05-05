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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f0c29, #302b63, #24243e); }
section[data-testid="stSidebar"] * { color: white !important; }
.main { background: #eaf6ff; }
.stApp { background: #eaf6ff; }
[data-testid="stAppViewContainer"] { background: #eaf6ff; }
[data-testid="stMain"] { background: #eaf6ff; }
.answer-box { background: linear-gradient(135deg, #ede9fe, #ddd6fe); border-radius: 12px; padding: 20px; border-left: 4px solid #7c3aed; font-size: 15px; line-height: 1.7; color: #1e1b4b; }
.no-answer-box { background: #fff7ed; border-radius: 12px; padding: 16px 20px; border-left: 4px solid #f97316; color: #7c2d12; font-size: 14px; }
.learned-box { background: linear-gradient(135deg, #d1fae5, #a7f3d0); border-radius: 12px; padding: 20px; border-left: 4px solid #059669; font-size: 15px; line-height: 1.7; color: #064e3b; }
.badge-open { background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-inprogress { background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-resolved { background:#d1fae5;color:#065f46;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.badge-overdue { background:#fee2e2;color:#991b1b;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600; }
.prio-high { background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-medium { background: #eaf6ff;color:#854d0e;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
.prio-low { background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700; }
div.stButton > button { background: linear-gradient(135deg, #7c3aed, #5b21b6); color: white; border: none; border-radius: 10px; padding: 10px 24px; font-weight: 600; font-size: 14px; }
div.stButton > button:hover { background: linear-gradient(135deg, #6d28d9, #4c1d95); }
.metric-card { background:white;border-radius:14px;padding:20px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,0.06); }
.metric-number { font-family:'Syne',sans-serif;font-size:36px;font-weight:800;color:#7c3aed; }
.metric-label { font-size:13px;color:#6b7280;margin-top:4px; }
.gap-card { background:white;border-radius:12px;padding:16px;margin-bottom:10px;border-left:4px solid #f97316;box-shadow:0 2px 8px rgba(0,0,0,0.05); }
.gap-count { font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#f97316; }
.timeline-dot { width:12px;height:12px;border-radius:50%;display:inline-block;margin-right:8px; }

/* Doc Validator styles */
.validator-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    margin-bottom: 20px;
}
.sensitive-badge {
    display: inline-block;
    background: linear-gradient(135deg, #fee2e2, #fecaca);
    color: #991b1b;
    border: 1.5px solid #fca5a5;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.3px;
}
.normal-badge {
    display: inline-block;
    background: linear-gradient(135deg, #d1fae5, #a7f3d0);
    color: #065f46;
    border: 1.5px solid #6ee7b7;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.3px;
}
.chain-step {
    display: inline-flex;
    align-items: center;
    background: #eff6ff;
    border: 1.5px solid #bfdbfe;
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 600;
    color: #1e40af;
    margin: 4px;
}
.chain-arrow {
    font-size: 20px;
    color: #9ca3af;
    margin: 0 2px;
}
.auto-approve-box {
    background: linear-gradient(135deg, #f0fdf4, #dcfce7);
    border: 2px solid #86efac;
    border-radius: 14px;
    padding: 20px 24px;
    text-align: center;
}
.sensitive-box {
    background: linear-gradient(135deg, #fff1f2, #ffe4e6);
    border: 2px solid #fda4af;
    border-radius: 14px;
    padding: 20px 24px;
}
.validator-title {
    font-family: 'Syne', sans-serif;
    font-size: 22px;
    font-weight: 800;
    color: #1e1b4b;
    margin-bottom: 4px;
}
.keyword-tag {
    display: inline-block;
    background: #f3f4f6;
    color: #374151;
    border-radius: 8px;
    padding: 2px 10px;
    font-size: 12px;
    margin: 2px;
    border: 1px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  IMPORT APPROVAL PIPELINE
# ════════════════════════════════════════════════════════
try:
    from approval_pipeline import page_approval_pipeline, DOC_CATEGORIES, _build_chain, _classify_request
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
            st.toast(f"🎫 Ticket #{ticket.get('id')} saved to `tickets` table in Supabase!", icon="☁️")
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
        st.toast(f"✏️ Ticket #{tid} updated in `tickets` table → status: {status}", icon="☁️")
    except Exception as e:
        raise Exception(f"Update failed: {e}")

def db_delete_ticket(tid):
    db = get_db()
    if db:
        try:
            db.table("tickets").delete().eq("id", tid).execute()
            st.toast(f"🗑️ Ticket #{tid} deleted from `tickets` table in Supabase", icon="☁️")
        except Exception as e:
            raise Exception(f"Delete failed: {e}")

def db_log_failed_query(query: str):
    db = get_db()
    if db:
        try:
            db.table("failed_queries").insert({"query": query}).execute()
            st.toast("📋 Unanswered question logged to `failed_queries` table in Supabase", icon="☁️")
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
#  AUTO-SAVE NOTE TO RESOLVED ISSUES
# ════════════════════════════════════════════════════════
def auto_save_note_to_resolved(ticket_query: str, note: str):
    db = get_db()
    if db is None or not note.strip() or not ticket_query.strip():
        return False
    try:
        existing = db.table("resolved_issues").select("id").eq("query", ticket_query).execute()
        if not existing.data:
            db.table("resolved_issues").insert({"query": ticket_query, "solution": note.strip()}).execute()
            st.toast("🧠 Admin note saved as new learned answer in `resolved_issues` table!", icon="☁️")
        else:
            db.table("resolved_issues").update({"solution": note.strip()}).eq("query", ticket_query).execute()
            st.toast("🧠 Learned answer updated in `resolved_issues` table in Supabase", icon="☁️")
        return True
    except Exception:
        return False


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
_Q_THRESHOLD   = 0.60
_A_THRESHOLD   = 0.65
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
#  ANSWER LOOKUP  (PDF → Learned)
# ════════════════════════════════════════════════════════
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
#  DOC VALIDATOR LOGIC
# ════════════════════════════════════════════════════════

# Keywords that flag a document as SENSITIVE → must go through pipeline
_SENSITIVE_KEYWORDS = [
    # Network / Access
    "vpn", "virtual private network", "network access", "firewall", "proxy",
    "remote access", "zero trust", "ssl vpn", "ipsec",
    # Security
    "security", "cybersecurity", "penetration test", "pentest", "vulnerability",
    "encryption", "cryptography", "access control", "identity", "iam",
    "sso", "single sign-on", "mfa", "multi-factor", "certificate", "ssl", "tls",
    # Legal / Compliance
    "legal", "contract", "nda", "agreement", "gdpr", "compliance", "audit",
    "regulation", "policy", "terms of service", "data protection", "privacy",
    # Financial
    "financial", "budget", "invoice", "payment", "salary", "payroll",
    "revenue", "expense", "accounting", "tax", "billing",
    # Infrastructure
    "infrastructure", "cloud", "aws", "gcp", "azure", "kubernetes", "k8s",
    "server", "database schema", "production", "disaster recovery", "backup",
    # Sensitive data
    "pii", "personal data", "sensitive data", "confidential", "classified",
    "secret", "restricted", "privileged",
]

# Keywords that flag a document as NORMAL → auto-approved
_NORMAL_KEYWORDS = [
    "faq", "onboarding", "general", "guide", "how to", "tutorial",
    "overview", "introduction", "readme", "changelog", "release notes",
    "meeting notes", "team update", "announcement",
]

def classify_doc_sensitivity(title: str, description: str) -> dict:
    """
    Classifies whether a document is SENSITIVE (needs pipeline) or NORMAL (auto-approved).
    Returns a dict with: is_sensitive, reason, matched_keywords, chain, category
    """
    combined = (title + " " + description).lower()

    # Check sensitive keywords first
    matched_sensitive = [kw for kw in _SENSITIVE_KEYWORDS if kw in combined]
    matched_normal    = [kw for kw in _NORMAL_KEYWORDS    if kw in combined]

    if matched_sensitive:
        # Determine which category from approval_pipeline
        if PIPELINE_AVAILABLE:
            result     = _classify_request(f"I need to create a document about {title}. {description}")
            category   = result.get("category", "Security")
            chain      = _build_chain(category)
            cat_config = DOC_CATEGORIES.get(category, {})
            # Force sensitive docs to always go through chain even if category is General
            if not chain:
                chain    = ["Team Lead", "Tech Manager", "CTO", "CEO"]
                category = "Security"
        else:
            category = "Security"
            chain    = ["Team Lead", "Tech Manager", "CTO", "CEO"]

        return {
            "is_sensitive":       True,
            "category":           category,
            "matched_keywords":   matched_sensitive[:6],   # show up to 6
            "chain":              chain,
            "reason":             f"This document contains sensitive content ({', '.join(matched_sensitive[:3])}…) and must go through the full approval pipeline.",
        }
    else:
        return {
            "is_sensitive":       False,
            "category":           "General",
            "matched_keywords":   matched_normal[:6],
            "chain":              [],
            "reason":             "This document does not contain sensitive content and will be auto-approved instantly.",
        }


# ════════════════════════════════════════════════════════
#  PAGE: EMPLOYEE PORTAL
# ════════════════════════════════════════════════════════
def page_employee():
    st.markdown("# 🔍 Employee Help Portal")
    st.markdown("<p style='color:#6b7280'>Ask any question. If no answer is found, raise a support ticket.</p>", unsafe_allow_html=True)
    st.markdown("---")

    pairs = load_qa_pairs()
    if len(pairs) == 0:
        st.error("⚠️ PDF knowledge base could not be loaded.")
    else:
        st.success(f"📚 PDF Knowledge Base: {len(pairs)} Q&A pairs", icon="✅")

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

            if source == "learned":
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
                if st.button("👍 Helpful", key="emp_helpful"):
                    st.success("Great! Glad it helped.")
            with col_b:
                if st.button("👎 Not helpful", key="emp_not_helpful"):
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
            user_id = st.text_input("👤 Employee ID *", placeholder="e.g. EMP-1042", key="emp_user_id")
            job_role = st.selectbox("💼 Job Role *", ["Select…", "Software Engineer", "Data Analyst", "QA Engineer", "DevOps Engineer", "Product Manager", "HR / Operations", "Other"], key="emp_job_role")
        with c2:
            priority = st.selectbox("🚨 Priority *", ["Medium", "High", "Low"], key="emp_priority")

        original_question = st.session_state.get("ticket_query", "")
        if original_question:
            st.markdown(f"<small style='color:#7c3aed'>🔍 Your search question: <strong>{original_question}</strong></small>", unsafe_allow_html=True)
        query_text = st.text_area("📋 Describe your problem in detail *", value="", placeholder="Add more details about your issue…", height=120, key="emp_query_text")

        col_sub, col_cancel, _ = st.columns([1, 1, 4])
        with col_sub:
            if st.button("🚀 Submit Ticket", use_container_width=True, key="emp_submit"):
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
                        st.toast(f"🎉 Ticket #{t.get('id')} submitted & stored in Supabase `tickets` table!", icon="✅")
                        st.success(f"✅ Ticket #{t.get('id', '–')} submitted! Our team will respond shortly.", icon="🎉")
                        st.session_state["show_ticket"] = False
                    except Exception as ex:
                        st.error(f"Failed: {ex}")
        with col_cancel:
            if st.button("✖ Cancel", use_container_width=True, key="emp_cancel"):
                st.session_state["show_ticket"] = False
                st.rerun()


# ════════════════════════════════════════════════════════
#  PAGE: ADMIN PANEL  (with Doc Validator tab)
# ════════════════════════════════════════════════════════
def page_admin():
    ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "admin123")
    if not st.session_state.get("admin_logged_in"):
        st.markdown("# 🛡️ Admin Panel")
        st.markdown("---")
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
        st.markdown("# 🛡️ Admin Dashboard")
    with c2:
        if st.button("Logout", key="admin_logout_btn"):
            st.session_state["admin_logged_in"] = False
            st.toast("👋 Admin logged out", icon="🔒")
            st.rerun()

    # ── Admin tabs ────────────────────────────────────────────────────────────
    admin_tab1, admin_tab2 = st.tabs(["📋 Ticket Management", "🔍 Doc Validator"])

    # ══════════════════════════════════════════
    #  TAB 1 — Ticket Management (original)
    # ══════════════════════════════════════════
    with admin_tab1:
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

        c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1])
        with c1:
            sf = st.selectbox("Status", ["All", "Open", "In Progress", "Resolved", "Overdue"], key="admin_filter_status")
        with c2:
            pf = st.selectbox("Priority", ["All", "High", "Medium", "Low"], key="admin_filter_priority")
        with c3:
            search_term = st.text_input("🔍 Search tickets", placeholder="keyword / employee ID", key="admin_search_term")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            export_btn = st.button("📥 Export CSV", use_container_width=True, key="admin_export_btn")

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
            st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="helpdesk_tickets.csv", mime="text/csv", key="admin_download_csv")
            st.toast("📥 CSV exported from `tickets` table", icon="✅")

        if not tickets:
            st.info("No tickets found.", icon="📭")
        else:
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
                    st.markdown("---")

                    nc1, nc2 = st.columns(2)
                    with nc1:
                        new_status = st.selectbox(
                            "Update Status", ["Open", "In Progress", "Resolved"],
                            index=["Open", "In Progress", "Resolved"].index(status),
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
                        if st.button("💾 Save", key=f"admin_save_{tid}", use_container_width=True):
                            try:
                                db_update_ticket(tid, new_status, note)
                                if note.strip():
                                    auto_save_note_to_resolved(ticket_query, note)
                                st.success("✅ Ticket updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                    with bc2:
                        if st.button("🗑️ Delete", key=f"admin_del_{tid}", use_container_width=True):
                            try:
                                db_delete_ticket(tid)
                                st.warning("Deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

    # ══════════════════════════════════════════
    #  TAB 2 — Doc Validator
    # ══════════════════════════════════════════
    with admin_tab2:
        _render_doc_validator()


# ════════════════════════════════════════════════════════
#  DOC VALIDATOR UI
# ════════════════════════════════════════════════════════
def _render_doc_validator():
    st.markdown("""
    <div style='margin-bottom: 8px;'>
        <p class='validator-title'>🔍 Document Sensitivity Validator</p>
        <p style='color:#6b7280; font-size:14px; margin-top:0;'>
            Enter your document details below. The system will instantly classify it as
            <strong>Sensitive</strong> (requires full approval pipeline) or
            <strong>Normal</strong> (auto-approved).
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form("doc_validator_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            doc_title = st.text_input(
                "📄 Document Title *",
                placeholder="e.g. VPN Access Policy, Employee Onboarding Guide…",
                key="dv_title"
            )
        with col2:
            doc_type_hint = st.selectbox(
                "📂 Document Hint (optional)",
                ["— Let the system decide —", "VPN / Network", "Security Policy",
                 "Legal / Compliance", "Financial", "Infrastructure",
                 "Technical Guide", "Team Process", "FAQ / Onboarding", "General"],
                key="dv_type_hint"
            )

        doc_description = st.text_area(
            "📝 Document Description *",
            placeholder="Briefly describe what this document covers, its purpose, and intended audience…",
            height=120,
            key="dv_description"
        )

        validate_btn = st.form_submit_button(
            "🔍 Validate Document",
            type="primary",
            use_container_width=False
        )

    # ── Validation result ─────────────────────────────────────────────────────
    if validate_btn:
        if not doc_title.strip() or not doc_description.strip():
            st.warning("⚠️ Please fill in both the Document Title and Description.")
        else:
            # Append type hint to description for better classification
            hint_text = doc_description.strip()
            if doc_type_hint != "— Let the system decide —":
                hint_text += f" {doc_type_hint}"

            result = classify_doc_sensitivity(doc_title.strip(), hint_text)
            st.session_state["dv_result"]      = result
            st.session_state["dv_last_title"]  = doc_title.strip()
            st.session_state["dv_last_desc"]   = doc_description.strip()

    # ── Show result if available ──────────────────────────────────────────────
    result = st.session_state.get("dv_result")
    if result:
        st.markdown("---")
        st.markdown("### 📊 Validation Result")

        is_sensitive = result["is_sensitive"]

        if is_sensitive:
            # ── SENSITIVE result ──────────────────────────────────────────────
            st.markdown(f"""
            <div class='sensitive-box'>
                <div style='display:flex; align-items:center; gap:12px; margin-bottom:14px;'>
                    <span style='font-size:36px;'>🔴</span>
                    <div>
                        <span class='sensitive-badge'>🔒 SENSITIVE DOCUMENT</span>
                        <p style='margin:6px 0 0 0; color:#7f1d1d; font-size:14px;'>
                            {result["reason"]}
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Detected keywords
            if result["matched_keywords"]:
                kw_html = "".join(
                    f"<span class='keyword-tag'>🔑 {kw}</span>"
                    for kw in result["matched_keywords"]
                )
                st.markdown(f"""
                <div style='margin-bottom:16px;'>
                    <p style='font-size:13px; color:#6b7280; margin-bottom:6px;'>
                        <strong>Detected sensitive keywords:</strong>
                    </p>
                    {kw_html}
                </div>
                """, unsafe_allow_html=True)

            # Approval chain preview
            chain = result["chain"]
            if chain:
                st.markdown("#### 🔗 Required Approval Chain")
                st.markdown(
                    "<p style='color:#6b7280; font-size:13px; margin-top:-8px;'>"
                    f"This document must be approved by all {len(chain)} level(s) before it is published.</p>",
                    unsafe_allow_html=True
                )

                # Visual chain
                chain_html = ""
                for i, role in enumerate(chain):
                    role_icons = {
                        "Team Lead":    "👨‍💼",
                        "Tech Manager": "👩‍💻",
                        "CTO":          "🧑‍🔬",
                        "CEO":          "👑",
                    }
                    icon = role_icons.get(role, "👤")
                    chain_html += f"<span class='chain-step'>{icon} {role}</span>"
                    if i < len(chain) - 1:
                        chain_html += "<span class='chain-arrow'>→</span>"

                st.markdown(
                    f"<div style='display:flex; flex-wrap:wrap; align-items:center; "
                    f"gap:4px; padding:16px; background:#eff6ff; border-radius:12px; "
                    f"border:1.5px solid #bfdbfe;'>{chain_html}</div>",
                    unsafe_allow_html=True
                )

                st.markdown("<br>", unsafe_allow_html=True)

                # Timeline breakdown
                st.markdown("#### 📅 Approval Timeline")
                for i, role in enumerate(chain):
                    role_descs = {
                        "Team Lead":    "Reviews team-level concerns and day-to-day impact.",
                        "Tech Manager": "Assesses technical risk and implementation feasibility.",
                        "CTO":          "Evaluates architectural and strategic technology alignment.",
                        "CEO":          "Final sign-off for company-wide policy and risk exposure.",
                    }
                    desc   = role_descs.get(role, "Reviews and approves the document.")
                    colors = ["#7c3aed", "#3b82f6", "#0891b2", "#059669"]
                    color  = colors[i % len(colors)]
                    st.markdown(
                        f"<div style='display:flex; gap:12px; align-items:flex-start; "
                        f"margin-bottom:10px; padding:12px 16px; background:white; "
                        f"border-radius:10px; border-left:4px solid {color};'>"
                        f"<span style='font-size:22px; min-width:32px; text-align:center;'>"
                        f"{'👨‍💼' if role=='Team Lead' else '👩‍💻' if role=='Tech Manager' else '🧑‍🔬' if role=='CTO' else '👑'}"
                        f"</span>"
                        f"<div>"
                        f"<p style='margin:0; font-weight:700; color:{color};'>Stage {i+1}: {role}</p>"
                        f"<p style='margin:2px 0 0 0; font-size:13px; color:#6b7280;'>{desc}</p>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

            # Action buttons
            st.markdown("---")
            st.markdown("#### ⚡ Next Steps")
            act_col1, act_col2, _ = st.columns([2, 2, 3])
            with act_col1:
                if PIPELINE_AVAILABLE:
                    if st.button("🚀 Submit to Approval Pipeline", use_container_width=True, type="primary", key="dv_submit_pipeline"):
                        # Store prefill info so the pipeline form can use it
                        st.session_state["ap_ai_prefill"] = {
                            "title":    st.session_state.get("dv_last_title", ""),
                            "category": result.get("category", "Security"),
                            "subtype":  "Compliance",
                            "urgency":  "Normal",
                        }
                        st.session_state["ap_show_prefill_form"] = True
                        st.session_state["nav_page"] = "📋 Approval Pipeline"
                        st.success("✅ Pre-filled! Navigate to the **Approval Pipeline** page to submit.")
                else:
                    st.info("Approval Pipeline not available.")
            with act_col2:
                if st.button("🔄 Validate Another Doc", use_container_width=True, key="dv_reset"):
                    st.session_state.pop("dv_result", None)
                    st.rerun()

        else:
            # ── NORMAL result ─────────────────────────────────────────────────
            st.markdown(f"""
            <div class='auto-approve-box'>
                <div style='display:flex; align-items:center; gap:12px; margin-bottom:10px;'>
                    <span style='font-size:40px;'>✅</span>
                    <div>
                        <span class='normal-badge'>✅ NORMAL DOCUMENT — AUTO-APPROVED</span>
                        <p style='margin:6px 0 0 0; color:#14532d; font-size:14px;'>
                            {result["reason"]}
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            if result["matched_keywords"]:
                kw_html = "".join(
                    f"<span class='keyword-tag' style='background:#f0fdf4; border-color:#86efac;'>✅ {kw}</span>"
                    for kw in result["matched_keywords"]
                )
                st.markdown(f"""
                <div style='margin-bottom:16px;'>
                    <p style='font-size:13px; color:#6b7280; margin-bottom:6px;'>
                        <strong>Detected normal-content keywords:</strong>
                    </p>
                    {kw_html}
                </div>
                """, unsafe_allow_html=True)

            st.info(
                "💡 **No approval chain needed.** This document will be instantly approved "
                "when submitted through the Approval Pipeline. You can proceed directly to submission.",
                icon="ℹ️"
            )

            st.markdown("---")
            act_col1, act_col2, _ = st.columns([2, 2, 3])
            with act_col1:
                if PIPELINE_AVAILABLE:
                    if st.button("🚀 Submit to Approval Pipeline", use_container_width=True, type="primary", key="dv_submit_normal"):
                        st.session_state["ap_ai_prefill"] = {
                            "title":    st.session_state.get("dv_last_title", ""),
                            "category": "General",
                            "subtype":  "General Info",
                            "urgency":  "Normal",
                        }
                        st.session_state["ap_show_prefill_form"] = True
                        st.success("✅ Pre-filled! Navigate to the **Approval Pipeline** page to submit.")
                else:
                    st.info("Approval Pipeline not available.")
            with act_col2:
                if st.button("🔄 Validate Another Doc", use_container_width=True, key="dv_reset_normal"):
                    st.session_state.pop("dv_result", None)
                    st.rerun()

    else:
        # Empty state placeholder
        st.markdown("""
        <div style='text-align:center; padding:48px 24px; background:white;
                    border-radius:16px; border:2px dashed #e5e7eb; margin-top:16px;'>
            <div style='font-size:52px; margin-bottom:12px;'>🔍</div>
            <p style='font-size:16px; font-weight:600; color:#374151; margin:0;'>
                Enter your document details above and click <strong>Validate Document</strong>
            </p>
            <p style='font-size:13px; color:#9ca3af; margin-top:8px;'>
                The system will instantly classify it and show you the required approval chain.
            </p>
            <div style='margin-top:20px; display:flex; justify-content:center; gap:24px; flex-wrap:wrap;'>
                <div style='text-align:center;'>
                    <span style='font-size:28px;'>🔴</span>
                    <p style='font-size:12px; color:#991b1b; font-weight:600; margin:4px 0 0;'>Sensitive</p>
                    <p style='font-size:11px; color:#9ca3af; margin:0;'>Full pipeline required</p>
                </div>
                <div style='text-align:center;'>
                    <span style='font-size:28px;'>✅</span>
                    <p style='font-size:12px; color:#065f46; font-weight:600; margin:4px 0 0;'>Normal</p>
                    <p style='font-size:11px; color:#9ca3af; margin:0;'>Auto-approved instantly</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


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
    st.download_button("⬇️ Download All Tickets as CSV", data=csv_bytes, file_name="helpdesk_tickets.csv", mime="text/csv", key="analytics_download_csv")


# ════════════════════════════════════════════════════════
#  PAGE: KNOWLEDGE GAP REPORT
# ════════════════════════════════════════════════════════
def page_knowledge_gap():
    if not st.session_state.get("admin_logged_in"):
        st.warning("Please log in via the Admin Panel first.")
        return

    st.markdown("# 🕳️ Knowledge Gap Report")
    st.markdown("<p style='color:#6b7280'>Questions employees asked that the system couldn't answer.</p>", unsafe_allow_html=True)
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
    st.markdown("### 📋 All Unanswered Questions")

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
    if st.button("🗑️ Clear All Failed Queries (after fixing KB)", key="gap_clear_btn"):
        try:
            db.table("failed_queries").delete().neq("id", 0).execute()
            st.toast("🗑️ All failed queries cleared from `failed_queries` table", icon="✅")
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
    if st.button("🧪 Test Database", key="setup_test_db"):
        try:
            db = get_db()
            if db is None:
                st.error("Not configured.")
            else:
                db.table("tickets").select("id").limit(1).execute()
                st.success("✅ Database connected!")
                st.toast("✅ Successfully connected to Supabase!", icon="☁️")
        except Exception as e:
            st.error(f"Failed: {e}")

    if st.button("📄 Test PDF + Q&A Extraction", key="setup_test_pdf"):
        pdf_bytes = get_pdf_bytes()
        if not pdf_bytes:
            st.error("❌ Could not download PDF.")
        else:
            st.success(f"✅ PDF downloaded ({len(pdf_bytes) // 1024} KB)")
            pairs = load_qa_pairs()
            if pairs:
                st.success(f"✅ {len(pairs)} Q&A pairs extracted!")
                st.toast(f"📄 {len(pairs)} Q&A pairs loaded from PDF into memory", icon="📚")
                with st.expander("Preview first 5 pairs"):
                    for q, a in pairs[:5]:
                        st.markdown(f"**Q:** {q[:200]}")
                        st.markdown(f"**A:** {a[:200]}")
                        st.markdown("---")
            else:
                st.error("❌ No Q&A pairs found.")

    if st.button("🧠 Test Semantic Search Model", key="setup_test_model"):
        model, q_emb, a_emb, pairs, util = load_model_and_embeddings()
        if model is None:
            st.error("❌ Model failed to load.")
        else:
            st.success("✅ Model loaded: multi-qa-mpnet-base-dot-v1")
            st.toast("🧠 Semantic model loaded into RAM cache", icon="⚡")
            st.info(f"📊 {len(pairs)} Q embeddings + {len(pairs)} A embeddings ready.")

    st.markdown("---")
    st.markdown("### 🧠 Learned Answers (from resolved tickets)")
    if st.button("📋 View All Learned Answers", key="setup_view_learned"):
        db = get_db()
        if db is None:
            st.error("Supabase not configured.")
        else:
            try:
                rows = db.table("resolved_issues").select("*").order("created_at", desc=True).execute().data or []
                if rows:
                    st.success(f"{len(rows)} learned answer(s) in database.")
                    st.toast(f"🧠 Fetched {len(rows)} learned answers from `resolved_issues` table", icon="☁️")
                    for row in rows:
                        with st.expander(f"🟢 {row['query'][:100]}"):
                            st.markdown(f"**Original question:** {row['query']}")
                            st.markdown(f"**Admin solution:** {row['solution']}")
                            st.markdown(f"<small style='color:#6b7280'>Saved: {_to_ist(row.get('created_at', ''))}</small>", unsafe_allow_html=True)
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
elif page == "📋 Approval Pipeline":
    if PIPELINE_AVAILABLE:
        page_approval_pipeline()
    else:
        st.error("❌ `approval_pipeline.py` is missing from your project folder.")
elif page == "⚙️ Setup / Config":
    page_setup()
