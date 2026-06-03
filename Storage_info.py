"""
storage_info.py  –  Shows a dialog explaining where each piece of data is saved.
"""
import streamlit as st


@st.dialog("🗄️ Where is your data saved?", width="large")
def _storage_dialog():
    st.markdown("""
    <style>
    .storage-section { border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; }
    .storage-supabase { background: #e6f4ea; border-left: 4px solid #1e8c45; }
    .storage-cache    { background: #ede7f6; border-left: 4px solid #6c3fc5; }
    .storage-session  { background: #fff8e1; border-left: 4px solid #f5a623; }
    .storage-never    { background: #fce8e8; border-left: 4px solid #d93025; }
    .storage-section h4 { margin: 0 0 6px 0; font-size: 15px; }
    .storage-section ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.8; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="storage-section storage-supabase">
      <h4>☁️ Supabase — permanent cloud database</h4>
      <ul>
        <li><b>tickets</b> table → every support ticket submitted via the Employee Portal</li>
        <li><b>ap_requests</b> table → every approval pipeline request (create / approve / reject / delete)</li>
      </ul>
      <small>✅ Survives app restarts and redeploys.</small>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="storage-section storage-cache">
      <h4>⚡ Streamlit @st.cache_resource — RAM only</h4>
      <ul>
        <li><b>Q&amp;A pairs</b> parsed from the PDF knowledge base</li>
      </ul>
      <small>⚠️ Wiped on every app restart. PDF is re-downloaded and re-parsed on next cold start.</small>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="storage-section storage-session">
      <h4>🧠 st.session_state — browser tab memory</h4>
      <ul>
        <li><code>admin_logged_in</code> — admin login status</li>
        <li><code>ap_role_auth</code> — which role tabs are authenticated</li>
        <li><code>ap_requests</code> — local mirror of Supabase approval requests</li>
        <li><code>show_ticket</code> — controls ticket form visibility</li>
        <li><code>ticket_query</code> — carries unanswered question to ticket form</li>
      </ul>
      <small>⚠️ Gone when the browser tab closes or app restarts.</small>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="storage-section storage-never">
      <h4>🚫 Never saved anywhere</h4>
      <ul>
        <li><b>Passwords</b> — never stored in DB or logs</li>
        <li><b>Raw PDF bytes</b> — downloaded, parsed, then discarded</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)


def show_storage_info_button():
    """Renders a button in the sidebar that opens the storage info dialog."""
    if st.sidebar.button("🗄️ Where is data saved?", use_container_width=True, key="storage_info_btn"):
        _storage_dialog()
