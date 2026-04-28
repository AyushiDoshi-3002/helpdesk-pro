"""
utils.py – shared helpers for the Smart Approval Pipeline
"""
import streamlit as st
from datetime import datetime

ADMIN_PASSWORD = "admin123"
MODEL = "claude-sonnet-4-20250514"

CHANGE_TYPES = {
    "Documentation Update": {"risk": "Low",    "needs_ceo": False, "auto_senior": True,  "category": "docs"},
    "Code Change":          {"risk": "Medium", "needs_ceo": False, "auto_senior": False, "category": "tech"},
    "Security Patch":       {"risk": "High",   "needs_ceo": True,  "auto_senior": False, "category": "security"},
    "API Change":           {"risk": "High",   "needs_ceo": True,  "auto_senior": False, "category": "api"},
    "Financial Report":     {"risk": "High",   "needs_ceo": True,  "auto_senior": False, "category": "finance"},
    "Policy Document":      {"risk": "Medium", "needs_ceo": False, "auto_senior": False, "category": "policy"},
    "Employee Data":        {"risk": "High",   "needs_ceo": True,  "auto_senior": False, "category": "hr"},
    "Vendor Contract":      {"risk": "Medium", "needs_ceo": False, "auto_senior": False, "category": "legal"},
    "System Architecture":  {"risk": "High",   "needs_ceo": False, "auto_senior": False, "category": "tech"},
}

CAT_LABELS = {
    "docs":     "Internal Documentation",
    "tech":     "Technical Change",
    "security": "Security-Critical",
    "api":      "External API / Integration",
    "finance":  "Financial Data",
    "policy":   "Policy / Compliance",
    "hr":       "People & HR",
    "legal":    "Legal / Vendor",
}

AGENTS = [
    {"id": "classifier", "label": "System Classifier", "icon": "🔍", "desc": "Reads change type, assigns risk, determines routing"},
    {"id": "senior",     "label": "Senior Agent",       "icon": "👨‍💼", "desc": "Reviews edit quality — may auto-pass low-risk"},
    {"id": "techlead",   "label": "Tech Lead Agent",    "icon": "🧑‍🔧", "desc": "Validates technical safety, writes CTO/CEO briefing"},
    {"id": "cto",        "label": "CTO / CEO Agent",    "icon": "🏛️",  "desc": "Reads briefing, decides to approve or escalate"},
    {"id": "human",      "label": "Your Approval",      "icon": "✅",  "desc": "THE ONLY MANUAL STEP — approve or reject here", "manual": True},
    {"id": "kb",         "label": "KB Sync",            "icon": "📚",  "desc": "Auto-triggered on approval → writes to knowledge base"},
]

# ── DB helpers ────────────────────────────────────────────────────────────────

def create_task(data: dict) -> dict:
    task = {
        "id": st.session_state.next_id,
        **data,
        "stage": "classifier",
        "status": "Classifying",
        "risk_level": "Pending",
        "stage_results": {
            "junior": {
                "agent": "Junior Agent",
                "decision": "Approved",
                "reason": f"Submitted by {data.get('requester', '?')}",
            }
        },
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "reviewer_note": "",
    }
    st.session_state.db.append(task)
    st.session_state.next_id += 1
    return task


def update_task(task_id: int, patch: dict):
    for t in st.session_state.db:
        if t["id"] == task_id:
            t.update(patch)
            t["updated_at"] = datetime.now().isoformat()
            return


def delete_task(task_id: int):
    st.session_state.db = [t for t in st.session_state.db if t["id"] != task_id]


def get_by_status(status: str) -> list:
    return [t for t in st.session_state.db if t["status"] == status]


def get_all(filter_status: str = "All") -> list:
    if filter_status and filter_status != "All":
        return [t for t in reversed(st.session_state.db) if t["status"] == filter_status]
    return list(reversed(st.session_state.db))


def get_stats() -> dict:
    db = st.session_state.db
    progress_set = {"Classifying", "Senior Review", "TechLead Review", "CTO Review", "CEO Review"}
    return {
        "total":    len(db),
        "progress": sum(1 for t in db if t["status"] in progress_set),
        "awaiting": sum(1 for t in db if t["status"] == "Awaiting Approval"),
        "approved": sum(1 for t in db if t["status"] in ("Approved", "Done")),
        "rejected": sum(1 for t in db if t["status"] == "Rejected"),
    }


def fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return iso or "—"


def risk_color(risk: str) -> str:
    return {"Low": "🟢", "Medium": "🟡", "High": "🔴", "Critical": "🔴", "Pending": "⚪"}.get(risk, "⚪")


def status_emoji(status: str) -> str:
    return {
        "Classifying":       "🔍",
        "Senior Review":     "👨‍💼",
        "TechLead Review":   "🧑‍🔧",
        "CTO Review":        "🏛️",
        "CEO Review":        "🏛️",
        "Awaiting Approval": "⏳",
        "Approved":          "✅",
        "Rejected":          "❌",
        "Done":              "🎉",
    }.get(status, "❓")
