"""
Q&A Engine — No API required.
Fetches the PDF directly from Supabase Storage, extracts Q&A pairs,
then searches by keyword matching to answer employee questions.
"""
import re
import io
import streamlit as st
import requests

# ── PDF source: Supabase Storage (public bucket) ──────────────────────────────
PDF_URL = "https://jvulbphmksdebkkkhgvh.supabase.co/storage/v1/object/public/Documents/questions.pdf"

# ── Threshold: minimum score to return an answer ──────────────────────────────
MATCH_THRESHOLD = 10

# Words so common they add zero signal — excluded from scoring
STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "in", "on", "of", "to", "and",
    "or", "how", "why", "when", "where", "does", "do", "can", "it", "its",
    "by", "for", "with", "that", "this", "be", "as", "at", "from", "was",
    "were", "has", "have", "had", "not", "but", "if", "then", "so", "me",
    "my", "we", "you", "your", "i", "he", "she", "they", "which", "about",
    "would", "could", "should", "will", "let", "get", "got", "use", "used",
    "mean", "means", "give", "tell", "explain", "define", "describe",
}


@st.cache_resource(show_spinner="📄 Loading knowledge base…")
def load_qa_pairs() -> list:
    """
    Download PDF from Supabase Storage, extract text, parse into Q&A pairs.
    Returns empty list (NOT a fallback) if PDF cannot be loaded —
    so the app clearly shows 'no answer' instead of wrong answers from hardcoded data.
    """
    text, error = _fetch_pdf_text()

    if error:
        # Store error in session so the UI can show it prominently
        st.session_state["pdf_load_error"] = error
        return []  # ← empty, no silent fallback

    st.session_state.pop("pdf_load_error", None)
    pairs = _parse_qa(text)
    st.session_state["pdf_pair_count"] = len(pairs)
    return pairs


def _fetch_pdf_text() -> tuple:
    """
    Returns (text, None) on success or ("", error_message) on failure.
    Does NOT fall back to hardcoded data — caller decides what to do.
    """
    try:
        import PyPDF2

        resp = requests.get(PDF_URL, timeout=30)

        # Catch HTTP errors explicitly so we can show a clear message
        if resp.status_code == 403:
            return "", (
                f"🔒 **PDF access blocked (403 Forbidden).**\n\n"
                f"Your Supabase Storage bucket is not publicly accessible.\n\n"
                f"**Fix:** Go to Supabase → Storage → Documents bucket → "
                f"Edit bucket → enable **Public bucket** → save. "
                f"Then add a SELECT policy for the `anon` role."
            )
        if resp.status_code != 200:
            return "", f"❌ PDF fetch failed with HTTP {resp.status_code}."

        reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
        pages = [p.extract_text() or "" for p in reader.pages]
        full_text = "\n".join(pages)

        if not full_text.strip():
            return "", (
                "⚠️ PDF loaded but no text could be extracted. "
                "The file may be scanned/image-based. "
                "Try re-uploading a text-based PDF."
            )

        return full_text, None

    except Exception as e:
        return "", f"❌ Unexpected error loading PDF: {type(e).__name__}: {e}"


def _parse_qa(text: str) -> list:
    """
    Parse numbered Q&A pairs from the PDF text.
    Handles patterns like '1. What is Python?' followed by answer text.
    """
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
        question_lines = []
        answer_lines = []
        in_question = True

        for line in lines:
            line = line.strip()
            if not line:
                in_question = False
                continue
            if in_question and (line.endswith('?') or len(question_lines) > 2):
                question_lines.append(line)
                in_question = False
            elif in_question:
                question_lines.append(line)
            else:
                answer_lines.append(line)

        question = " ".join(question_lines).strip()
        answer = " ".join(answer_lines).strip()

        if len(question) < 5 or not answer:
            continue

        pairs.append({"num": num, "question": question, "answer": answer})

    return pairs


def _meaningful_words(text: str) -> set:
    """Extract words ≥3 chars that are NOT stop words."""
    words = set(re.findall(r'\b\w{3,}\b', text.lower()))
    return words - STOP_WORDS


def answer_question(query: str) -> dict:
    """
    Search loaded Q&A pairs for the best keyword match.
    Returns found=False immediately if no pairs are loaded (PDF failed).
    """
    qa_pairs = load_qa_pairs()

    # No pairs = PDF didn't load = don't guess, just return not found
    if not qa_pairs:
        return {"found": False, "answer": "", "matched_question": "", "score": 0}

    query_lower = query.lower()
    query_words = _meaningful_words(query_lower)

    if not query_words:
        return {"found": False, "answer": "", "matched_question": "", "score": 0}

    tech_terms = {
        'list', 'tuple', 'dict', 'dictionary', 'set', 'function', 'class',
        'object', 'lambda', 'decorator', 'generator', 'iterator', 'exception',
        'module', 'package', 'inheritance', 'polymorphism', 'encapsulation',
        'abstraction', 'gil', 'pep8', 'comprehension', 'thread', 'process',
        'async', 'python', 'variable', 'scope', 'namespace', 'mutable',
        'immutable', 'argument', 'parameter', 'return', 'import', 'loop',
        'recursion', 'stack', 'heap', 'memory', 'garbage', 'collection',
        'type', 'string', 'integer', 'boolean', 'float', 'array', 'index',
        'slice', 'map', 'filter', 'zip', 'enumerate', 'format', 'file',
        'context', 'manager', 'yield', 'await', 'coroutine',
    }

    best_score = 0
    best_match = None

    for pair in qa_pairs:
        q_lower = pair["question"].lower()
        a_lower = pair["answer"].lower()
        score = 0

        if query_lower in q_lower:
            score += 15

        q_words = _meaningful_words(q_lower)
        a_words = _meaningful_words(a_lower)

        q_overlap = query_words & q_words
        a_overlap = query_words & a_words

        score += len(q_overlap) * 5
        score += len(a_overlap) * 2

        tech_overlap = (query_words & tech_terms) & q_words
        score += len(tech_overlap) * 8

        if q_overlap and len(q_overlap) / max(len(query_words), 1) < 0.3 and score < 15:
            score = 0

        if score > best_score:
            best_score = score
            best_match = pair

    if best_match and best_score >= MATCH_THRESHOLD:
        return {
            "found": True,
            "answer": best_match["answer"],
            "matched_question": best_match["question"],
            "score": best_score,
        }

    return {"found": False, "answer": "", "matched_question": "", "score": 0}


def get_all_questions() -> list:
    return [p["question"] for p in load_qa_pairs()]
