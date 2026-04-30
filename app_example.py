"""
app.py  –  Main entry point. Add the storage info button to your sidebar.
Only the relevant sidebar section is shown below — merge with your existing app.py.
"""
import streamlit as st

# ── ADD THIS IMPORT ───────────────────────────────────────────────────────────
from storage_info import show_storage_info_button

# ── Your existing page imports ────────────────────────────────────────────────
# import employee_portal
# import admin
# import approval_pipeline
# import setup

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏢 HelpDesk Pro")
    st.markdown("---")

    # Your existing navigation buttons / selectbox go here ...
    # e.g. page = st.selectbox("Navigate", [...])

    st.markdown("---")

    # ── ADD THIS ONE LINE anywhere in the sidebar ─────────────────────────────
    show_storage_info_button()

# ── Rest of your app routing stays exactly the same ───────────────────────────
# if page == "Employee Portal": employee_portal.show()
# elif page == "Admin": admin.show()
# ...
