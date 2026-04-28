import streamlit as st
from utils import CHANGE_TYPES, create_task, get_stats


def render():
    st.title("📋 Submit Change Request")
    st.caption("Fill in the form — agents will classify, review, and route automatically.")

    with st.form("submit_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            requester = st.text_input("Your Name / ID *", placeholder="e.g. Priya K · ENG-042")
            department = st.selectbox("Department *", [
                "", "Engineering", "Finance", "HR", "Legal",
                "Operations", "Security", "Executive", "Product", "Other"
            ])
            priority = st.selectbox("Priority", ["Medium", "High", "Low"])

        with col2:
            title = st.text_input("Change Title *", placeholder="e.g. Update API login documentation")
            request_type = st.selectbox("Change Type *", [
                "", *list(CHANGE_TYPES.keys())
            ])

        description = st.text_area(
            "Describe the change *",
            placeholder="What are you changing, why, and what are the risks? The classifier reads this to determine routing.",
            height=120,
        )

        # Route preview
        if request_type and request_type in CHANGE_TYPES:
            info = CHANGE_TYPES[request_type]
            risk_color = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(info["risk"], "⚪")
            ceo_note = "CEO routing" if info["needs_ceo"] else "CTO routing"
            auto_note = " · Senior auto-pass eligible" if info.get("auto_senior") else ""
            st.info(f"{risk_color} **Routing preview:** {info['risk']} risk → {ceo_note}{auto_note}")

        submitted = st.form_submit_button("🚀 Submit to Pipeline", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not requester.strip(): errors.append("Name / ID required.")
        if not title.strip():     errors.append("Title required.")
        if not department:        errors.append("Select department.")
        if not request_type:      errors.append("Select change type.")
        if not description.strip(): errors.append("Description required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            task = create_task({
                "title": title.strip(),
                "requester": requester.strip(),
                "department": department,
                "request_type": request_type,
                "description": description.strip(),
                "priority": priority,
            })
            st.success(f"✅ Task **#{task['id']}** created! Agents will pick it up on the next heartbeat.")
            st.balloons()

    # Stats row
    st.divider()
    st.subheader("📊 Pipeline Overview")
    s = get_stats()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📋 Total", s["total"])
    c2.metric("⚙️ In Pipeline", s["progress"])
    c3.metric("🔔 Needs OK", s["awaiting"])
    c4.metric("🟢 Approved", s["approved"])
    c5.metric("🔴 Rejected", s["rejected"])

    # How it works
    st.divider()
    st.subheader("🔄 How It Works")
    steps = [
        ("📋", "Submit", "Fill in this form with your change details"),
        ("🔍", "Classify", "AI classifier assigns risk & category"),
        ("👨‍💼", "Senior Review", "Senior agent reviews quality (auto-pass for low risk)"),
        ("🧑‍🔧", "Tech Lead", "Tech lead validates safety & drafts executive briefing"),
        ("🏛️", "CTO/CEO", "Executive agent makes final call or escalates"),
        ("✅", "Your Approval", "THE only manual step — you approve or reject"),
        ("📚", "KB Sync", "Auto-writes to knowledge base on approval"),
    ]
    cols = st.columns(len(steps))
    for col, (icon, label, desc) in zip(cols, steps):
        with col:
            st.markdown(f"**{icon} {label}**")
            st.caption(desc)
