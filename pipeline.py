import streamlit as st
from utils import get_all, get_stats, delete_task, fmt_date, risk_color, status_emoji, AGENTS, CAT_LABELS
from agents import run_heartbeat_tick, run_kb_for_task


def _render_hierarchy(sr: dict, current_stage: str, task: dict):
    for agent in AGENTS:
        aid = agent["id"]
        res = sr.get(aid)

        col_icon, col_body = st.columns([1, 10])

        with col_icon:
            if res:
                dec = res.get("decision", "")
                if dec == "Reject":
                    st.markdown("### ❌")
                elif res.get("skipped"):
                    st.markdown("### ⏭️")
                elif dec in ("Approve", "Approved", "Routed", "updated", "Done"):
                    st.markdown("### ✅")
                elif dec == "Escalate_Human":
                    st.markdown("### ⬆️")
                else:
                    st.markdown("### ✅")
            elif aid == current_stage:
                st.markdown("### ⏳")
            else:
                st.markdown("### ⚫")

        with col_body:
            badge = ""
            if agent.get("manual"):
                badge = "🟡 MANUAL"
            elif res and res.get("skipped"):
                badge = "🔵 AUTO-PASS"
            elif aid == current_stage and not res:
                badge = "🟢 ACTIVE"
            else:
                badge = "🤖 AUTO"

            role_note = f" (as {res['role']})" if res and res.get("role") else ""
            st.markdown(f"**{agent['icon']} {agent['label']}{role_note}** `{badge}`")
            st.caption(agent["desc"])

            if res:
                dec = res.get("decision", "")
                reason = res.get("reason") or res.get("routing_note") or res.get("status") or ""
                if dec == "Reject":
                    st.error(reason)
                elif res.get("skipped"):
                    st.info(reason)
                elif aid == "classifier":
                    # Show classification tags
                    risk = res.get("risk", "")
                    cat  = CAT_LABELS.get(res.get("category", ""), res.get("category", ""))
                    tags = f"`{cat}` · `{risk} risk`"
                    if res.get("involves_security"): tags += " · `🔒 security-critical`"
                    if res.get("involves_external"): tags += " · `🌐 external integration`"
                    if res.get("needs_ceo"):         tags += " · `CEO-level routing`"
                    if res.get("auto_pass_senior"):  tags += " · `✨ senior auto-pass`"
                    st.success(f"{tags}")
                    if res.get("summary"):
                        st.caption(f"❝{res['summary']}❞")
                elif aid == "techlead" and res.get("cto_email_body"):
                    st.success(reason)
                    role = "CEO" if res.get("needs_ceo") else "CTO"
                    with st.expander(f"📧 View briefing email to {role}"):
                        st.markdown(f"**From:** Tech Lead · System Notification  \n**To:** {role} · Approval Required  \n**Re:** {task.get('title', '')}")
                        st.divider()
                        st.write(res["cto_email_body"])
                        if res.get("technical_note"):
                            st.caption(f"Technical note: {res['technical_note']}")
                else:
                    st.success(reason)
            elif aid == current_stage:
                st.info("Agent working…")

        st.divider()


def render():
    st.title("⚙️ Live Pipeline")
    st.caption("All requests and their current agent stage.")

    # Heartbeat controls
    hb_col1, hb_col2 = st.columns([3, 1])
    with hb_col1:
        st.info("🤖 **Agent heartbeat** — click the button to advance queued tasks through the pipeline.")
    with hb_col2:
        if st.button("⚡ Run Agents Now", type="primary", use_container_width=True):
            with st.spinner("Agents running…"):
                processed = run_heartbeat_tick()
            if processed:
                st.success(f"✅ {processed} task(s) advanced!")
                st.rerun()
            else:
                st.info("Nothing to process right now.")

    # Metrics
    s = get_stats()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📋 Total", s["total"])
    c2.metric("⚙️ In Pipeline", s["progress"])
    c3.metric("🔔 Needs OK", s["awaiting"])
    c4.metric("🟢 Approved", s["approved"])
    c5.metric("🔴 Rejected", s["rejected"])

    st.divider()

    # Filter tabs
    filter_options = [
        "All", "Classifying", "Senior Review", "TechLead Review",
        "CTO Review", "CEO Review", "Awaiting Approval", "Approved", "Rejected", "Done"
    ]
    if "pipeline_filter" not in st.session_state:
        st.session_state.pipeline_filter = "All"

    selected = st.radio("Filter", filter_options, horizontal=True,
                        index=filter_options.index(st.session_state.pipeline_filter),
                        label_visibility="collapsed")
    st.session_state.pipeline_filter = selected

    tasks = get_all(selected)

    if not tasks:
        st.info("No tasks found. Submit a request to get started.")
        return

    for task in tasks:
        sr = task.get("stage_results", {})
        with st.expander(
            f"{status_emoji(task['status'])} **#{task['id']}** · {task['title']} "
            f"— {task['status']} · {risk_color(task['risk_level'])} {task['risk_level']} risk",
            expanded=(task["status"] == "Awaiting Approval"),
        ):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Requester:** {task['requester']}")
            c2.markdown(f"**Department:** {task['department']}")
            c3.markdown(f"**Type:** {task['request_type']}")
            c1.markdown(f"**Priority:** {task.get('priority','Medium')}")
            c2.markdown(f"**Created:** {fmt_date(task['created_at'])}")

            st.divider()
            st.markdown(f"> {task['description']}")
            st.divider()

            st.subheader("🔗 Agent Chain")
            _render_hierarchy(sr, task.get("stage", ""), task)

            if st.button(f"🗑️ Delete #{task['id']}", key=f"del_{task['id']}"):
                delete_task(task["id"])
                st.rerun()
