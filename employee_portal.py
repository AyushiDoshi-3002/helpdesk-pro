"""
employee_portal.py  –  3-Tab Employee Portal
Tab 1 : Knowledge Base Q&A + Support Ticket
Tab 2 : Ticket Hub  →  (a) Incident Ticket  |  (b) Document Approval Ticket
Tab 3 : My Tickets  –  employee can check status of their own tickets
"""

import streamlit as st
import re
import io
import requests
from datetime import datetime, timezone, timedelta

# ── IST helper ────────────────────────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS FROM YOUR EXISTING MODULES
#  (copy-paste safe: each import is guarded so the file still runs if a module
#   is temporarily absent during development)
# ══════════════════════════════════════════════════════════════════════════════

# ── Supabase DB helpers (from app.py / db.py) ────────────────────────────────
try:
    from supabase import create_client
    SUPABASE_OK = True
except ImportError:
    SUPABASE_OK = False

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
    row = {
        "user_id":  user_id,
        "job_role": job_role,
        "query":    query,
        "priority": priority,
        "status":   "Open",
    }
    result = db.table("tickets").insert(row).execute()
    if result.data:
        ticket = result.data[0]
        st.toast(f"🎫 Ticket #{ticket.get('id')} saved to Supabase!", icon="☁️")
        return ticket
    raise Exception("No data returned from insert")

def db_get_tickets(user_id_filter=None, status_filter=None):
    db = get_db()
    if db is None:
        return []
    try:
        q = db.table("tickets").select("*").order("created_at", desc=True)
        if status_filter and status_filter != "All":
            q = q.eq("status", status_filter)
        if user_id_filter:
            q = q.eq("user_id", user_id_filter)
        return q.execute().data or []
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return []

def db_log_failed_query(query: str):
    db = get_db()
    if db:
        try:
            db.table("failed_queries").insert({"query": query}).execute()
            st.toast("📋 Logged to failed_queries in Supabase", icon="☁️")
        except Exception:
            pass

def check_learned_answers(query: str):
    """Keyword-similarity lookup across resolved_issues + resolved tickets."""
    db = get_db()
    if db is None:
        return None

    _STOP = {
        "what","is","are","the","a","an","of","in","on","at","to","for","and",
        "or","how","why","when","where","who","does","do","can","could","would",
        "should","explain","tell","me","about","difference","between","use",
        "using","means","mean","define","definition","describe","give",
    }

    def _norm(t):
        return re.sub(r'[^\w\s]', '', t.lower()).strip()

    def _words(t):
        return {w for w in re.findall(r'\b[a-z]{2,}\b', t.lower()) if w not in _STOP}

    def _score(q, stored):
        qn, sn = _norm(q), _norm(stored)
        if qn == sn:
            return 1.0
        if qn in sn or sn in qn:
            return 0.85
        qw, sw = _words(q), _words(stored)
        if not qw or not sw:
            return 0.0
        inter = qw & sw
        shorter = qw if len(qw) <= len(sw) else sw
        if inter == shorter and len(shorter) >= 1:
            return 0.80
        j = len(inter) / len(qw | sw)
        return max(j, 0.35) if inter else 0.0

    THRESHOLD = 0.30
    best_score, best_sol, best_match = 0.0, None, None

    try:
        rows = (db.table("tickets")
                  .select("query, admin_note")
                  .not_.is_("admin_note", "null")
                  .execute().data or [])
        for r in rows:
            note = (r.get("admin_note") or "").strip()
            q    = (r.get("query")      or "").strip()
            if not note or not q:
                continue
            s = _score(query, q)
            if s > best_score:
                best_score, best_sol, best_match = s, note, q
    except Exception:
        pass

    try:
        rows2 = db.table("resolved_issues").select("query, solution").execute().data or []
        for r in rows2:
            sol = (r.get("solution") or "").strip()
            q   = (r.get("query")   or "").strip()
            if not sol or not q:
                continue
            s = _score(query, q)
            if s > best_score:
                best_score, best_sol, best_match = s, sol, q
    except Exception:
        pass

    if best_sol and best_score >= THRESHOLD:
        return {"solution": best_sol, "matched_query": best_match,
                "score": best_score, "source": "learned"}
    return None


# ── PDF + Semantic Search (same as app.py) ────────────────────────────────────
_PDF_URL = "https://jvulbphmksdebkkkhgvh.supabase.co/storage/v1/object/public/Documents/questions.pdf"

_Q_THRESHOLD   = 0.60
_A_THRESHOLD   = 0.65
_ANSWER_WEIGHT = 0.85

@st.cache_resource(show_spinner="📄 Downloading PDF…")
def _get_pdf_bytes(_v=3):
    try:
        key  = st.secrets.get("SUPABASE_KEY", "")
        hdrs = {"apikey": key, "Authorization": f"Bearer {key}"}
        r    = requests.get(_PDF_URL, headers=hdrs, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        st.warning(f"PDF download failed: {e}")
        return None

@st.cache_resource(show_spinner="📄 Extracting Q&A…")
def load_qa_pairs():
    pdf = _get_pdf_bytes()
    if not pdf:
        return []
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(pdf)) as p:
            for pg in p.pages:
                t = pg.extract_text()
                if t:
                    text += t + "\n"
    except Exception as e:
        st.warning(f"pdfplumber error: {e}")
        return []
    text = text.lower()
    pairs = []
    for part in re.split(r'q\.', text):
        if "answer" not in part:
            continue
        try:
            q_part, a_part = part.split("answer", 1)
            q, a = q_part.strip(), a_part.strip()
            if "enroll" in a or "course" in a:
                continue
            if len(a) < 30 or len(q) < 5:
                continue
            pairs.append((q, a))
        except Exception:
            continue
    return pairs

@st.cache_resource(show_spinner="🧠 Loading semantic model…")
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer, util
        pairs = load_qa_pairs()
        if not pairs:
            return None, None, None, None, None
        model  = SentenceTransformer('multi-qa-mpnet-base-dot-v1')
        qs     = [q for q, _ in pairs]
        ans    = [a for _, a in pairs]
        q_emb  = model.encode(qs,  convert_to_tensor=True, show_progress_bar=False)
        a_emb  = model.encode(ans, convert_to_tensor=True, show_progress_bar=False)
        return model, q_emb, a_emb, pairs, util
    except Exception as e:
        st.warning(f"Model error: {e}")
        return None, None, None, None, None

def answer_question(query: str) -> dict:
    model, q_emb, a_emb, pairs, util = _load_model()
    if model is not None:
        try:
            qe      = model.encode(query.lower(), convert_to_tensor=True)
            q_sc    = util.cos_sim(qe, q_emb)[0]
            bqi     = int(q_sc.argmax());  bqs = float(q_sc[bqi])
            a_sc    = util.cos_sim(qe, a_emb)[0]
            bai     = int(a_sc.argmax());  bas = float(a_sc[bai])
            wa      = bas * _ANSWER_WEIGHT
            if bqs >= _Q_THRESHOLD or bas >= _A_THRESHOLD:
                idx   = bqi if bqs >= wa else bai
                score = bqs if bqs >= wa else bas
                src   = "question" if bqs >= wa else "answer"
                q, a  = pairs[idx]
                return {"found": True, "answer": a.strip(), "matched": q.strip(),
                        "score": score, "match_src": src,
                        "pdf_error": False, "source": "pdf"}
        except Exception:
            pass

    learned = check_learned_answers(query)
    if learned:
        return {"found": True, "answer": learned["solution"],
                "matched": learned["matched_query"],
                "score": learned["score"], "match_src": "learned",
                "pdf_error": False, "source": "learned"}

    return {"found": False, "answer": "", "matched": "", "score": 0,
            "match_src": "none", "pdf_error": model is None, "source": "none"}


# ── Approval Pipeline helpers (from approval_pipeline.py) ────────────────────
try:
    from approval_pipeline import (
        DOC_CATEGORIES, _build_chain, _create as _ap_create,
        _escalation_label, _fmt as _ap_fmt,
        _get_sb as _ap_get_sb, TABLE as AP_TABLE,
        _now as _ap_now,
    )
    PIPELINE_OK = True
except ImportError:
    PIPELINE_OK = False

# ── Ticket-intent detector ─────────────────────────────────────────────────────
_TICKET_PHRASES = [
    "raise a ticket","raise ticket","raise a query","raise query",
    "raise an issue","raise issue","submit a ticket","submit ticket",
    "create a ticket","create ticket","open a ticket","log a ticket",
    "report an issue","report a problem","report a bug",
    "need help ticket","contact support","get support","escalate",
]

def _is_ticket_intent(text: str) -> bool:
    lower = text.lower().strip()
    return any(p in lower for p in _TICKET_PHRASES)


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED CSS
# ══════════════════════════════════════════════════════════════════════════════
_CSS = """
<style>
.ep-answer-box {
    background: #faf7f2;
    border-left: 3px solid #8b3a2a;
    border-radius: 3px;
    padding: 22px 26px;
    font-size: 22px;
    line-height: 1.85;
    color: #3d3530;
    margin: 10px 0;
    box-shadow: 0 1px 6px rgba(26,22,18,.07);
}
.ep-learned-box {
    background: #faf7f2;
    border-left: 3px solid #3d5a4a;
    border-radius: 3px;
    padding: 22px 26px;
    font-size: 22px;
    line-height: 1.85;
    color: #3d3530;
    margin: 10px 0;
}
.ep-no-ans {
    background: #f0e0db;
    border-left: 3px solid #c4543a;
    border-radius: 3px;
    padding: 16px 20px;
    color: #8b3a2a;
    font-size: 21px;
    margin: 10px 0;
}
.ep-section-label {
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    color: #9c8e82;
    letter-spacing: .10em;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.ep-ticket-card {
    background: #faf7f2;
    border: 1px solid #d4c9bc;
    border-left: 3px solid #8b3a2a;
    border-radius: 3px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.ep-ticket-card.open   { border-left-color: #8b6914; }
.ep-ticket-card.prog   { border-left-color: #2d3d4f; }
.ep-ticket-card.res    { border-left-color: #3d5a4a; }
.ep-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 2px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: .08em;
    text-transform: uppercase;
    font-family: 'DM Mono', monospace;
}
.badge-open   { background: #f0e2b0; color: #8b6914; border: 1px solid #d4b830; }
.badge-prog   { background: #c8d8e8; color: #2d3d4f; border: 1px solid #8ab0cc; }
.badge-res    { background: #d4e8dc; color: #3d5a4a; border: 1px solid #7ab898; }
.ep-type-card {
    background: #faf7f2;
    border: 1.5px solid #d4c9bc;
    border-radius: 6px;
    padding: 28px 24px;
    text-align: center;
    cursor: pointer;
    transition: border-color .18s, box-shadow .18s;
}
.ep-type-card:hover { border-color: #8b3a2a; box-shadow: 0 2px 12px rgba(139,58,42,.12); }
.ep-type-card.selected { border-color: #8b3a2a; background: #fdf5f3; }
.ep-type-icon { font-size: 38px; margin-bottom: 10px; }
.ep-type-title { font-family: 'Playfair Display', serif; font-size: 20px; font-weight: 700; color: #1a1612; }
.ep-type-desc  { font-size: 15px; color: #6b5f55; margin-top: 6px; line-height: 1.5; }
.ep-info-banner {
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-left: 3px solid #f59e0b;
    border-radius: 3px;
    padding: 14px 18px;
    font-size: 20px;
    color: #92400e;
    margin: 10px 0;
}
.ep-route-badge {
    display: inline-block;
    background: #eff6ff;
    border: 1px solid #93c5fd;
    color: #1d4ed8;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    padding: 3px 12px;
    margin: 3px 2px;
}
.ep-chain-box {
    background: #fffbeb;
    border: 1.5px solid #fcd34d;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 10px 0;
    font-size: 14px;
    color: #92400e;
}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════════
#  REUSABLE: KB SEARCH + ANSWER DISPLAY
# ══════════════════════════════════════════════════════════════════════════════
def _render_kb_result(question: str, ctx_key: str):
    """
    Runs KB search for `question`, renders result.
    Returns  'found' | 'not_found' | 'ticket_intent'
    so the caller can decide what to show next.
    """
    if _is_ticket_intent(question):
        st.markdown(
            "<div class='ep-info-banner'>"
            "Sure — fill in the support ticket form below.</div>",
            unsafe_allow_html=True,
        )
        return "ticket_intent"

    with st.spinner("Searching knowledge base…"):
        result = answer_question(question)

    if result.get("pdf_error") and not result["found"]:
        st.error("Knowledge base unavailable. Please raise a support ticket.")
        db_log_failed_query(question)
        return "not_found"

    if result["found"]:
        src  = result.get("source", "pdf")
        msrc = result.get("match_src", "question")

        if src == "learned":
            st.markdown("#### ✦ Answer Found")
            st.markdown(
                f"<p class='ep-section-label'>Source: Previously resolved ticket &nbsp;·&nbsp; "
                f"similarity {result['score']:.0%}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='ep-learned-box'>{result['answer']}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("#### ✦ Answer Found")
            mlabel = "matched via question" if msrc == "question" else "matched via answer content"
            st.markdown(
                f"<p class='ep-section-label'>Source: PDF Knowledge Base &nbsp;·&nbsp; "
                f"{mlabel} &nbsp;·&nbsp; score {result['score']:.2f}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<small style='color:#9c8e82;font-size:18px;'>"
                f"Matched: <em>{result['matched'][:120]}</em></small>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='ep-answer-box'>{result['answer']}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        c1, c2, _ = st.columns([1, 1, 4])
        with c1:
            if st.button("👍 Helpful", key=f"helpful_{ctx_key}"):
                st.success("Glad it helped!")
        with c2:
            if st.button("👎 Not helpful", key=f"nothelpful_{ctx_key}"):
                db_log_failed_query(question)
                return "not_found"
        return "found"

    else:
        st.markdown(
            "<div class='ep-no-ans'>No answer found in the knowledge base. "
            "Please raise a support ticket below.</div>",
            unsafe_allow_html=True,
        )
        db_log_failed_query(question)
        return "not_found"


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — KNOWLEDGE BASE Q&A + SUPPORT TICKET
#  (your original employee portal, untouched)
# ══════════════════════════════════════════════════════════════════════════════
def _tab_kb_qa():
    st.markdown("### 💬 Ask a Question")
    st.markdown(
        "<p style='color:#6b5f55;font-size:21px;'>"
        "Ask anything — or type <em>raise a ticket</em> to go straight to support.</p>",
        unsafe_allow_html=True,
    )

    pairs = load_qa_pairs()
    if len(pairs) == 0:
        st.error("⚠️ PDF knowledge base could not be loaded.")
    else:
        st.success(f"📚 Knowledge Base ready — {len(pairs)} Q&A pairs indexed")

    st.markdown("---")
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input(
            "",
            placeholder="e.g. What is the difference between a list and a tuple?",
            label_visibility="collapsed",
            key="tab1_question",
        )
    with col2:
        search = st.button("Search →", use_container_width=True, key="tab1_search")

    if search and question.strip():
        status = _render_kb_result(question.strip(), ctx_key="tab1")
        if status in ("not_found", "ticket_intent"):
            st.session_state["tab1_show_ticket"]   = True
            st.session_state["tab1_ticket_query"]  = question.strip() if status == "not_found" else ""
    elif search:
        st.warning("Please enter a question.")

    st.markdown("---")

    if st.session_state.get("tab1_show_ticket", False):
        st.markdown("### 🎫 Raise a Support Ticket")
        _render_support_ticket_form(
            prefill_query = st.session_state.get("tab1_ticket_query", ""),
            ctx           = "tab1_ticket",
            on_cancel_key = "tab1_show_ticket",
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SUPPORT TICKET FORM  (reused in Tab 1 + Tab 2 Incident flow)
# ══════════════════════════════════════════════════════════════════════════════
def _render_support_ticket_form(prefill_query: str, ctx: str, on_cancel_key: str):
    c1, c2 = st.columns(2)
    with c1:
        user_id  = st.text_input("Employee ID *", placeholder="e.g. EMP-1042", key=f"{ctx}_uid")
        job_role = st.selectbox(
            "Job Role *",
            ["Select…","Software Engineer","Data Analyst","QA Engineer",
             "DevOps Engineer","Product Manager","HR / Operations","Other"],
            key=f"{ctx}_role",
        )
    with c2:
        priority = st.selectbox("Priority *", ["Medium","High","Low"], key=f"{ctx}_prio")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<small style='color:#9c8e82;font-size:17px;'>Tickets usually resolved within 24 h.</small>",
            unsafe_allow_html=True,
        )

    if prefill_query:
        st.markdown(
            f"<small style='color:#8b3a2a;font-size:17px;'>Search query: {prefill_query}</small>",
            unsafe_allow_html=True,
        )

    query_text = st.text_area(
        "Describe your problem in detail *",
        value="",
        placeholder="Add more details about the issue…",
        height=120,
        key=f"{ctx}_qtext",
    )

    col_sub, col_cancel, _ = st.columns([1, 1, 4])
    with col_sub:
        if st.button("Submit Ticket →", use_container_width=True, key=f"{ctx}_submit"):
            errors = []
            if not user_id.strip():        errors.append("Employee ID required.")
            if job_role == "Select…":      errors.append("Select your job role.")
            final_q = prefill_query or query_text.strip()
            if not final_q:                errors.append("Problem description required.")
            for e in errors:
                st.error(e)
            if not errors:
                try:
                    t = db_create_ticket(user_id.strip(), job_role, final_q, priority)
                    st.success(f"✅ Ticket #{t.get('id','–')} submitted! Our team will respond shortly.")
                    st.session_state[on_cancel_key]  = False
                    st.session_state[f"{ctx}_uid"]   = ""
                    st.session_state[f"{ctx}_qtext"] = ""
                    st.toast(f"🎉 Ticket #{t.get('id')} created!", icon="✅")
                except Exception as ex:
                    st.error(f"Failed: {ex}")
    with col_cancel:
        if st.button("Cancel", use_container_width=True, key=f"{ctx}_cancel"):
            st.session_state[on_cancel_key] = False
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — TICKET HUB  (Incident  |  Doc Approval)
# ══════════════════════════════════════════════════════════════════════════════
def _tab_ticket_hub():
    st.markdown("### 🎫 Ticket Hub")
    st.markdown(
        "<p style='color:#6b5f55;font-size:21px;'>"
        "Choose the type of ticket you want to raise.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Ticket-type selector ─────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        selected_a = st.session_state.get("hub_type") == "incident"
        if st.button(
            "🚨  Incident Ticket\n\nReport a problem, bug, or technical issue. "
            "We'll search the KB first — if no answer, a support ticket is raised automatically.",
            key="hub_btn_incident",
            use_container_width=True,
        ):
            st.session_state["hub_type"]             = "incident"
            st.session_state["hub_inc_show_form"]    = False
            st.session_state["hub_inc_kb_status"]    = None
            st.session_state["hub_doc_show_form"]    = False

    with col_b:
        if st.button(
            "📄  Document Approval Ticket\n\nRequest creation / approval of a document. "
            "Fill in the details and it will be routed through the correct approval pipeline.",
            key="hub_btn_doc",
            use_container_width=True,
        ):
            st.session_state["hub_type"]             = "doc"
            st.session_state["hub_inc_show_form"]    = False
            st.session_state["hub_inc_kb_status"]    = None
            st.session_state["hub_doc_show_form"]    = False

    st.markdown("---")

    hub_type = st.session_state.get("hub_type")

    # ── INCIDENT TICKET flow ─────────────────────────────────────────────────
    if hub_type == "incident":
        _hub_incident_flow()

    # ── DOC APPROVAL TICKET flow ─────────────────────────────────────────────
    elif hub_type == "doc":
        _hub_doc_approval_flow()

    else:
        st.markdown(
            "<div class='ep-info-banner'>"
            "👆 Select a ticket type above to get started.</div>",
            unsafe_allow_html=True,
        )


# ── INCIDENT flow ─────────────────────────────────────────────────────────────
def _hub_incident_flow():
    st.markdown("#### 🚨 Incident Ticket")
    st.markdown(
        "<p style='color:#6b5f55;font-size:20px;'>"
        "Describe your issue. We'll search the knowledge base first — "
        "if no answer is found, a support ticket will be raised.</p>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([4, 1])
    with c1:
        question = st.text_input(
            "",
            placeholder="Describe the issue or ask a question…",
            label_visibility="collapsed",
            key="hub_inc_question",
        )
    with c2:
        search = st.button("Search →", use_container_width=True, key="hub_inc_search")

    if search and question.strip():
        status = _render_kb_result(question.strip(), ctx_key="hub_inc")
        st.session_state["hub_inc_kb_status"]   = status
        st.session_state["hub_inc_query_cache"] = question.strip()
        if status in ("not_found", "ticket_intent"):
            st.session_state["hub_inc_show_form"] = True
    elif search:
        st.warning("Please describe your issue.")

    if st.session_state.get("hub_inc_show_form", False):
        st.markdown("---")
        st.markdown("##### 📋 Support Ticket Details")
        _render_support_ticket_form(
            prefill_query = (
                st.session_state.get("hub_inc_query_cache", "")
                if st.session_state.get("hub_inc_kb_status") == "not_found"
                else ""
            ),
            ctx           = "hub_inc_ticket",
            on_cancel_key = "hub_inc_show_form",
        )


# ── DOC APPROVAL flow ─────────────────────────────────────────────────────────
def _hub_doc_approval_flow():
    st.markdown("#### 📄 Document Approval Ticket")

    if not PIPELINE_OK:
        st.error(
            "⚠️ `approval_pipeline.py` is not found in your project folder. "
            "Please add it to enable document approval routing."
        )
        return

    st.markdown(
        "<p style='color:#6b5f55;font-size:20px;'>"
        "Fill in the details below. The system will classify your document, "
        "determine the approval chain, and submit it to the pipeline.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Step 1: Employee identity ─────────────────────────────────────────────
    st.markdown("##### 👤 Your Details")
    d1, d2 = st.columns(2)
    with d1:
        emp_id   = st.text_input("Employee ID *", placeholder="e.g. EMP-1042", key="doc_emp_id")
    with d2:
        emp_name = st.text_input("Your Name *",   placeholder="e.g. Priya K.",  key="doc_emp_name")

    st.markdown("---")

    # ── Step 2: Document details ──────────────────────────────────────────────
    st.markdown("##### 📄 Document Details")

    cat_keys  = list(DOC_CATEGORIES.keys())
    d3, d4    = st.columns(2)
    with d3:
        doc_title = st.text_input(
            "Document Title *",
            placeholder="e.g. Database Backup Procedure",
            key="doc_title",
        )
        doc_cat = st.selectbox(
            "Document Category *",
            cat_keys,
            format_func=lambda c: DOC_CATEGORIES[c]["label"],
            key="doc_cat",
        )
    with d4:
        avail_sub = DOC_CATEGORIES[st.session_state.get("doc_cat", cat_keys[0])]["subtypes"]
        doc_sub   = st.selectbox("Document Subtype *", avail_sub, key="doc_sub")
        urg_opts  = ["Normal", "URGENT", "CRITICAL"]
        doc_urg   = st.selectbox("Urgency *", urg_opts, key="doc_urg")

    doc_desc = st.text_area(
        "What does this document need to cover? *",
        placeholder="Describe the purpose, scope, and intended audience of the document…",
        height=100,
        key="doc_desc",
    )

    # ── Live approval-chain preview ───────────────────────────────────────────
    chosen_cat = st.session_state.get("doc_cat", cat_keys[0])
    cfg        = DOC_CATEGORIES[chosen_cat]
    chain      = _build_chain(chosen_cat)

    if cfg["auto"]:
        route_str = "✅ Auto-approved instantly — no approvers required"
    else:
        route_str = " → ".join(chain) + f"  ·  {_escalation_label()} per level"

    st.markdown(
        f"<div class='ep-chain-box'>"
        f"<strong>Approval Route:</strong> &nbsp;"
        f"{''.join(f'<span class=ep-route-badge>{r}</span>' for r in chain) if chain else '<span class=ep-route-badge>Auto-approved</span>'}"
        f"<br><small style='font-size:13px;'>Each approver has <strong>{_escalation_label()}</strong> to respond — "
        f"no response escalates to the next level.</small>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Submit ────────────────────────────────────────────────────────────────
    if st.button("🚀 Submit for Approval", use_container_width=False, type="primary", key="doc_submit"):
        errors = []
        if not emp_id.strip():   errors.append("Employee ID is required.")
        if not emp_name.strip(): errors.append("Your name is required.")
        if not doc_title.strip():errors.append("Document title is required.")
        if not doc_desc.strip(): errors.append("Document description is required.")

        for e in errors:
            st.error(e)

        if not errors:
            requester_str = f"{emp_name.strip()} · {emp_id.strip()}"
            try:
                req = _ap_create(
                    title       = doc_title.strip(),
                    category    = chosen_cat,
                    subtype     = st.session_state.get("doc_sub", avail_sub[0]),
                    description = doc_desc.strip(),
                    urgency     = doc_urg,
                    requester   = requester_str,
                )
                if req["done"]:
                    st.success(
                        f"✅ **{req['id']}** — '{doc_title}' auto-approved instantly! "
                        f"No further action required."
                    )
                else:
                    ch = req["chain"]
                    st.success(
                        f"✅ **{req['id']}** submitted — routed to **{ch[0]}**. "
                        f"Full chain: **{' → '.join(ch)}**. "
                        f"Each approver has **{_escalation_label()}** to respond."
                    )
                    st.markdown(
                        f"<div class='ep-chain-box'>"
                        f"<strong>📋 Request ID:</strong> {req['id']}<br>"
                        f"<strong>📄 Title:</strong> {req['title']}<br>"
                        f"<strong>🗂 Category:</strong> {req['category']} › {req['subtype']}<br>"
                        f"<strong>⚡ Urgency:</strong> {req['urgency']}<br>"
                        f"<strong>⏰ First deadline:</strong> {_ap_fmt(req['expires_at'])}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.info(
                        "You can track approval progress in the **📋 Approval Pipeline** page "
                        "from the sidebar.",
                        icon="ℹ️",
                    )

                # reset form fields
                for k in ["doc_emp_id","doc_emp_name","doc_title","doc_desc"]:
                    st.session_state.pop(k, None)

            except Exception as ex:
                st.error(f"Submission failed: {ex}")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — MY TICKETS  (employee checks their own ticket status)
# ══════════════════════════════════════════════════════════════════════════════
def _tab_my_tickets():
    st.markdown("### 📋 My Tickets")
    st.markdown(
        "<p style='color:#6b5f55;font-size:21px;'>"
        "Enter your Employee ID to view all tickets you have raised.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        my_id = st.text_input(
            "Employee ID",
            placeholder="e.g. EMP-1042",
            key="my_tickets_id",
        )
    with c2:
        sf = st.selectbox("Filter", ["All","Open","In Progress","Resolved"], key="my_tickets_filter")
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔎 Fetch Tickets", use_container_width=True, key="my_tickets_fetch")

    if fetch_btn:
        if not my_id.strip():
            st.warning("Please enter your Employee ID.")
        else:
            tickets = db_get_tickets(
                user_id_filter = my_id.strip(),
                status_filter  = sf if sf != "All" else None,
            )
            st.session_state["my_tickets_data"] = tickets
            st.session_state["my_tickets_uid"]  = my_id.strip()

    tickets = st.session_state.get("my_tickets_data")

    if tickets is None:
        return

    uid = st.session_state.get("my_tickets_uid", "")

    if not tickets:
        st.info(f"No tickets found for **{uid}**.", icon="📭")
        return

    # ── Summary row ───────────────────────────────────────────────────────────
    open_c = sum(1 for t in tickets if t["status"] == "Open")
    prog_c = sum(1 for t in tickets if t["status"] == "In Progress")
    res_c  = sum(1 for t in tickets if t["status"] == "Resolved")

    m1, m2, m3, m4 = st.columns(4)
    def _mcard(col, val, label):
        with col:
            st.markdown(
                f"<div style='background:#faf7f2;border:1px solid #d4c9bc;border-radius:3px;"
                f"padding:14px 18px;text-align:center;'>"
                f"<div style='font-family:Playfair Display,serif;font-size:38px;font-weight:700;"
                f"color:#1a1612;'>{val}</div>"
                f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#9c8e82;"
                f"letter-spacing:.08em;text-transform:uppercase;'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    _mcard(m1, len(tickets), "Total")
    _mcard(m2, open_c,       "Open")
    _mcard(m3, prog_c,       "In Progress")
    _mcard(m4, res_c,        "Resolved")

    st.markdown("---")

    # ── Ticket cards ──────────────────────────────────────────────────────────
    for t in tickets:
        tid     = t.get("id")
        status  = t.get("status", "Open")
        prio    = t.get("priority", "Medium")
        created = _to_ist(t.get("created_at", ""))
        query   = t.get("query", "")
        note    = t.get("admin_note") or ""

        status_cls   = {"Open":"open","In Progress":"prog","Resolved":"res"}.get(status,"open")
        badge_cls    = {"Open":"badge-open","In Progress":"badge-prog","Resolved":"badge-res"}.get(status,"badge-open")
        prio_colors  = {"High":"#8b3a2a","Medium":"#8b6914","Low":"#3d5a4a"}
        prio_color   = prio_colors.get(prio, "#6b5f55")

        with st.expander(
            f"#{tid}  ·  {status}  ·  {prio} priority  ·  {created}",
            expanded=False,
        ):
            st.markdown(
                f"<span class='ep-badge {badge_cls}'>{status}</span>"
                f"&nbsp;&nbsp;<span style='color:{prio_color};font-family:DM Mono,monospace;"
                f"font-size:13px;font-weight:600;text-transform:uppercase;"
                f"letter-spacing:.08em;'>{prio}</span>",
                unsafe_allow_html=True,
            )

            st.markdown(f"**Submitted:** {created}")
            st.markdown(f"**Job Role:** {t.get('job_role','–')}")

            st.markdown("**Your Query:**")
            st.markdown(
                f"<div class='ep-answer-box' style='font-size:20px;'>{query}</div>",
                unsafe_allow_html=True,
            )

            if note:
                st.markdown("**Admin Response / Solution:**")
                st.markdown(
                    f"<div class='ep-learned-box' style='font-size:20px;'>{note}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div class='ep-no-ans' style='font-size:18px;'>"
                    "⏳ No admin response yet. Our team is working on it.</div>",
                    unsafe_allow_html=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def show():
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("# 🔍 Employee Support Portal")
    st.markdown(
        "<p style='color:#6b5f55;font-size:22px;margin-top:-8px;'>"
        "Ask questions, raise tickets, and track your support requests.</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs([
        "💬 Knowledge Base & Q&A",
        "🎫 Raise a Ticket",
        "📋 My Tickets",
    ])

    with tab1:
        _tab_kb_qa()

    with tab2:
        _tab_ticket_hub()

    with tab3:
        _tab_my_tickets()
