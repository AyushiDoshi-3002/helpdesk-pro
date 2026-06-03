"""
storage_info.py  –  Document Viewer + Storage Info Dialog
"""

import streamlit as st
from datetime import datetime, timezone, timedelta

# ── Roles and passwords ───────────────────────────────────────────────────────
PRIVILEGED_ROLES = {"Manager", "Sr. Manager", "Tech Manager", "CTO", "CEO"}

ROLE_PASSWORDS: dict[str, str] = {
    "Manager":      "Mgr456",
    "Sr. Manager":  "SrMgr789",
    "Tech Manager": "Manager123",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

IST = timezone(timedelta(hours=5, minutes=30))

def _to_ist(dt_str: str) -> str:
    try:
        normalised = dt_str.strip().replace(" ", "T").replace("Z", "+00:00")
        if "+" not in normalised[10:] and normalised[-6] != "+":
            normalised += "+00:00"
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return dt_str


def _get_db():
    try:
        import app as _app
        return _app.get_db()
    except Exception:
        pass
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _fetch_documents() -> list:
    db = _get_db()
    if db is None:
        return []
    try:
        return (
            db.table("documents")
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data or []
        )
    except Exception as e:
        st.sidebar.error(f"Could not load documents: {e}")
        return []


_SENS_COLOR = {
    "Normal":       ("#3d5a4a", "#d4e8dc"),
    "Restricted":   ("#8b6914", "#f0e2b0"),
    "Confidential": ("#8b3a2a", "#f0e0db"),
    "Top Secret":   ("#f5f0e8", "#1a1612"),
}

_ROLE_LEVEL = {
    "Employee":     0,
    "Team Lead":    1,
    "Manager":      2,
    "Sr. Manager":  2,
    "Tech Manager": 3,
    "CTO":          4,
    "CEO":          5,
}
_MIN_ROLE_LEVEL = {
    "Employee":     0,
    "Manager":      2,
    "Tech Manager": 3,
    "CTO":          4,
    "CEO":          5,
}

def _viewer_can_see(viewer_role: str, doc_min_role: str) -> bool:
    if viewer_role in ("CTO", "CEO"):
        return True
    viewer_level = _ROLE_LEVEL.get(viewer_role, 0)
    min_level    = _MIN_ROLE_LEVEL.get(doc_min_role, 0)
    return viewer_level >= min_level


# ── Storage Info Dialog ───────────────────────────────────────────────────────
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
        <li><b>ap_requests</b> table → every approval pipeline request</li>
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
      <small>⚠️ Wiped on every app restart.</small>
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


# ── Main public function ──────────────────────────────────────────────────────
def show_storage_info_button():
    # ── Session state init ────────────────────────────────────────────────────
    if "si_role"          not in st.session_state: st.session_state["si_role"]          = "Manager"
    if "si_pwd_open"      not in st.session_state: st.session_state["si_pwd_open"]      = False
    if "si_authenticated" not in st.session_state: st.session_state["si_authenticated"] = False
    if "si_auth_role"     not in st.session_state: st.session_state["si_auth_role"]     = ""
    if "si_docs_open"     not in st.session_state: st.session_state["si_docs_open"]     = False

    # ── Storage info button ───────────────────────────────────────────────────
    if st.button("🗄️ Where is data saved?", use_container_width=True, key="storage_info_btn"):
        _storage_dialog()

    st.markdown("---")

    # ── Document viewer ───────────────────────────────────────────────────────
    role = st.session_state["si_role"]

    already_auth = (
        st.session_state["si_authenticated"]
        and st.session_state["si_auth_role"] == role
    )

    if not already_auth:
        if st.button("📁 View Documents", key="si_view_docs_btn", use_container_width=True):
            st.session_state["si_pwd_open"]  = True
            st.session_state["si_docs_open"] = False

    # ── Password prompt ───────────────────────────────────────────────────────
    if st.session_state["si_pwd_open"] and not already_auth:
        with st.sidebar:
            st.markdown(
                "<p style='font-family:EB Garamond,serif;font-size:14px;"
                "color:#f5f0e8;margin:4px 0 2px;'>Enter password:</p>",
                unsafe_allow_html=True,
            )
            role_select = st.selectbox(
                "Role",
                list(ROLE_PASSWORDS.keys()),
                key="si_role_login_select",
                label_visibility="collapsed",
            )
            pwd_input = st.text_input(
                "Password",
                type="password",
                key="si_pwd_input",
                label_visibility="collapsed",
                placeholder="Password…",
            )
            col_ok, col_cancel = st.columns(2)
            with col_ok:
                if st.button("Confirm", key="si_pwd_confirm", use_container_width=True):
                    if pwd_input == ROLE_PASSWORDS.get(role_select, ""):
                        st.session_state["si_authenticated"] = True
                        st.session_state["si_auth_role"]     = role_select
                        st.session_state["si_role"]          = role_select
                        st.session_state["si_pwd_open"]      = False
                        st.session_state["si_docs_open"]     = True
                        st.toast(f"✓ Authenticated as {role_select}", icon="🔓")
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
            with col_cancel:
                if st.button("Cancel", key="si_pwd_cancel", use_container_width=True):
                    st.session_state["si_pwd_open"] = False
                    st.rerun()

    # ── Authenticated view ────────────────────────────────────────────────────
    if already_auth:
        col_btn, col_out = st.columns([3, 1])
        with col_btn:
            btn_label = "📂 Close Documents" if st.session_state["si_docs_open"] else "📁 View Documents"
            if st.button(btn_label, key="si_toggle_docs_btn", use_container_width=True):
                st.session_state["si_docs_open"] = not st.session_state["si_docs_open"]
                st.rerun()
        with col_out:
            if st.button("🔒", key="si_sign_out_btn", use_container_width=True, help="Sign out"):
                st.session_state["si_authenticated"] = False
                st.session_state["si_auth_role"]     = ""
                st.session_state["si_docs_open"]     = False
                st.session_state["si_pwd_open"]      = False
                st.rerun()

        if st.session_state["si_docs_open"]:
            _render_document_viewer(role)


# ── Document viewer renderer ──────────────────────────────────────────────────
def _render_document_viewer(viewer_role: str):
    docs = _fetch_documents()
    visible_docs = [
        d for d in docs
        if _viewer_can_see(viewer_role, d.get("min_role", "Employee"))
    ]

    categories  = sorted({d.get("category", "General") for d in visible_docs})
    cat_options = ["All"] + categories

    with st.sidebar:
        st.markdown(
            f"<p style='font-family:DM Mono,monospace;font-size:11px;"
            f"color:#3a3028;letter-spacing:.10em;text-transform:uppercase;"
            f"margin:10px 0 4px;'>Viewing as <strong style='color:#f5f0e8'>"
            f"{viewer_role}</strong></p>",
            unsafe_allow_html=True,
        )
        selected_cat = st.selectbox(
            "Category", cat_options, key="si_cat_filter", label_visibility="collapsed",
        )
        search_term = st.text_input(
            "Search", placeholder="Search documents…",
            key="si_doc_search", label_visibility="collapsed",
        )

    filtered = visible_docs
    if selected_cat != "All":
        filtered = [d for d in filtered if d.get("category") == selected_cat]
    if search_term.strip():
        kw = search_term.strip().lower()
        filtered = [
            d for d in filtered
            if kw in d.get("title", "").lower()
            or kw in (d.get("description") or "").lower()
        ]

    with st.sidebar:
        st.markdown(
            f"<p style='font-family:DM Mono,monospace;font-size:11px;"
            f"color:#6b5f55;letter-spacing:.06em;margin:4px 0 8px;'>"
            f"{len(filtered)} document(s)</p>",
            unsafe_allow_html=True,
        )
        if not filtered:
            st.markdown(
                "<p style='font-family:EB Garamond,serif;font-size:14px;"
                "color:#9c8e82;font-style:italic;'>No documents found.</p>",
                unsafe_allow_html=True,
            )
            return
        for doc in filtered:
            _render_doc_card_sidebar(doc, viewer_role)


def _render_doc_card_sidebar(doc: dict, viewer_role: str):
    title       = doc.get("title", "Untitled")
    category    = doc.get("category", "General")
    sensitivity = doc.get("sensitivity", "Normal")
    min_role    = doc.get("min_role", "Employee")
    description = doc.get("description") or ""
    preview     = doc.get("content_preview") or ""
    file_url    = doc.get("file_url") or ""
    owner       = doc.get("owner_id") or "—"
    created_at  = doc.get("created_at") or ""

    sens_color, sens_bg = _SENS_COLOR.get(sensitivity, ("#6b5f55", "#e8e0d0"))

    with st.sidebar.expander(f"📄 {title}", expanded=False):
        st.markdown(
            f"<div style='margin-bottom:8px;'>"
            f"<span style='font-family:DM Mono,monospace;font-size:10px;"
            f"background:#2a2420;color:#c8c0b8;border-radius:2px;"
            f"padding:2px 6px;letter-spacing:.06em;text-transform:uppercase;'>"
            f"{category}</span>"
            f"<span style='display:inline-block;background:{sens_bg};"
            f"color:{sens_color};border-radius:2px;padding:2px 6px;"
            f"font-size:10px;font-weight:600;letter-spacing:.08em;"
            f"text-transform:uppercase;font-family:DM Mono,monospace;"
            f"margin-left:4px;'>{sensitivity}</span>"
            f"<span style='font-family:DM Mono,monospace;font-size:10px;"
            f"color:#6b5f55;margin-left:6px;'>{min_role}+</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if description:
            st.markdown(
                f"<p style='font-family:EB Garamond,serif;font-size:14px;"
                f"color:#c8c0b8;line-height:1.6;margin:0 0 8px;'>"
                f"{description[:200]}{'…' if len(description) > 200 else ''}</p>",
                unsafe_allow_html=True,
            )
        if preview:
            st.markdown(
                f"<div style='background:#2a2420;border-left:2px solid #8b3a2a;"
                f"border-radius:2px;padding:10px 12px;margin:6px 0;"
                f"font-family:EB Garamond,serif;font-size:13px;"
                f"color:#c8c0b8;line-height:1.6;'>"
                f"{preview[:400]}{'…' if len(preview) > 400 else ''}"
                f"</div>",
                unsafe_allow_html=True,
            )
        if file_url:
            st.markdown(
                f"<a href='{file_url}' target='_blank' "
                f"style='font-family:DM Mono,monospace;font-size:11px;"
                f"color:#c4543a;letter-spacing:.04em;'>↗ Open document</a>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<p style='font-family:DM Mono,monospace;font-size:10px;"
            f"color:#4a4038;margin-top:8px;'>"
            f"Owner: {owner} · Added: {_to_ist(created_at) if created_at else '—'}"
            f"</p>",
            unsafe_allow_html=True,
        )
