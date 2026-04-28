import streamlit as st
from utils import (
    ADMIN_PASSWORD, get_by_status, update_task, delete_task,
    fmt_date, risk_color, status_emoji, AGENTS, CAT_LABELS
)
from agents import run_kb_for_task


def _render_agent_summary(sr: dict, task: dict):
    """Compact agent chain summary for approval view."""
    for agent in AGENTS:
        aid  = agent["id"]
        res  = sr.get(aid)
        if not res:
            continue
        dec = res.get("decision", "")
        icon = "✅" if dec not in ("Reject",) else "❌"
        if res.get("skipped"): icon = "⏭️"
        reason = res.get("reason") or res.get("routing_note") or res.get("status") or ""
        st.markdown(f"{icon} **{agent['icon']} {agent['label']}** — {reason}")

        if aid == "techlead" and res.get("cto_email_body"):
            role = "CEO" if res.get("needs_ceo") else "CTO"
            with st.expander(f"📧 Tech Lead briefing to {role}"):
                st.write(res["cto_email_body"])

        if aid == "classifier":
            risk = res.get("risk", "")
            cat  = CAT_LABELS.get(res.get("category", ""), res.get("category", ""))
            st.caption(f"`{cat}` · `{risk} risk`" + (" · `🔒 security`" if res.get("involves_security") else ""))


def render():
    st.title("✅ Your Approval")
    st.caption("The only manual step — every task here has been reviewed by the full agent chain.")

    # Login gate
    if not st.session_state.logged_in:
        st.divider()
        with st.container():
            col = st.columns([1, 2, 1])[1]
            with col:
                st.subheader("🔐 Admin Login")
                pwd = st.text_input("Password", type="password", key="login_pwd")
                if st.button("Login →", type="primary", use_container_width=True):
                    if pwd == ADMIN_PASSWORD:
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        return

    # Logged in
    awaiting = get_by_status("Awaiting Approval")

    if not awaiting:
        st.success("🎉 Nothing waiting for your approval right now.")
        return

    st.warning(f"🔔 **{len(awaiting)} task(s)** need your approval.")

    for task in awaiting:
        sr = task.get("stage_results", {})
        with st.expander(
            f"⏳ **#{task['id']}** · {task['title']} — {risk_color(task['risk_level'])} {task['risk_level']} risk",
            expanded=True,
        ):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Requester:** {task['requester']}")
            c2.markdown(f"**Department:** {task['department']}")
            c3.markdown(f"**Type:** {task['request_type']}")
            c1.markdown(f"**Priority:** {task.get('priority','Medium')}")
            c2.markdown(f"**Submitted:** {fmt_date(task['created_at'])}")

            st.divider()
            st.markdown(f"> {task['description']}")
            st.divider()

            st.subheader("📋 Agent Chain Summary")
            _render_agent_summary(sr, task)

            st.divider()
            note = st.text_area(
                "Your decision note (optional)",
                placeholder="Add context for the record…",
                key=f"note_{task['id']}",
                height=80,
            )

            col_a, col_r, col_d = st.columns([2, 2, 1])
            with col_a:
                if st.button(f"✅ Approve → KB", key=f"approve_{task['id']}", type="primary", use_container_width=True):
                    new_sr = dict(sr)
                    new_sr["human"] = {
                        "agent": "You",
                        "decision": "Approved",
                        "reason": note or "Approved by authority.",
                    }
                    update_task(task["id"], {
                        "status": "Approved",
                        "stage": "kb",
                        "stage_results": new_sr,
                        "reviewer_note": note,
                    })
                    run_kb_for_task(task["id"], new_sr)
                    st.success("✅ Approved! Knowledge base updated.")
                    st.rerun()

            with col_r:
                if st.button(f"❌ Reject", key=f"reject_{task['id']}", use_container_width=True):
                    new_sr = dict(sr)
                    new_sr["human"] = {
                        "agent": "You",
                        "decision": "Rejected",
                        "reason": note or "Rejected by authority.",
                    }
                    update_task(task["id"], {
                        "status": "Rejected",
                        "stage": "human",
                        "stage_results": new_sr,
                        "reviewer_note": note,
                    })
                    st.error("❌ Rejected.")
                    st.rerun()

            with col_d:
                if st.button(f"🗑️", key=f"del_{task['id']}", use_container_width=True):
                    delete_task(task["id"])
                    st.rerun()
