"""
Employee Portal – search Q&A, raise tickets.
Now uses semantic similarity (sentence-transformers) + learned answers from Supabase.
"""
import streamlit as st
from qa_engine import answer_question, load_qa_pairs
import db


# ── Learned answers from Supabase (like your working model's check_learned_answers) ──

def _check_learned_answers(query: str) -> str | None:
    """
    Check Supabase resolved_issues table for a previously solved query.
    Exact substring match — same logic as your working model.
    """
    try:
        client = db.get_client()
        if client is None:
            return None
        response = client.table("resolved_issues").select("*").execute()
        for row in (response.data or []):
            if query.lower() in (row.get("query") or "").lower():
                return row.get("solution")
    except Exception:
        pass
    return None


def show():
    st.markdown("# 🔍 Employee Help Portal")
    st.markdown(
        "<p style='color:#6b7280;font-size:15px;margin-top:-10px'>"
        "Ask any question. If we don't have an answer, raise a support ticket.</p>",
        unsafe_allow_html=True,
    )

    # ── PDF / model status banner ─────────────────────────────────────────────
    error = st.session_state.get("pdf_load_error")
    if error:
        st.error(error, icon="🔒")
        st.info(
            "Until the PDF is accessible, searches will return 'No Answer Found'. "
            "Employees can still raise support tickets below.",
            icon="ℹ️",
        )
    else:
        pair_count = st.session_state.get("pdf_pair_count")
        if pair_count:
            st.success(
                f"📚 Knowledge Base: {pair_count} Q&A pairs loaded · "
                f"Powered by semantic AI search (all-MiniLM-L6-v2)",
                icon="✅",
            )

    # ── Search Section ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💬 Ask a Question")

    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input(
            "",
            placeholder="e.g. What is the difference between a list and a tuple?",
            key="question_input",
            label_visibility="collapsed",
        )
    with col2:
        search_btn = st.button("🔎 Search", use_container_width=True)

    if search_btn and question.strip():

        if st.session_state.get("pdf_load_error"):
            st.warning("⚠️ Knowledge base unavailable. Please raise a support ticket below.")
            st.session_state["prefill_query"] = question.strip()
            st.session_state["show_ticket"] = True

        else:
            with st.spinner("🔍 Searching knowledge base…"):

                # Step 1: check learned answers from Supabase first
                learned = _check_learned_answers(question.strip())

                if learned:
                    st.markdown("#### ✅ Answer Found")
                    st.markdown(
                        "<small style='color:#7c3aed'>📌 Source: <em>Previously resolved issue (learned answer)</em></small>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div class='answer-box'>{learned}</div>",
                        unsafe_allow_html=True,
                    )
                    st.success("This answer was learned from a previously resolved ticket.", icon="🧠")

                else:
                    # Step 2: semantic search on PDF
                    result = answer_question(question.strip())

                    if result["found"]:
                        st.markdown("#### ✅ Answer Found")
                        st.markdown(
                            f"<small style='color:#7c3aed'>📌 Matched: "
                            f"<em>{result['matched_question']}</em> "
                            f"(similarity: {result['score']})</small>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"<div class='answer-box'>{result['answer']}</div>",
                            unsafe_allow_html=True,
                        )
                        st.success("This answer came from the PDF Knowledge Base.", icon="📚")

                        # Feedback buttons
                        st.markdown("---")
                        fb_col1, fb_col2 = st.columns([1, 1])
                        with fb_col1:
                            if st.button("👍 Helpful", use_container_width=True):
                                st.toast("Thanks for your feedback!", icon="🙏")
                        with fb_col2:
                            if st.button("👎 Not helpful", use_container_width=True):
                                st.session_state["prefill_query"] = question.strip()
                                st.session_state["show_ticket"] = True
                                st.rerun()

                    else:
                        st.markdown("#### ❌ No Answer Found")
                        st.markdown(
                            f"<div class='no-answer-box'>"
                            f"⚠️ Best similarity score was <b>{result['score']}</b> "
                            f"(need ≥ 0.4). This question isn't covered in our knowledge base. "
                            f"Please raise a support ticket below."
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        st.session_state["prefill_query"] = question.strip()
                        st.session_state["show_ticket"] = True

    elif search_btn and not question.strip():
        st.warning("Please enter a question before searching.")

    # ── Ticket Section ────────────────────────────────────────────────────────
    show_ticket = st.session_state.get("show_ticket", False)
    st.markdown("---")
    with st.expander(
        "📝 Raise a Support Ticket"
        + (" ← Your question wasn't found, create a ticket!" if show_ticket else ""),
        expanded=show_ticket,
    ):
        _ticket_form()


def _ticket_form():
    prefill = st.session_state.get("prefill_query", "")

    st.markdown(
        "<p style='color:#6b7280;font-size:14px'>"
        "Fill in the details below. Our admin team will review and respond to your ticket.</p>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        user_id = st.text_input("👤 Employee ID *", placeholder="e.g. EMP-1042")
        job_role = st.selectbox(
            "💼 Job Role *",
            ["Select…", "Software Engineer", "Data Analyst", "QA Engineer",
             "DevOps Engineer", "Product Manager", "HR / Operations", "Sales", "Other"],
        )
    with col2:
        priority = st.selectbox(
            "🚨 Priority *", ["Medium", "High", "Low"],
            help="High = blocking work, Medium = important, Low = general query",
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<small style='color:#6b7280'>Tickets are usually resolved within 24 hours.</small>",
            unsafe_allow_html=True,
        )

    query_text = st.text_area(
        "📋 Describe your problem *",
        value=prefill,
        placeholder="Describe the issue you are facing in detail…",
        height=120,
    )

    if st.button("🚀 Submit Ticket", use_container_width=True):
        errors = []
        if not user_id.strip():       errors.append("Employee ID is required.")
        if job_role == "Select…":     errors.append("Please select your job role.")
        if not query_text.strip():    errors.append("Problem description is required.")

        for e in errors:
            st.error(e)

        if not errors:
            try:
                ticket = db.create_ticket(
                    user_id=user_id.strip(),
                    job_role=job_role,
                    query=query_text.strip(),
                    priority=priority,
                )
                st.success(
                    f"✅ Ticket #{ticket.get('id','–')} submitted! "
                    "Our admin team will review it shortly.", icon="🎉",
                )
                st.session_state.pop("prefill_query", None)
                st.session_state["show_ticket"] = False
            except ConnectionError as ce:
                st.error(str(ce))
            except Exception as ex:
                st.error(f"Failed to submit ticket: {ex}")
