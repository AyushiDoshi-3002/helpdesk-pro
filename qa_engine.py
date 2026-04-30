"""
Q&A Engine — Semantic similarity using sentence-transformers.
Based on the working model that used all-MiniLM-L6-v2 + cosine similarity.

Install:  pip install sentence-transformers pdfplumber requests
"""
import re
import io
import os
import requests
import streamlit as st

# ── PDF source: Supabase Storage ──────────────────────────────────────────────
PDF_URL = "https://jvulbphmksdebkkkhgvh.supabase.co/storage/v1/object/public/Documents/questions.pdf"

# ── Similarity threshold (from your working model: 0.4) ──────────────────────
SIMILARITY_THRESHOLD = 0.4


# ── Load model + PDF (cached so it only runs once per app session) ────────────

@st.cache_resource(show_spinner="🤖 Loading AI model…")
def _load_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


@st.cache_resource(show_spinner="📄 Loading knowledge base from Supabase…")
def load_qa_pairs() -> list:
    """
    Fetch PDF → extract Q&A pairs → encode questions into embeddings.
    Returns list of dicts: {question, answer, embedding}
    """
    text, error = _fetch_pdf_text()

    if error:
        st.session_state["pdf_load_error"] = error
        return []

    st.session_state.pop("pdf_load_error", None)

    # Try your PDF's format first (q. / answer), fall back to numbered format
    pairs = _parse_qa_qformat(text)
    if len(pairs) < 3:
        pairs = _parse_qa_numbered(text)

    if not pairs:
        st.session_state["pdf_load_error"] = (
            "⚠️ PDF loaded but no Q&A pairs could be parsed. "
            "Check the PDF format."
        )
        return []

    # Encode all questions into embeddings
    model = _load_model()
    questions = [p["question"] for p in pairs]
    embeddings = model.encode(questions, convert_to_tensor=True)

    for i, pair in enumerate(pairs):
        pair["embedding"] = embeddings[i]

    st.session_state["pdf_pair_count"] = len(pairs)
    return pairs


# ── PDF fetching ──────────────────────────────────────────────────────────────

def _fetch_pdf_text() -> tuple:
    """Returns (text, None) on success or ('', error_message) on failure."""
    try:
        import pdfplumber

        resp = requests.get(PDF_URL, timeout=30)

        if resp.status_code == 403:
            return "", (
                "🔒 **PDF access blocked (403).** "
                "Go to Supabase → Storage → Documents → Edit bucket → enable **Public bucket**. "
                "Also add a SELECT policy for the `anon` role."
            )
        if resp.status_code != 200:
            return "", f"❌ PDF fetch failed: HTTP {resp.status_code}"

        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]

        full_text = "\n".join(pages).lower()

        if not full_text.strip():
            return "", "⚠️ PDF loaded but no text extracted — may be image-based."

        return full_text, None

    except Exception as e:
        return "", f"❌ Error loading PDF: {type(e).__name__}: {e}"


# ── Q&A parsers ───────────────────────────────────────────────────────────────

def _parse_qa_qformat(text: str) -> list:
    """
    Parser from your working model.
    Splits on 'q.' and then on 'answer'.
    Matches PDFs formatted like:  Q. What is Python?  Answer: ...
    """
    pairs = []
    parts = re.split(r'q\.', text)

    for part in parts:
        if "answer" not in part:
            continue
        try:
            q_part, a_part = part.split("answer", 1)
            question = q_part.strip()
            answer = a_part.strip()

            # Skip enrollment/course noise (from your working model)
            if "enroll" in answer or "course" in answer:
                continue
            if len(answer) < 30 or len(question) < 5:
                continue

            pairs.append({"question": question, "answer": answer})
        except Exception:
            continue

    return pairs


def _parse_qa_numbered(text: str) -> list:
    """
    Fallback parser for numbered PDFs like:
    1. What is Python?
    Python is a high-level language...
    """
    parts = re.split(r'\n\s*(\d{1,3})\.\s+', text)
    pairs = []
    i = 1
    while i < len(parts) - 1:
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        i += 2
        if not content:
            continue

        lines = content.split('\n')
        question_lines, answer_lines = [], []
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

        if len(question) < 5 or len(answer) < 30:
            continue

        pairs.append({"question": question, "answer": answer})

    return pairs


# ── Main answer function ──────────────────────────────────────────────────────

def answer_question(query: str) -> dict:
    """
    Semantic similarity search — same approach as your working model.
    Uses cosine similarity between query embedding and all question embeddings.
    Threshold: 0.4 (from your working model).
    """
    from sentence_transformers import util

    qa_pairs = load_qa_pairs()

    if not qa_pairs:
        return {"found": False, "answer": "", "matched_question": "", "score": 0.0}

    model = _load_model()
    query_embedding = model.encode(query, convert_to_tensor=True)

    import torch
    all_embeddings = torch.stack([p["embedding"] for p in qa_pairs])
    scores = util.cos_sim(query_embedding, all_embeddings)[0]

    best_idx = int(scores.argmax())
    best_score = float(scores[best_idx])

    if best_score >= SIMILARITY_THRESHOLD:
        return {
            "found": True,
            "answer": qa_pairs[best_idx]["answer"],
            "matched_question": qa_pairs[best_idx]["question"],
            "score": round(best_score, 2),
        }

    return {"found": False, "answer": "", "matched_question": "", "score": round(best_score, 2)}


def get_all_questions() -> list:
    return [p["question"] for p in load_qa_pairs()]
