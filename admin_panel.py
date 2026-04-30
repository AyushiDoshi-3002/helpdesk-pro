"""
Admin Panel – view, update, and resolve support tickets.
"""
import streamlit as st
import db
from datetime import datetime, timezone, timedelta


ADMIN_PASSWORD = "admin123"   # Change in production / move to st.secrets

# ── IST Timezone (UTC+5:30) ───────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

def _to_ist(dt_str: str) -> str:
    """Convert a UTC ISO string → formatted IST string."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return dt_str


def show():
    # ── Auth Gate ─────────────────────────────────────────────────────────────
    if not st.session_state.get("admin_logged_in"):
        _login()
        return

    _dashboard()


# ── Login ─────────────────────────────────────────────────────────────────────

def _login():
    st.markdown("# 🛡️ Admin Panel")
    st.markdown("---")
    col, _ = st.columns([1.5, 2.5])
    with col:
        st.markdown(
            "<div class='card'><h3 style='font-family:Syne,sans-serif'>Admin Login</h3>",
            unsafe_allow_html=True,
        )
        pwd = st.text_input("Password", type="password", placeholder="Enter admin password")
        if st.button("Login →", use_container_width=True):
            secret_pwd = st.secrets.get("ADMIN_PASSWORD", ADMIN_PASSWORD)
            if pwd == secret_pwd:
                st.session_state["admin_logged_in"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.markdown("</div>", unsafe_allow_html=True)


# ── Main Dashboard ────────────────────────────────────────────────────────────

def _dashboard():
    col_title, col_logout = st.columns([5, 1])
    with col_title:
        st.markdown("# 🛡️ Admin Dashboard")
    with col_logout:
        if st.button("Logout"):
            st.session_state["admin_logged_in"] = False
            st.rerun()

    # Stats row
    try:
        stats = db.ticket_stats()
        c1, c2, c3, c4 = st.columns(4)
        _metric_card(c1, stats["total"],       "Total Tickets",  "📋")
        _metric_card(c2, stats["open"],        "Open",           "🟡")
        _metric_card(c3, stats["in_progress"], "In Progress",    "🔵")
        _metric_card(c4, stats["resolved"],    "Resolved",       "🟢")
    except Exception as e:
        st.error(f"Could not load stats: {e}")

    st.markdown("---")

    # Filter bar
    col_f1, col_f2, _ = st.columns([1.5, 1.5, 3])
    with col_f1:
        status_filter = st.selectbox("Filter by Status", ["All", "Open", "In Progress", "Resolved"])
    with col_f2:
        priority_filter = st.selectbox("Filter by Priority", ["All", "High", "Medium", "Low"])

    st.markdown("---")

    # Load tickets
    try:
        tickets = db.get_all_tickets(status_filter if status_filter != "All" else None)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if priority_filter != "All":
        tickets = [t for t in tickets if t.get("priority") == priority_filter]

    if not tickets:
        st.info("No tickets found for the selected filters.", icon="📭")
        return

    st.markdown(f"**{len(tickets)} ticket(s) found**")

    for ticket in tickets:
        _ticket_card(ticket)


def _metric_card(col, value, label, icon):
    with col:
        st.markdown(
            f"<div class='metric-card'>"
            f"<div style='font-size:28px'>{icon}</div>"
            f"<div class='metric-number'>{value}</div>"
            f"<div class='metric-label'>{label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _ticket_card(ticket):
    tid = ticket.get("id")
    status = ticket.get("status", "Open")
    priority = ticket.get("priority", "Medium")
    created = ticket.get("created_at", "")

    # ✅ Format date in IST
    created_fmt = _to_ist(created)

    # Status badge
    badge_cls = {
        "Open":        "badge-open",
        "In Progress": "badge-inprogress",
        "Resolved":    "badge-resolved",
    }.get(status, "badge-open")

    prio_cls = {
        "High":   "prio-high",
        "Medium": "prio-medium",
        "Low":    "prio-low",
    }.get(priority, "prio-medium")

    with st.expander(
        f"🎫 Ticket #{tid} — {ticket.get('user_id','?')} ({ticket.get('job_role','?')}) "
        f"| {status} | {priority} | {created_fmt}",
        expanded=False,
    ):
        st.markdown(
            f"<span class='{badge_cls}'>{status}</span>&nbsp;&nbsp;"
            f"<span class='{prio_cls}'>{priority}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**Employee ID:** {ticket.get('user_id','–')}")
        st.markdown(f"**Job Role:** {ticket.get('job_role','–')}")
        st.markdown(f"**Submitted:** {created_fmt}")
        st.markdown("**Problem Description:**")
        st.markdown(
            f"<div class='answer-box'>{ticket.get('query','–')}</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("**Admin Response**")

        col1, col2 = st.columns(2)
        with col1:
            new_status = st.selectbox(
                "Update Status",
                ["Open", "In Progress", "Resolved"],
                index=["Open", "In Progress", "Resolved"].index(status),
                key=f"status_{tid}",
            )
        with col2:
            admin_note = st.text_area(
                "Admin Note / Response",
                value=ticket.get("admin_note") or "",
                placeholder="Write your response or internal note here…",
                key=f"note_{tid}",
                height=100,
            )

        col_update, col_delete, _ = st.columns([1, 1, 3])
        with col_update:
            if st.button("💾 Save", key=f"save_{tid}", use_container_width=True):
                try:
                    db.update_ticket(tid, new_status, admin_note)
                    st.success("Ticket updated!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        with col_delete:
            if st.button("🗑️ Delete", key=f"del_{tid}", use_container_width=True):
                try:
                    db.delete_ticket(tid)
                    st.warning("Ticket deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
