"""
Employee Portal – search Q&A, raise tickets.
"""
import streamlit as st
from qa_engine import answer_question
import db


def show():
    st.markdown("# 🔍 Employee Help Portal")
    st.markdown(
        "<p style='color:#6b7280;font-size:15px;margin-top:-10px'>"
        "Ask any Python-related question. If we don't have an answer, raise a support ticket.</p>",
        unsafe_allow_html=True,
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

    # Handle search
    if search_btn and question.strip():
        with st.spinner("🔍 Searching knowledge base…"):
            result = answer_question(question.strip())

        if result["found"]:
            st.markdown("#### ✅ Answer Found")
            st.markdown(
                f"<small style='color:#7c3aed'>📌 Matched: <em>{result['matched_question']}</em></small>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='answer-box'>{result['answer']}</div>",
                unsafe_allow_html=True,
            )
            st.success("This answer came from our Python Knowledge Base.", icon="📚")

        else:
            st.markdown("#### ❌ No Answer Found")
            st.markdown(
                "<div class='no-answer-box'>"
                "⚠️ We couldn't find an answer for your query in our knowledge base. "
                "Please raise a support ticket below and our team will get back to you."
                "</div>",
                unsafe_allow_html=True,
            )
            # Auto-scroll hint
            st.session_state["prefill_query"] = question.strip()
            st.session_state["show_ticket"] = True

    elif search_btn and not question.strip():
        st.warning("Please enter a question before searching.")

    # ── Ticket Section ────────────────────────────────────────────────────────
    show_ticket = st.session_state.get("show_ticket", False)

    st.markdown("---")
    with st.expander(
        "📝 Raise a Support Ticket" + (" ← Your question wasn't found, create a ticket!" if show_ticket else ""),
        expanded=show_ticket,
    ):
        _ticket_form()


def _ticket_form():
    """Ticket creation form."""
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
            [
                "Select…",
                "Software Engineer",
                "Data Analyst",
                "QA Engineer",
                "DevOps Engineer",
                "Product Manager",
                "HR / Operations",
                "Sales",
                "Other",
            ],
        )

    with col2:
        priority = st.selectbox(
            "🚨 Priority *",
            ["Medium", "High", "Low"],
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

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        submit = st.button("🚀 Submit Ticket", use_container_width=True)

    if submit:
        # Validation
        errors = []
        if not user_id.strip():
            errors.append("Employee ID is required.")
        if job_role == "Select…":
            errors.append("Please select your job role.")
        if not query_text.strip():
            errors.append("Problem description is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                ticket = db.create_ticket(
                    user_id=user_id.strip(),
                    job_role=job_role,
                    query=query_text.strip(),
                    priority=priority,
                )
                ticket_id = ticket.get("id", "–")
                st.success(
                    f"✅ Ticket #{ticket_id} submitted successfully! "
                    "Our admin team will review it shortly.",
                    icon="🎉",
                )
                # Clear prefill
                st.session_state.pop("prefill_query", None)
                st.session_state["show_ticket"] = False

            except ConnectionError as ce:
                st.error(str(ce))
            except Exception as ex:
                st.error(f"Failed to submit ticket: {ex}")
