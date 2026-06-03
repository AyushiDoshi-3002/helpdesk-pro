"""
storage_info.py  -  Role-gated Document Viewer for HelpDesk Pro
Place this file in the same folder as app.py
"""

import streamlit as st
from datetime import datetime, timezone, timedelta

PRIVILEGED_ROLES = {"Manager", "Sr. Manager", "Tech Manager", "CTO", "CEO"}

ROLE_PASSWORDS = {
    "Manager":      "Mgr456",
    "Sr. Manager":  "SrMgr789",
    "Tech Manager": "Manager123",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

IST = timezone(timedelta(hours=5, minutes=30))


def _to_ist(dt_str):
    try:
        normalised = str(dt_str).strip().replace(" ", "T").replace("Z", "+00:00")
        if "+" not in normalised[10:] and normalised[-6] != "+":
            normalised += "+00:00"
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return str(dt_str)


def _get_db():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _fetch_documents():
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

_SENS_STYLE = {
    "Normal":       ("#3d5a4a", "#d4e8dc"),
    "Restricted":   ("#8b6914", "#f0e2b0"),
    "Confidential": ("#8b3a2a", "#f0e0db"),
    "Top Secret":   ("#f5f0e8", "#1a1612"),
}


def _viewer_can_see(viewer_role, doc_min_role):
    if viewer_role in ("CTO", "CEO"):
        return True
    return _ROLE_LEVEL.get(viewer_role, 0) >= _MIN_ROLE_LEVEL.get(doc_min_role, 0)


def show_storage_info_button():
    # Init session state
    for key, default in [
        ("si_role",          "Employee"),
        ("si_pwd_open",      False),
        ("si_authenticated", False),
        ("si_auth_role",     ""),
        ("si_docs_open",     False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<p style='font-family:DM Mono,monospace;font-size:11px;color:#9c8e82;"
        "letter-spacing:.10em;text-transform:uppercase;margin-bottom:6px;'>"
        "Document Access</p>",
        unsafe_allow_html=True,
    )

    all_roles = [
        "Employee", "Team Lead", "Manager",
        "Sr. Manager", "Tech Manager", "CTO", "CEO"
    ]

    selected_role = st.sidebar.selectbox(
        "Your role",
        all_roles,
        index=all_roles.index(st.session_state["si_role"]),
        key="si_role_select",
        label_visibility="collapsed",
    )

    # Reset auth if role changed
    if selected_role != st.session_state["si_role"]:
        st.session_state["si_role"]          = selected_role
        st.session_state["si_pwd_open"]      = False
        st.session_state["si_authenticated"] = False
        st.session_state["si_auth_role"]     = ""
        st.session_state["si_docs_open"]     = False
        st.rerun()

    role = st.session_state["si_role"]

    # Not a privileged role — show nothing
    if role not in PRIVILEGED_ROLES:
        st.sidebar.markdown(
            "<p style='font-family:EB Garamond,serif;font-size:13px;"
            "color:#6b5f55;font-style:italic;margin-top:4px;'>"
            "Document access not available for this role.</p>",
            unsafe_allow_html=True,
        )
        return

    already_auth = (
        st.session_state["si_authenticated"]
        and st.session_state["si_auth_role"] == role
    )

    # ── Not yet authenticated ─────────────────────────────────────────────────
    if not already_auth:
        if st.sidebar.button(
            "📁 View Documents",
            key="si_view_docs_btn",
            use_container_width=True,
        ):
            st.session_state["si_pwd_open"] = True
            st.rerun()

        if st.session_state["si_pwd_open"]:
            st.sidebar.markdown(
                f"<p style='font-family:EB Garamond,serif;font-size:13px;"
                f"color:#c8c0b8;margin:6px 0 2px;'>"
                f"Password for <strong>{role}</strong>:</p>",
                unsafe_allow_html=True,
            )
            pwd = st.sidebar.text_input(
                "pwd",
                type="password",
                key="si_pwd_input",
                label_visibility="collapsed",
                placeholder="Enter password…",
            )
            c1, c2 = st.sidebar.columns(2)
            with c1:
                if st.button("Confirm", key="si_pwd_ok", use_container_width=True):
                    if pwd == ROLE_PASSWORDS.get(role, ""):
                        st.session_state["si_authenticated"] = True
                        st.session_state["si_auth_role"]     = role
                        st.session_state["si_pwd_open"]      = False
                        st.session_state["si_docs_open"]     = True
                        st.rerun()
                    else:
                        st.sidebar.error("Incorrect password.")
            with c2:
                if st.button("Cancel", key="si_pwd_cancel", use_container_width=True):
                    st.session_state["si_pwd_open"] = False
                    st.rerun()
        return

    # ── Authenticated ─────────────────────────────────────────────────────────
    btn_label = "📂 Hide Documents" if st.session_state["si_docs_open"] else "📁 View Documents"

    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        if st.button(btn_label, key="si_toggle_btn", use_container_width=True):
            st.session_state["si_docs_open"] = not st.session_state["si_docs_open"]
            st.rerun()
    with col2:
        if st.button("🔒", key="si_signout_btn", use_container_width=True, help="Sign out"):
            st.session_state["si_authenticated"] = False
            st.session_state["si_auth_role"]     = ""
            st.session_state["si_docs_open"]     = False
            st.rerun()

    if not st.session_state["si_docs_open"]:
        return

    # ── Document viewer ───────────────────────────────────────────────────────
    docs = _fetch_documents()
    visible = [
        d for d in docs
        if _viewer_can_see(role, d.get("min_role", "Employee"))
    ]

    categories = sorted({d.get("category", "General") for d in visible})
    cat_opts   = ["All"] + categories

    st.sidebar.markdown(
        f"<p style='font-family:DM Mono,monospace;font-size:11px;color:#9c8e82;"
        f"letter-spacing:.06em;margin:6px 0 2px;'>"
        f"Viewing as <strong style='color:#f5f0e8'>{role}</strong> "
        f"· {len(visible)} doc(s)</p>",
        unsafe_allow_html=True,
    )

    sel_cat = st.sidebar.selectbox(
        "Filter category",
        cat_opts,
        key="si_cat_filter",
        label_visibility="collapsed",
    )

    search = st.sidebar.text_input(
        "Search",
        placeholder="Search…",
        key="si_search",
        label_visibility="collapsed",
    )

    filtered = visible
    if sel_cat != "All":
        filtered = [d for d in filtered if d.get("category") == sel_cat]
    if search.strip():
        kw = search.strip().lower()
        filtered = [
            d for d in filtered
            if kw in d.get("title", "").lower()
            or kw in (d.get("description") or "").lower()
        ]

    if not filtered:
        st.sidebar.markdown(
            "<p style='font-family:EB Garamond,serif;font-size:13px;"
            "color:#9c8e82;font-style:italic;'>No documents found.</p>",
            unsafe_allow_html=True,
        )
        return

    for doc in filtered:
        title       = doc.get("title", "Untitled")
        sensitivity = doc.get("sensitivity", "Normal")
        category    = doc.get("category", "General")
        description = doc.get("description") or ""
        preview     = doc.get("content_preview") or ""
        file_url    = doc.get("file_url") or ""
        owner       = doc.get("owner_id") or "—"
        created_at  = doc.get("created_at") or ""

        s_color, s_bg = _SENS_STYLE.get(sensitivity, ("#6b5f55", "#e8e0d0"))

        with st.sidebar.expander(f"📄 {title}"):
            st.markdown(
                f"<span style='font-family:DM Mono,monospace;font-size:10px;"
                f"background:#2a2420;color:#c8c0b8;border-radius:2px;"
                f"padding:2px 6px;letter-spacing:.06em;text-transform:uppercase;'>"
                f"{category}</span>"
                f"<span style='background:{s_bg};color:{s_color};"
                f"border-radius:2px;padding:2px 6px;font-size:10px;"
                f"font-family:DM Mono,monospace;font-weight:600;"
                f"letter-spacing:.08em;text-transform:uppercase;margin-left:4px;'>"
                f"{sensitivity}</span>",
                unsafe_allow_html=True,
            )

            if description:
                st.markdown(
                    f"<p style='font-family:EB Garamond,serif;font-size:13px;"
                    f"color:#c8c0b8;line-height:1.55;margin:6px 0;'>"
                    f"{description[:180]}{'…' if len(description)>180 else ''}</p>",
                    unsafe_allow_html=True,
                )

            if preview:
                st.markdown(
                    f"<div style='background:#2a2420;border-left:2px solid #8b3a2a;"
                    f"padding:8px 10px;margin:4px 0;font-family:EB Garamond,serif;"
                    f"font-size:12px;color:#c8c0b8;line-height:1.5;'>"
                    f"{preview[:300]}{'…' if len(preview)>300 else ''}</div>",
                    unsafe_allow_html=True,
                )

            if file_url:
                st.markdown(
                    f"<a href='{file_url}' target='_blank' "
                    f"style='font-family:DM Mono,monospace;font-size:11px;"
                    f"color:#c4543a;'>↗ Open document</a>",
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"<p style='font-family:DM Mono,monospace;font-size:10px;"
                f"color:#4a4038;margin-top:6px;'>"
                f"Owner: {owner} · {_to_ist(created_at) if created_at else '—'}</p>",
                unsafe_allow_html=True,
            )
