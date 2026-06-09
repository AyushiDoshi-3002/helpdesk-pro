"""
doc_visibility.py – Improved with better CSS
"""
import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from styles import apply_global_styles   # ← NEW IMPORT

# ... [Keep all your existing imports and functions until page_doc_visibility() ] ...

def page_doc_visibility():
    apply_global_styles()          # ← Apply global styles
    _init()
    
    st.markdown(_CSS, unsafe_allow_html=True)   # Keep your local CSS too

    if not st.session_state.dv_loaded:
        _load()

    # Hero Section
    st.markdown("""
    <div class='dv-hero'>
      <p class='dv-hero-title'>Document Visibility Control</p>
      <p class='dv-hero-sub'>
        Secure role-based access to sensitive documents with automatic 7-day expiry.
      </p>
      <div class='hierarchy-bar'>
        <span class='hier-role hier-tm'>Team Member</span><span class='hier-arrow'>→</span>
        <span class='hier-role hier-tl'>Team Lead</span><span class='hier-arrow'>→</span>
        <span class='hier-role hier-tech'>Tech Manager</span><span class='hier-arrow'>→</span>
        <span class='hier-role hier-mgr'>Manager</span><span class='hier-arrow'>→</span>
        <span class='hier-role hier-cto'>CTO</span><span class='hier-arrow'>→</span>
        <span class='hier-role hier-ceo'>CEO</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Rest of your tabs code remains same...
    pending_count = sum(1 for r in st.session_state.dv_requests if r.get("status") == "Pending")
    tab1, tab2, tab3 = st.tabs([
        "📂 Request Document Access",
        f"🔑 Approver Inbox ({pending_count})",
        "📋 All Access Records",
    ])

    with tab1: _tab_request()
    with tab2: _tab_approver_inbox()
    with tab3: _tab_all_records()


# Keep your existing _CSS but enhance it:
_CSS = """
<style>
.dv-hero {
    background: linear-gradient(135deg, #faf7f2, #f5f0e8);
    border: 1px solid #d4c9bc;
    border-top: 5px solid #8b3a2a;
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 24px;
    box-shadow: 0 6px 20px rgba(139,58,42,0.1);
}
.dv-hero-title {
    font-size: 28px;
    font-weight: 700;
    margin: 0 0 8px 0;
}
.dv-hero-sub {
    font-size: 17px;
    color: #6b5f55;
    margin: 0;
}
.timer-chip-green, .timer-chip-red {
    border-radius: 9999px;
    padding: 6px 14px;
    font-weight: 700;
}
.doc-card {
    border-radius: 12px;
    transition: all 0.3s ease;
}
</style>
"""
