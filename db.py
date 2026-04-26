"""
Supabase database utilities for HelpDesk Pro.
"""
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
from typing import Optional

# ── SQL to create the tickets table (run once in Supabase SQL editor) ────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    job_role    TEXT NOT NULL,
    query       TEXT NOT NULL,
    priority    TEXT NOT NULL CHECK (priority IN ('High','Medium','Low')),
    status      TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','In Progress','Resolved')),
    admin_note  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
"""


@st.cache_resource(show_spinner=False)
def get_client() -> Optional[Client]:
    """Return a cached Supabase client, or None if creds are missing."""
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if url and key:
        return create_client(url, key)
    return None


# ── Ticket CRUD ──────────────────────────────────────────────────────────────

def create_ticket(user_id: str, job_role: str, query: str, priority: str) -> dict:
    """Insert a new ticket and return the created row."""
    db = get_client()
    if db is None:
        raise ConnectionError("Supabase is not configured. Check Setup page.")

    row = {
        "user_id":  user_id,
        "job_role": job_role,
        "query":    query,
        "priority": priority,
        "status":   "Open",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    result = db.table("tickets").insert(row).execute()
    return result.data[0] if result.data else {}


def get_all_tickets(status_filter: Optional[str] = None) -> list:
    """Fetch all tickets, optionally filtered by status."""
    db = get_client()
    if db is None:
        return []
    q = db.table("tickets").select("*").order("created_at", desc=True)
    if status_filter and status_filter != "All":
        q = q.eq("status", status_filter)
    return q.execute().data or []


def update_ticket(ticket_id: int, status: str, admin_note: str) -> dict:
    """Update ticket status and admin note."""
    db = get_client()
    if db is None:
        raise ConnectionError("Supabase is not configured.")
    result = (
        db.table("tickets")
        .update({
            "status":     status,
            "admin_note": admin_note,
            "updated_at": datetime.utcnow().isoformat(),
        })
        .eq("id", ticket_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def delete_ticket(ticket_id: int) -> None:
    db = get_client()
    if db:
        db.table("tickets").delete().eq("id", ticket_id).execute()


def ticket_stats() -> dict:
    """Return counts by status."""
    tickets = get_all_tickets()
    return {
        "total":       len(tickets),
        "open":        sum(1 for t in tickets if t["status"] == "Open"),
        "in_progress": sum(1 for t in tickets if t["status"] == "In Progress"),
        "resolved":    sum(1 for t in tickets if t["status"] == "Resolved"),
    }
