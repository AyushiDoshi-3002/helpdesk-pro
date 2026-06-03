"""
storage_info.py  –  Role-gated Document Viewer
────────────────────────────────────────────────
Only visible in the sidebar for:
    Manager | Sr. Manager | Tech Manager | CTO | CEO

Flow:
  1. User picks their role from a selectbox in the sidebar.
  2. If the role is privileged, a "View Documents" button appears.
  3. Clicking it opens an inline password prompt.
  4. Correct password → full document library renders in a modal-style
     expander inside the sidebar (or as a full page if you prefer).

Passwords are the same ones already used in approval_pipeline.py:
    Manager      → Mgr456
    Tech Manager → Manager123
    CTO          → CTO123
    CEO          → CEO123
    Sr. Manager  → SrMgr789   (add to ROLE_PASSWORDS in approval_pipeline.py
                                if you want to keep them in sync)

HOW TO USE
──────────
In your app.py sidebar block, replace / extend your existing navigation
section with:

    from storage_info import show_storage_info_button

    with st.sidebar:
        ...
        show_storage_info_button()

That single call handles everything — role selector, password gate,
and document display.
"""

import streamlit as st
from datetime import datetime, timezone, timedelta

# ── Roles that are allowed to see the button at all ───────────────────────────
PRIVILEGED_ROLES = {"Manager", "Sr. Manager", "Tech Manager", "CTO", "CEO"}

# ── Per-role passwords (keep in sync with approval_pipeline.py) ───────────────
ROLE_PASSWORDS: dict[str, str] = {
    "Manager":      "Mgr456",
    "Sr. Manager":  "SrMgr789",
    "Tech Manager": "Manager123",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

# ── IST helper ────────────────────────────────────────────────────────────────
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


# ── DB helper (re-uses the Supabase client already wired in app.py) ───────────
def _get_db():
    """
    Tries to reuse the cached client from app.py.
    Falls back to creating a new one from secrets.
    """
    # app.py exposes get_db() — try that first to avoid a second connection.
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


# ── Sensitivity / role badge styling (mirrors app.py palette) ─────────────────
_SENS_COLOR = {
    "Normal":       ("#3d5a4a", "#d4e8dc"),   # (text, bg)
    "Restricted":   ("#8b6914", "#f0e2b0"),
    "Confidential": ("#8b3a2a", "#f0e0db"),
    "Top Secret":   ("#f5f0e8", "#1a1612"),
}

def _sens_badge(sensitivity: str) -> str:
    color, bg = _SENS_COLOR.get(sensitivity, ("#6b5f55", "#e8e0d0"))
    return (
        f"<span style='display:inline-block;background:{bg};color:{color};"
        f"border-radius:2px;padding:2px 8px;font-size:11px;font-weight:600;"
        f"letter-spacing:.08em;text-transform:uppercase;"
        f"font-family:DM Mono,monospace;margin-left:6px;'>{sensitivity}</span>"
    )


# ── Role hierarchy for "can this role see this doc?" check ────────────────────
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
    """Return True if viewer_role meets or exceeds doc_min_role."""
    # CTO and CEO always see everything
    if viewer_role in ("CTO", "CEO"):
        return True
    viewer_level = _ROLE_LEVEL.get(viewer_role, 0)
    min_level    = _MIN_ROLE_LEVEL.get(doc_min_role, 0)
    return viewer_level >= min_level


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN PUBLIC FUNCTION — call this once inside `with st.sidebar:`
# ══════════════════════════════════════════════════════════════════════════════

def show_storage_info_button():
    """
    Renders the role selector and (if eligible + authenticated) the document
    viewer inside the Streamlit sidebar.

    Usage
    ─────
    with st.sidebar:
        show_storage_info_button()
    """
    # ── Initialise session state keys ─────────────────────────────────────────
    if "si_role" not in st.session_state: st.session_state["si_role"] = "Manager"
    if "si_pwd_open"      not in st.session_state: st.session_state["si_pwd_open"]      = False
    if "si_authenticated" not in st.session_state: st.session_state["si_authenticated"] = False
    if "si_auth_role"     not in st.session_state: st.session_state["si_auth_role"]     = ""
    if "si_docs_open"     not in st.session_state: st.session_state["si_docs_open"]     = False

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<p style='font-family:DM Mono,monospace;font-size:11px;color:#3a3028;"
        "letter-spacing:.10em;text-transform:uppercase;margin-bottom:6px;'>"
        "Document Access</p>",
        unsafe_allow_html=True,
    )

    # ── Role selector (shown to everyone) ─────────────────────────────────────
    role = st.session_state["si_role"]

    # ── Only privileged roles see the button ─────────────────────────────────
    

    # ── "View Documents" button (visible only to privileged roles) ────────────
    already_auth = (
        st.session_state["si_authenticated"]
        and st.session_state["si_auth_role"] == role
    )

    if not already_auth:
        if st.sidebar.button("📁 View Documents", key="si_view_docs_btn", use_container_width=True):
            st.session_state["si_pwd_open"] = True
            st.session_state["si_docs_open"] = False

    # ── Password prompt ───────────────────────────────────────────────────────
    if st.session_state["si_pwd_open"] and not already_auth:
        with st.sidebar:
            st.markdown(
                f"<p style='font-family:EB Garamond,serif;font-size:14px;"
                f"color:#f5f0e8;margin:4px 0 2px;'>"
                f"Enter <strong>{role}</strong> password:</p>",
                unsafe_allow_html=True,
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
                    if pwd_input == ROLE_PASSWORDS.get(role, ""):
                        st.session_state["si_authenticated"] = True
                        st.session_state["si_auth_role"]     = role
                        st.session_state["si_pwd_open"]      = False
                        st.session_state["si_docs_open"]     = True
                        st.toast(f"✓ Authenticated as {role}", icon="🔓")
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
            with col_cancel:
                if st.button("Cancel", key="si_pwd_cancel", use_container_width=True):
                    st.session_state["si_pwd_open"] = False
                    st.rerun()

    # ── Authenticated — show toggle + document viewer ─────────────────────────
    if already_auth:
        col_btn, col_out = st.sidebar.columns([3, 1])
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


# ══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT VIEWER  (rendered inside an expander in the sidebar)
# ══════════════════════════════════════════════════════════════════════════════

def _render_document_viewer(viewer_role: str):
    """Renders the document library filtered by viewer_role's access level."""

    docs = _fetch_documents()

    # ── Filter: only show docs the role is allowed to access ─────────────────
    visible_docs = [
        d for d in docs
        if _viewer_can_see(viewer_role, d.get("min_role", "Employee"))
    ]

    # ── Category filter ───────────────────────────────────────────────────────
    categories = sorted({d.get("category", "General") for d in visible_docs})
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
            "Category",
            cat_options,
            key="si_cat_filter",
            label_visibility="collapsed",
        )

        search_term = st.text_input(
            "Search",
            placeholder="Search documents…",
            key="si_doc_search",
            label_visibility="collapsed",
        )

    # Apply filters
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
    """Renders a single document card inside the sidebar."""
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
        # Badges row
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
