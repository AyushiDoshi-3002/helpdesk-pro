import streamlit as st

st.set_page_config(
    page_title="Smart Approval Pipeline",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Session state init ────────────────────────────────────────────────────────
if "db" not in st.session_state:
    st.session_state.db = []
if "next_id" not in st.session_state:
    st.session_state.next_id = 1
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "Submit Request"
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 Smart Pipeline")
    st.caption("Agentic Approval System")
    st.divider()

    pages = ["Submit Request", "Live Pipeline", "Your Approval", "History"]
    icons = ["📋", "⚙️", "✅", "📚"]
    for icon, pg in zip(icons, pages):
        if st.button(f"{icon} {pg}", use_container_width=True,
                     type="primary" if st.session_state.page == pg else "secondary"):
            st.session_state.page = pg
            st.rerun()

    st.divider()
    st.markdown("**Agent Chain**")
    st.markdown("""
    🔍 System Classifier  
    👨‍💼 Senior Agent  
    🧑‍🔧 Tech Lead Agent  
    🏛️ CTO / CEO Agent  
    ✅ **Your Approval ← YOU**  
    📚 KB Sync
    """)

    st.divider()
    db = st.session_state.db
    in_progress_statuses = {"Classifying", "Senior Review", "TechLead Review", "CTO Review", "CEO Review"}
    total    = len(db)
    progress = sum(1 for t in db if t["status"] in in_progress_statuses)
    awaiting = sum(1 for t in db if t["status"] == "Awaiting Approval")
    approved = sum(1 for t in db if t["status"] in ("Approved", "Done"))

    col1, col2 = st.columns(2)
    col1.metric("Total", total)
    col2.metric("In Pipeline", progress)
    col1.metric("Awaiting You", awaiting)
    col2.metric("Approved", approved)

# ── Route to page ─────────────────────────────────────────────────────────────
page = st.session_state.page

if page == "Submit Request":
    from pages.submit import render
    render()
elif page == "Live Pipeline":
    from pages.pipeline import render
    render()
elif page == "Your Approval":
    from pages.approval import render
    render()
elif page == "History":
    from pages.history import render
    render()
