"""
storage_info.py  –  Shows a popout/dialog explaining where each piece of data is saved.
Call show_storage_info_button() from any page or from app.py sidebar.
"""
import streamlit as st


def show_storage_info_button():
    """Renders a '🗄️ Where is data saved?' button in the sidebar."""
    if st.sidebar.button("🗄️ Where is data saved?", use_container_width=True):
        st.session_state["show_storage_info"] = not st.session_state.get("show_storage_info", False)

    if st.session_state.get("show_storage_info", False):
        _render_popout()


def _render_popout():
    """Renders the storage info as a styled dialog/modal using st.dialog (Streamlit ≥ 1.32)."""
    @st.dialog("🗄️ Where is your data saved?", width="large")
    def _dialog():
        st.markdown(
            """
            <style>
            .storage-section { border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; }
            .storage-supabase { background: #e6f4ea; border-left: 4px solid #1e8c45; }
            .storage-cache    { background: #ede7f6; border-left: 4px solid #6c3fc5; }
            .storage-session  { background: #fff8e1; border-left: 4px solid #f5a623; }
            .storage-never    { background: #fce8e8; border-left: 4px solid #d93025; }
            .storage-section h4 { margin: 0 0 6px 0; font-size: 15px; }
            .storage-section ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.8; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # ── Supabase ─────────────────────────────────────────────────────────
        st.markdown(
            """
            <div class="storage-section storage-supabase">
              <h4>☁️ Supabase — permanent cloud database</h4>
              <ul>
                <li><b>tickets</b> table → every support ticket submitted via the Employee Portal
                    <br><small>Written by <code>db.create_ticket()</code></small></li>
                <li><b>ap_requests</b> table → every approval pipeline request (create / approve / reject / delete)
                    <br><small>Written by <code>_db_insert()</code>, <code>_db_update()</code>, <code>_db_delete()</code> in approval_pipeline.py</small></li>
              </ul>
              <small>✅ Survives app restarts and redeploys.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Cache ─────────────────────────────────────────────────────────────
        st.markdown(
            """
            <div class="storage-section storage-cache">
              <h4>⚡ Streamlit @st.cache_resource — RAM only</h4>
              <ul>
                <li><b>Q&amp;A pairs</b> parsed from the Python Interview PDF
                    <br><small>Loaded by <code>load_qa_pairs()</code> in qa_engine.py</small></li>
              </ul>
              <small>⚠️ Wiped on every app restart. PDF is re-downloaded and re-parsed on next cold start.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Session state ─────────────────────────────────────────────────────
        st.markdown(
            """
            <div class="storage-section storage-session">
              <h4>🧠 st.session_state — browser tab memory</h4>
              <ul>
                <li><code>admin_logged_in</code> — admin login status (admin.py)</li>
                <li><code>ap_role_auth</code> — which role tabs are authenticated (approval_pipeline.py)</li>
                <li><code>ap_requests</code> — local mirror of Supabase approval requests, rebuilt on refresh</li>
                <li><code>ap_next_id</code> — counter for generating REQ-001, REQ-002… IDs</li>
                <li><code>ap_confirm_delete</code> — tracks which delete buttons are in "confirm" state</li>
                <li><code>prefill_query</code> — carries unanswered question down to the ticket form</li>
                <li><code>show_ticket</code> — controls whether the ticket form expander is open</li>
              </ul>
              <small>⚠️ Gone when the browser tab closes or app restarts. Never written to disk or DB.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Never saved ───────────────────────────────────────────────────────
        st.markdown(
            """
            <div class="storage-section storage-never">
              <h4>🚫 Never saved anywhere</h4>
              <ul>
                <li><b>Passwords</b> — admin &amp; role passwords are hardcoded constants, never stored in DB or logs</li>
                <li><b>Raw PDF bytes</b> — downloaded, parsed, then discarded; only the parsed Q&amp;A pairs are cached</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("✖ Close", use_container_width=True):
            st.session_state["show_storage_info"] = False
            st.rerun()

    _dialog()
