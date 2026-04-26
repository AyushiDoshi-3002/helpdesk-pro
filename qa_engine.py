"""
Q&A Engine — No API required.
Downloads the Python Interview PDF once, extracts Q&A pairs,
then searches by keyword matching to answer employee questions.
"""
import re
import io
import streamlit as st
import requests

# Google Drive direct download (converted from share link)
_GDRIVE_FILE_ID = "1cUagShzCe0XsCbF5NEU9T62ICcU2I5AO"
PDF_URL = f"https://drive.google.com/uc?export=download&id={_GDRIVE_FILE_ID}"


@st.cache_resource(show_spinner="📄 Loading knowledge base…")
def load_qa_pairs() -> list:
    """Download PDF, extract text, parse into Q&A pairs."""
    text = _fetch_pdf_text()
    return _parse_qa(text)


def _fetch_pdf_text() -> str:
    try:
        import PyPDF2
        resp = requests.get(PDF_URL, timeout=30)
        resp.raise_for_status()
        reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages)
    except Exception as e:
        st.warning(f"Could not download PDF ({e}). Using built-in fallback Q&A.")
        return _fallback_text()


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

    return pairs if pairs else _fallback_pairs()


def answer_question(query: str) -> dict:
    """
    Search loaded Q&A pairs for the best keyword match.
    Returns {"found": bool, "answer": str, "matched_question": str, "score": int}
    """
    qa_pairs = load_qa_pairs()
    query_lower = query.lower()
    query_words = set(re.findall(r'\b\w{3,}\b', query_lower))

    best_score = 0
    best_match = None

    for pair in qa_pairs:
        q_lower = pair["question"].lower()
        a_lower = pair["answer"].lower()
        score = 0

        if query_lower in q_lower:
            score += 20

        q_words = set(re.findall(r'\b\w{3,}\b', q_lower))
        a_words = set(re.findall(r'\b\w{3,}\b', a_lower))
        score += len(query_words & q_words) * 3
        score += len(query_words & a_words) * 1

        tech_terms = {'list', 'tuple', 'dict', 'dictionary', 'set', 'function',
                      'class', 'object', 'lambda', 'decorator', 'generator',
                      'iterator', 'exception', 'module', 'package', 'inheritance',
                      'polymorphism', 'encapsulation', 'abstraction', 'gil',
                      'pep8', 'comprehension', 'thread', 'process', 'async'}
        score += len((query_words & tech_terms) & (q_words & tech_terms)) * 5

        if score > best_score:
            best_score = score
            best_match = pair

    THRESHOLD = 4

    if best_match and best_score >= THRESHOLD:
        return {
            "found": True,
            "answer": best_match["answer"],
            "matched_question": best_match["question"],
            "score": best_score,
        }

    return {"found": False, "answer": "", "matched_question": "", "score": 0}


def get_all_questions() -> list:
    return [p["question"] for p in load_qa_pairs()]


def _fallback_text() -> str:
    return """
1. What is Python?
Python is a high-level, interpreted, general-purpose programming language known for its simplicity, readability, and vast ecosystem.

2. What are Python's key features?
Python features dynamic typing, interpreted execution, object-oriented design, a large standard library, and cross-platform support.

3. What is PEP 8?
PEP 8 is Python's official style guide that defines conventions for writing clean and readable Python code.

4. What is the difference between a list and a tuple?
Lists are mutable ordered collections defined with square brackets. Tuples are immutable ordered collections defined with parentheses.

5. What is a dictionary in Python?
A dictionary is an unordered key-value mapping. Keys must be unique and hashable. Defined with curly braces.

6. What is a lambda function?
A lambda is an anonymous single-expression function: lambda x: x * 2. Used for short throwaway functions.

7. What is a decorator?
A decorator wraps a function to extend its behavior without modifying its code. Applied with @decorator syntax.

8. What is the GIL?
The Global Interpreter Lock prevents multiple native threads from executing Python bytecode simultaneously in CPython.

9. What is a class in Python?
A class is a blueprint for creating objects. It defines attributes and methods shared by all instances.

10. What is inheritance?
Inheritance lets a child class acquire attributes and methods from a parent class using class Child(Parent).

11. What is a generator?
A generator is a function that yields values lazily using the yield keyword instead of returning all at once.

12. What is list comprehension?
List comprehension creates lists concisely: [x*2 for x in range(10) if x % 2 == 0].

13. What is the difference between append and extend?
append() adds a single element to a list. extend() adds all elements from an iterable.

14. What are Python built-in data types?
Python built-in types include int, float, str, bool, list, tuple, dict, set, and NoneType.

15. What is object-oriented programming?
OOP organizes code into classes and objects. Supports inheritance, encapsulation, polymorphism, and abstraction.
"""


def _fallback_pairs() -> list:
    return _parse_qa(_fallback_text())
