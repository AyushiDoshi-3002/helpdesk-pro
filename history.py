import streamlit as st
from utils import delete_task, fmt_date, risk_color, status_emoji


def render():
    st.title("📚 Decision History")
    st.caption("All approved, rejected, and completed requests.")

    db = st.session_state.db
    hist = [t for t in reversed(db) if t["status"] in ("Approved", "Rejected", "Done")]

    if not hist:
        st.info("No decisions yet. Submit a request and walk it through the pipeline.")
        return

    for task in hist:
        icon = status_emoji(task["status"])
        with st.expander(
            f"{icon} **#{task['id']}** · {task['title']} — {task['status']}",
            expanded=False,
        ):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Requester:** {task['requester']}")
            c2.markdown(f"**Department:** {task['department']}")
            c3.markdown(f"**Type:** {task['request_type']}")
            c1.markdown(f"**Risk:** {risk_color(task['risk_level'])} {task['risk_level']}")
            c2.markdown(f"**Submitted:** {fmt_date(task['created_at'])}")
            c3.markdown(f"**Completed:** {fmt_date(task['updated_at'])}")

            if task.get("reviewer_note"):
                st.divider()
                st.markdown("**💬 Reviewer note:**")
                if task["status"] == "Approved":
                    st.success(task["reviewer_note"])
                else:
                    st.error(task["reviewer_note"])

            st.divider()
            if st.button(f"🗑️ Delete #{task['id']}", key=f"hist_del_{task['id']}"):
                delete_task(task["id"])
                st.rerun()
