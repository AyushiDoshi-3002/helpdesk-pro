"""
doc_visibility.py  –  Hierarchy-based Document Visibility Control
══════════════════════════════════════════════════════════════════
HIERARCHY (lowest → highest):
  Team Member → Team Lead → Tech Manager → Manager → CTO → CEO

RULES:
  • CEO / CTO        → can view ALL documents instantly, no approval needed
  • Manager          → can request access; auto-approved (no chain), 7-day window
  • Tech Manager     → can request access; approved by Manager, 7-day window
  • Team Lead        → can request access; approved by Tech Manager → Manager
  • Team Member      → can request access; approved by Team Lead → Tech Manager

ACCESS EXPIRY:
  Every granted access (including CTO/CEO) is tracked with a 7-day window.
  After 7 days the record is marked Expired and access is revoked.

SUPABASE TABLE (run in SQL editor):
──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doc_visibility (
    id            BIGSERIAL PRIMARY KEY,
    doc_name      TEXT NOT NULL,
    doc_category  TEXT NOT NULL,
    sensitivity   TEXT NOT NULL DEFAULT 'Confidential',
    requester_id  TEXT NOT NULL,
    requester_role TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Pending',
    approved_by   TEXT,
    stage_idx     INTEGER NOT NULL DEFAULT 0,
    chain         JSONB NOT NULL DEFAULT '[]',
    granted_at    TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    history       JSONB NOT NULL DEFAULT '[]'
);
ALTER TABLE doc_visibility DISABLE ROW LEVEL SECURITY;
──────────────────────────────────────────────────────────────────
"""

import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# ── IST Timezone ──────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Supabase — reads from st.secrets (same as rest of app) ───────────────────
_TABLE = "doc_visibility"

# ── Role hierarchy (higher index = more authority) ────────────────────────────
ROLE_HIERARCHY = ["Team Member", "Team Lead", "Tech Manager", "Manager", "CTO", "CEO"]

# Roles that can approve AT each required level
# key = role being asked to approve, value = display label
APPROVER_PASSWORDS = {
    "Team Lead":    "Lead123",
    "Tech Manager": "Manager123",
    "Manager":      "Mgr456",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

# ── Approval chains per requester role ───────────────────────────────────────
# Team Member  → Team Lead → Tech Manager (2 levels)
# Team Lead    → Tech Manager → Manager   (2 levels)
# Tech Manager → Manager                  (1 level)
# Manager      → auto-approved            (0 levels — immediate)
# CTO          → auto-approved            (0 levels — immediate)
# CEO          → auto-approved            (0 levels — immediate)
def _build_visibility_chain(requester_role: str) -> list:
    chains = {
        "Team Member":  ["Team Lead", "Tech Manager"],
        "Team Lead":    ["Tech Manager", "Manager"],
        "Tech Manager": ["Manager"],
        "Manager":      [],
        "CTO":          [],
        "CEO":          [],
    }
    return chains.get(requester_role, ["Manager"])

def _is_auto_approved(requester_role: str) -> bool:
    return requester_role in ("Manager", "CTO", "CEO")

# ── Document catalog (mock — extend as needed) ────────────────────────────────
DOC_CATALOG = [
    # (doc_name, category, sensitivity)
    ("VPN Access Policy",              "Security",      "Top Secret"),
    ("Database Schema — Production",   "Technical",     "Confidential"),
    ("Employee Salary Bands",          "HR / Finance",  "Top Secret"),
    ("Q3 Financial Report",            "Finance",       "Confidential"),
    ("Infrastructure Runbook",         "Operations",    "Confidential"),
    ("Security Incident Response Plan","Security",      "Top Secret"),
    ("Cloud Architecture Diagram",     "Technical",     "Confidential"),
    ("CEO Board Presentation",         "Executive",     "Top Secret"),
    ("Team Onboarding Guide",          "General",       "Internal"),
    ("Product Roadmap 2026",           "Product",       "Confidential"),
    ("Penetration Test Report",        "Security",      "Top Secret"),
    ("API Gateway Credentials Guide",  "Technical",     "Confidential"),
    ("Customer PII Handling Policy",   "Legal",         "Top Secret"),
    ("Deployment Pipeline Guide",      "Operations",    "Internal"),
    ("HR Grievance Policy",            "HR / Finance",  "Internal"),
]

# Sensitivity → who can even request access
# Internal     → anyone
# Confidential → Team Lead and above
# Top Secret   → Tech Manager and above
SENSITIVITY_MIN_ROLE = {
    "Internal":     "Team Member",
    "Confidential": "Team Lead",
    "Top Secret":   "Tech Manager",
}

ACCESS_DAYS = 7  # access window in days

# ── Supabase client ───────────────────────────────────────────────────────────
@st.cache_resource
def _get_sb() -> Client:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    return create_client(url, key)

# ── Time helpers ──────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(IST)

def _fmt(dt) -> str:
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return str(dt)

def _to_utc_str(dt) -> str:
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return dt

def _from_str(s):
    if isinstance(s, str):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return s

def _days_left(expires_at) -> str:
    try:
        exp = _from_str(expires_at) if isinstance(expires_at, str) else expires_at
        secs = (exp - _now()).total_seconds()
        if secs <= 0:
            return "Expired"
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        return f"{d}d {h}h remaining" if d else f"{h}h remaining"
    except Exception:
        return "—"

def _is_expired(expires_at) -> bool:
    try:
        exp = _from_str(expires_at) if isinstance(expires_at, str) else expires_at
        return _now() > exp
    except Exception:
        return False

# ── DB helpers ────────────────────────────────────────────────────────────────
def _serialize(req: dict) -> dict:
    r = dict(req)
    r["created_at"] = _to_utc_str(r.get("created_at"))
    r["granted_at"] = _to_utc_str(r.get("granted_at")) if r.get("granted_at") else None
    r["expires_at"] = _to_utc_str(r.get("expires_at")) if r.get("expires_at") else None
    h = []
    for e in r.get("history", []):
        ee = dict(e)
        ee["time"] = _to_utc_str(ee.get("time"))
        h.append(ee)
    r["history"] = h
    if not isinstance(r.get("chain"), list):
        r["chain"] = []
    return r

def _deserialize(row: dict) -> dict:
    r = dict(row)
    r["created_at"] = _from_str(r.get("created_at"))
    r["granted_at"] = _from_str(r.get("granted_at")) if r.get("granted_at") else None
    r["expires_at"] = _from_str(r.get("expires_at")) if r.get("expires_at") else None
    h = []
    for e in (r.get("history") or []):
        ee = dict(e)
        ee["time"] = _from_str(ee.get("time"))
        h.append(ee)
    r["history"] = h
    if not isinstance(r.get("chain"), list):
        try:
            r["chain"] = json.loads(r["chain"]) if r.get("chain") else []
        except Exception:
            r["chain"] = []
    return r

def _db_insert(req: dict):
    try:
        res = _get_sb().table(_TABLE).insert(_serialize(req)).execute()
        if res.data:
            return res.data[0].get("id")
    except Exception as e:
        st.error(f"DB insert error: {e}")
    return None

def _db_update(req: dict):
    try:
        _get_sb().table(_TABLE).update(_serialize(req)).eq("id", req["id"]).execute()
    except Exception as e:
        st.error(f"DB update error: {e}")

def _db_load_all() -> list:
    try:
        res = _get_sb().table(_TABLE).select("*").order("created_at", desc=True).execute()
        return [_deserialize(r) for r in (res.data or [])]
    except Exception as e:
        st.error(f"DB load error: {e}")
        return []

def _db_delete(rid):
    try:
        _get_sb().table(_TABLE).delete().eq("id", rid).execute()
    except Exception as e:
        st.error(f"DB delete error: {e}")

# ── Session helpers ───────────────────────────────────────────────────────────
def _init():
    defaults = {
        "dv_requests": [],
        "dv_loaded": False,
        "dv_approver_auth": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _load():
    rows = _db_load_all()
    # Auto-expire any overdue records
    updated = []
    for r in rows:
        if r.get("status") == "Granted" and r.get("expires_at") and _is_expired(r["expires_at"]):
            r["status"] = "Expired"
            r["history"].append({"time": _now(), "by": "System", "action": "Access auto-expired after 7 days."})
            _db_update(r)
            updated.append(r["id"])
    st.session_state.dv_requests = rows
    st.session_state.dv_loaded = True

# ── Core actions ──────────────────────────────────────────────────────────────
def _create_request(doc_name, doc_category, sensitivity, requester_id, requester_role) -> dict:
    now   = _now()
    chain = _build_visibility_chain(requester_role)
    auto  = _is_auto_approved(requester_role)

    if auto:
        expires = now + timedelta(days=ACCESS_DAYS)
        req = {
            "doc_name":      doc_name,
            "doc_category":  doc_category,
            "sensitivity":   sensitivity,
            "requester_id":  requester_id,
            "requester_role": requester_role,
            "status":        "Granted",
            "approved_by":   "System (Auto)",
            "stage_idx":     0,
            "chain":         [],
            "granted_at":    now,
            "expires_at":    expires,
            "created_at":    now,
            "history": [
                {"time": now, "by": "System", "action": f"Requested by {requester_id} ({requester_role})."},
                {"time": now, "by": "System", "action": f"Auto-granted — {requester_role} has inherent access. Expires {_fmt(expires)}."},
            ],
        }
    else:
        req = {
            "doc_name":      doc_name,
            "doc_category":  doc_category,
            "sensitivity":   sensitivity,
            "requester_id":  requester_id,
            "requester_role": requester_role,
            "status":        "Pending",
            "approved_by":   None,
            "stage_idx":     0,
            "chain":         chain,
            "granted_at":    None,
            "expires_at":    None,
            "created_at":    now,
            "history": [
                {"time": now, "by": "System",
                 "action": f"Requested by {requester_id} ({requester_role}). Pending approval from {chain[0]}."},
            ],
        }

    new_id = _db_insert(req)
    req["id"] = new_id
    st.session_state.dv_requests.insert(0, req)
    return req

def _approve_request(req: dict, approver_role: str, note: str = ""):
    now      = _now()
    chain    = req["chain"]
    idx      = req["stage_idx"]
    next_idx = idx + 1

    req["history"].append({
        "time": now, "by": approver_role,
        "action": f"Approved{(' — ' + note) if note else ''}",
    })

    if next_idx >= len(chain):
        # All levels approved — grant access
        expires = now + timedelta(days=ACCESS_DAYS)
        req["status"]      = "Granted"
        req["approved_by"] = approver_role
        req["granted_at"]  = now
        req["expires_at"]  = expires
        req["history"].append({
            "time": now, "by": "System",
            "action": f"Access GRANTED. Expires {_fmt(expires)} (7 days).",
        })
    else:
        next_role = chain[next_idx]
        req["stage_idx"] = next_idx
        req["history"].append({
            "time": now, "by": "System",
            "action": f"Forwarded to {next_role} for approval.",
        })

    _db_update(req)

def _reject_request(req: dict, approver_role: str, note: str = ""):
    now = _now()
    req["status"] = "Rejected"
    req["history"].append({
        "time": now, "by": approver_role,
        "action": f"Rejected{(' — ' + note) if note else ''}",
    })
    _db_update(req)

def _revoke_access(req: dict):
    now = _now()
    req["status"] = "Revoked"
    req["history"].append({
        "time": now, "by": "Admin",
        "action": "Access manually revoked by admin.",
    })
    _db_update(req)

# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
/* Doc Visibility tab — Quarry palette extension */
.dv-hero {
    background: var(--paper, #faf7f2);
    border: 1px solid var(--border, #d4c9bc);
    border-top: 3px solid #8b3a2a;
    border-radius: 3px;
    padding: 24px 28px 20px;
    margin-bottom: 20px;
}
.dv-hero-title {
    font-family: 'Playfair Display', serif;
    font-size: 22px;
    font-weight: 700;
    color: #1a1612;
    margin: 0 0 6px;
}
.dv-hero-sub {
    font-family: 'EB Garamond', serif;
    font-size: 15px;
    color: #6b5f55;
    margin: 0;
}

/* Hierarchy ladder */
.hierarchy-bar {
    display: flex;
    align-items: center;
    gap: 0;
    flex-wrap: wrap;
    margin: 14px 0 0;
}
.hier-role {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 5px 12px;
    border-radius: 2px;
    border: 1px solid;
    margin: 2px;
}
.hier-tm   { background:#f5f0e8; color:#6b5f55; border-color:#d4c9bc; }
.hier-tl   { background:#e8e0d0; color:#3d3530; border-color:#b8a898; }
.hier-tech { background:#d4c9bc; color:#3d3530; border-color:#9c8e82; }
.hier-mgr  { background:#2d3d4f; color:#f5f0e8; border-color:#2d3d4f; }
.hier-cto  { background:#3d5a4a; color:#f5f0e8; border-color:#3d5a4a; }
.hier-ceo  { background:#8b3a2a; color:#f5f0e8; border-color:#8b3a2a; }
.hier-arrow{ font-size:14px; color:#9c8e82; margin:0 2px; }

/* Sensitivity badges */
.sens-internal     { background:#d4e8dc; color:#3d5a4a; border:1px solid #7ab898; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }
.sens-confidential { background:#f0e2b0; color:#8b6914; border:1px solid #d4b830; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }
.sens-topsecret    { background:#f0e0db; color:#8b3a2a; border:1px solid #c4543a; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }

/* Status badges */
.status-pending  { background:#f0e2b0; color:#8b6914; border:1px solid #d4b830; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }
.status-granted  { background:#d4e8dc; color:#3d5a4a; border:1px solid #7ab898; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }
.status-rejected { background:#f0e0db; color:#8b3a2a; border:1px solid #c4543a; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }
.status-expired  { background:#e8e0d0; color:#6b5f55; border:1px solid #b8a898; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }
.status-revoked  { background:#1a1612; color:#f5f0e8; border:1px solid #3d3530; font-family:'DM Mono',monospace; font-size:10px; padding:2px 8px; border-radius:2px; letter-spacing:0.06em; text-transform:uppercase; }

/* Doc card */
.doc-card {
    background: var(--paper, #faf7f2);
    border: 1px solid var(--border, #d4c9bc);
    border-radius: 3px;
    padding: 14px 18px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}
.doc-name {
    font-family: 'EB Garamond', serif;
    font-size: 16px;
    font-weight: 600;
    color: #1a1612;
}
.doc-cat {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: #9c8e82;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 2px;
}

/* Access timer chip */
.timer-chip-green {
    display:inline-block; background:#d4e8dc; border:1px solid #7ab898;
    border-radius:2px; padding:3px 10px; font-size:11px; color:#3d5a4a;
    font-family:'DM Mono',monospace; letter-spacing:0.04em; margin-top:4px;
}
.timer-chip-red {
    display:inline-block; background:#f0e0db; border:1px solid #c4543a;
    border-radius:2px; padding:3px 10px; font-size:11px; color:#8b3a2a;
    font-family:'DM Mono',monospace; letter-spacing:0.04em; margin-top:4px;
}

/* History entry */
.hist-entry {
    font-family:'EB Garamond',serif; font-size:14px; color:#3d3530;
    padding:6px 0; border-bottom:1px solid #ede7d9; line-height:1.6;
}
.hist-entry:last-child { border-bottom:none; }

/* Approver inbox card */
.inbox-card {
    background: var(--paper, #faf7f2);
    border: 1px solid var(--border, #d4c9bc);
    border-left: 3px solid #8b6914;
    border-radius: 3px;
    padding: 16px 20px;
    margin-bottom: 10px;
}

/* Auto-access banner */
.auto-banner {
    background: #d4e8dc;
    border: 1px solid #7ab898;
    border-left: 3px solid #3d5a4a;
    border-radius: 3px;
    padding: 14px 18px;
    margin-bottom: 16px;
    font-family: 'EB Garamond', serif;
    font-size: 15px;
    color: #3d5a4a;
}
</style>
"""

# ── Sensitivity badge helper ──────────────────────────────────────────────────
def _sens_badge(s: str) -> str:
    cls = {"Internal":"sens-internal","Confidential":"sens-confidential","Top Secret":"sens-topsecret"}.get(s,"sens-internal")
    return f"<span class='{cls}'>{s}</span>"

def _status_badge(s: str) -> str:
    cls = {"Pending":"status-pending","Granted":"status-granted","Rejected":"status-rejected",
           "Expired":"status-expired","Revoked":"status-revoked"}.get(s,"status-pending")
    return f"<span class='{cls}'>{s}</span>"

def _role_rank(role: str) -> int:
    try:
        return ROLE_HIERARCHY.index(role)
    except ValueError:
        return 0

def _can_request(requester_role: str, sensitivity: str) -> bool:
    min_role = SENSITIVITY_MIN_ROLE.get(sensitivity, "Team Member")
    return _role_rank(requester_role) >= _role_rank(min_role)

# ── Main page ─────────────────────────────────────────────────────────────────
def page_doc_visibility():
    _init()
    st.markdown(_CSS, unsafe_allow_html=True)

    if not st.session_state.dv_loaded:
        _load()

    # ── Hero ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class='dv-hero'>
      <p class='dv-hero-title'>Document Visibility Control</p>
      <p class='dv-hero-sub'>
        Role-based access to sensitive documents. All access grants are valid for
        <strong>7 days</strong> and expire automatically.
        CTO &amp; CEO have inherent access to all documents.
      </p>
      <div class='hierarchy-bar'>
        <span class='hier-role hier-tm'>Team Member</span>
        <span class='hier-arrow'>→</span>
        <span class='hier-role hier-tl'>Team Lead</span>
        <span class='hier-arrow'>→</span>
        <span class='hier-role hier-tech'>Tech Manager</span>
        <span class='hier-arrow'>→</span>
        <span class='hier-role hier-mgr'>Manager</span>
        <span class='hier-arrow'>→</span>
        <span class='hier-role hier-cto'>CTO</span>
        <span class='hier-arrow'>→</span>
        <span class='hier-role hier-ceo'>CEO</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    pending_count = sum(
        1 for r in st.session_state.dv_requests
        if r.get("status") == "Pending"
    )

    tab1, tab2, tab3 = st.tabs([
        "📂 Request Document Access",
        f"🔑 Approver Inbox ({pending_count})",
        "📋 All Access Records",
    ])

    with tab1:
        _tab_request()
    with tab2:
        _tab_approver_inbox()
    with tab3:
        _tab_all_records()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Request Access
# ══════════════════════════════════════════════════════════════════════════════
def _tab_request():
    st.markdown("### Request Document Access")
    st.markdown(
        "<p style='font-family:EB Garamond,serif;font-size:15px;color:#6b5f55;'>"
        "Select a document and your role. CTO &amp; CEO get immediate access. "
        "Others go through the approval chain.</p>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        employee_id = st.text_input("Employee ID *", placeholder="e.g. EMP-042", key="dv_emp_id")
        requester_role = st.selectbox("Your Role *", ROLE_HIERARCHY, key="dv_role")

    with c2:
        # Filter docs the role can access based on sensitivity
        eligible_docs = [
            (name, cat, sens) for name, cat, sens in DOC_CATALOG
            if _can_request(requester_role, sens)
        ]
        if not eligible_docs:
            st.warning("No documents available for your role level.")
            return

        doc_options = [f"{name}  [{sens}]" for name, cat, sens in eligible_docs]
        selected_idx = st.selectbox(
            "Select Document *",
            range(len(doc_options)),
            format_func=lambda i: doc_options[i],
            key="dv_doc_select",
        )
        doc_name, doc_cat, doc_sens = eligible_docs[selected_idx]

    # Show chain preview
    chain = _build_visibility_chain(requester_role)
    auto  = _is_auto_approved(requester_role)

    if auto:
        st.markdown(
            f"<div class='auto-banner'>"
            f"✓ As <strong>{requester_role}</strong>, you have inherent access. "
            f"Clicking Submit will immediately grant access for <strong>7 days</strong>."
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        chain_html = " → ".join(
            f"<span style='font-family:DM Mono,monospace;font-size:12px;"
            f"background:#e8e0d0;padding:3px 8px;border-radius:2px;color:#3d3530;'>{r}</span>"
            for r in chain
        )
        st.markdown(
            f"<p style='font-family:EB Garamond,serif;font-size:14px;color:#6b5f55;margin-top:8px;'>"
            f"Approval chain: {chain_html}</p>",
            unsafe_allow_html=True,
        )

    reason = st.text_area(
        "Reason for access *",
        placeholder="Briefly explain why you need access to this document…",
        height=90,
        key="dv_reason",
    )

    if st.button("Submit Access Request →", key="dv_submit_req"):
        errors = []
        if not employee_id.strip(): errors.append("Employee ID required.")
        if not reason.strip():      errors.append("Reason required.")
        for e in errors:
            st.error(e)
        if not errors:
            req = _create_request(doc_name, doc_cat, doc_sens, employee_id.strip(), requester_role)
            if req.get("status") == "Granted":
                st.success(
                    f"✓ Access granted immediately to **{doc_name}**. "
                    f"Expires {_fmt(req['expires_at'])}."
                )
            else:
                st.success(
                    f"Request submitted. Pending approval from **{chain[0]}**. "
                    f"You will be notified when access is granted."
                )
            st.rerun()

    # ── My access records (lookup by employee ID) ─────────────────────────────
    lookup_id = st.text_input(
        "Check my access status (Employee ID)",
        placeholder="Enter your Employee ID to see your requests",
        key="dv_lookup",
    )
    if lookup_id.strip():
        my_reqs = [
            r for r in st.session_state.dv_requests
            if r.get("requester_id","").lower() == lookup_id.strip().lower()
        ]
        if not my_reqs:
            st.info("No access requests found for this Employee ID.")
        else:
            st.markdown(f"**{len(my_reqs)} request(s) for {lookup_id.strip()}:**")
            for r in my_reqs:
                _render_request_card(r, show_actions=False, ctx="my")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Approver Inbox
# ══════════════════════════════════════════════════════════════════════════════
def _tab_approver_inbox():
    st.markdown("### Approver Inbox")
    st.markdown(
        "<p style='font-family:EB Garamond,serif;font-size:15px;color:#6b5f55;'>"
        "Log in as an approver to view and action pending requests assigned to your role.</p>",
        unsafe_allow_html=True,
    )

    approver_roles = ["Team Lead", "Tech Manager", "Manager", "CTO", "CEO"]

    for role in approver_roles:
        with st.expander(f"{'🔓' if st.session_state.dv_approver_auth.get(role) else '🔒'} {role} Inbox"):
            if not st.session_state.dv_approver_auth.get(role):
                pwd = st.text_input("Password", type="password", key=f"dv_pwd_{role}")
                if st.button("Log in →", key=f"dv_login_{role}"):
                    if pwd == APPROVER_PASSWORDS.get(role, ""):
                        st.session_state.dv_approver_auth[role] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                continue

            # Logged in
            col_hd, col_lo = st.columns([5, 1])
            with col_lo:
                if st.button("Log out", key=f"dv_logout_{role}"):
                    st.session_state.dv_approver_auth[role] = False
                    st.rerun()

            # Requests waiting for THIS role at the current stage
            pending = [
                r for r in st.session_state.dv_requests
                if r.get("status") == "Pending"
                and r.get("chain")
                and r["chain"][r.get("stage_idx", 0)] == role
            ]

            if not pending:
                st.success("✓ No pending requests for your role.")
            else:
                st.markdown(f"**{len(pending)} pending request(s):**")
                for req in pending:
                    _render_request_card(req, show_actions=True, ctx=f"inbox_{role}", approver_role=role)

            # Previously handled
            handled = [
                r for r in st.session_state.dv_requests
                if any(e.get("by") == role for e in r.get("history", []))
                and r.get("status") != "Pending"
            ]
            if handled:
                st.markdown(f"<small style='color:#9c8e82;font-family:DM Mono,monospace;'>{len(handled)} previously handled</small>", unsafe_allow_html=True)
                for req in handled[:5]:
                    _render_request_card(req, show_actions=False, ctx=f"done_{role}")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — All Records (Admin view)
# ══════════════════════════════════════════════════════════════════════════════
def _tab_all_records():
    if not st.session_state.get("admin_logged_in"):
        st.warning("Please log in via the Admin Panel to view all records.")
        return

    st.markdown("### All Document Access Records")

    c1, c2, c3 = st.columns(3)
    with c1:
        sf = st.selectbox("Status", ["All", "Pending", "Granted", "Rejected", "Expired", "Revoked"], key="dv_sf")
    with c2:
        rf = st.selectbox("Role", ["All"] + ROLE_HIERARCHY, key="dv_rf")
    with c3:
        search = st.text_input("Search doc / employee", key="dv_search_all")

    reqs = list(st.session_state.dv_requests)
    if sf != "All":
        reqs = [r for r in reqs if r.get("status") == sf]
    if rf != "All":
        reqs = [r for r in reqs if r.get("requester_role") == rf]
    if search.strip():
        kw = search.strip().lower()
        reqs = [r for r in reqs if kw in r.get("doc_name","").lower() or kw in r.get("requester_id","").lower()]

    # Stats
    all_reqs = st.session_state.dv_requests
    s_counts = {}
    for r in all_reqs:
        s_counts[r.get("status","?")] = s_counts.get(r.get("status","?"), 0) + 1

    cols = st.columns(5)
    for col, (label, key) in zip(cols, [
        ("Total", None), ("Granted", "Granted"), ("Pending", "Pending"),
        ("Expired", "Expired"), ("Rejected", "Rejected"),
    ]):
        val = len(all_reqs) if key is None else s_counts.get(key, 0)
        col.markdown(
            f"<div class='metric-card'>"
            f"<div class='metric-number'>{val}</div>"
            f"<div class='metric-label'>{label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    if not reqs:
        st.info("No records match your filters.")
        return

    st.markdown(
        f"<p style='font-family:DM Mono,monospace;font-size:11px;color:#9c8e82;"
        f"letter-spacing:0.06em;text-transform:uppercase;'>{len(reqs)} record(s)</p>",
        unsafe_allow_html=True,
    )

    for req in reqs:
        _render_request_card(req, show_actions=False, ctx="admin", admin_mode=True)

    # Refresh button
    st.markdown("---")
    if st.button("↻ Refresh Records", key="dv_refresh"):
        _load()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  Shared card renderer
# ══════════════════════════════════════════════════════════════════════════════
def _render_request_card(req: dict, show_actions: bool, ctx: str, approver_role: str = "", admin_mode: bool = False):
    rid    = req.get("id", "?")
    status = req.get("status", "Pending")
    chain  = req.get("chain", [])
    idx    = req.get("stage_idx", 0)
    stage  = chain[idx] if chain and idx < len(chain) else "—"

    # Time left chip
    if status == "Granted" and req.get("expires_at"):
        dl = _days_left(req["expires_at"])
        chip_cls = "timer-chip-red" if "h" in dl and "d" not in dl else "timer-chip-green"
        timer_html = f"<span class='{chip_cls}'>⏱ {dl}</span>"
    elif status == "Pending":
        timer_html = "<span class='status-pending'>Awaiting approval</span>"
    else:
        timer_html = ""

    label = (
        f"#{rid} · {req.get('doc_name','?')} · "
        f"{req.get('requester_id','?')} ({req.get('requester_role','?')}) · "
        f"{status}"
    )

    with st.expander(label, expanded=show_actions):
        # Header row
        hcol1, hcol2 = st.columns([3, 1])
        with hcol1:
            st.markdown(
                f"{_status_badge(status)} &nbsp; {_sens_badge(req.get('sensitivity','Internal'))}",
                unsafe_allow_html=True,
            )
            if timer_html:
                st.markdown(timer_html, unsafe_allow_html=True)
        with hcol2:
            if status == "Granted" and req.get("expires_at"):
                st.markdown(
                    f"<small style='font-family:DM Mono,monospace;font-size:10px;color:#9c8e82;'>"
                    f"Expires<br>{_fmt(req['expires_at'])}</small>",
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # Details
        d1, d2, d3 = st.columns(3)
        d1.markdown(f"**Document**\n\n{req.get('doc_name','—')}")
        d2.markdown(f"**Category**\n\n{req.get('doc_category','—')}")
        d3.markdown(f"**Requester**\n\n{req.get('requester_id','—')} ({req.get('requester_role','—')})")

        d4, d5, d6 = st.columns(3)
        d4.markdown(f"**Status**\n\n{status}")
        d5.markdown(f"**Current Stage**\n\n{stage if status == 'Pending' else '—'}")
        d6.markdown(f"**Approved By**\n\n{req.get('approved_by') or '—'}")

        if chain:
            st.markdown("**Approval chain progress:**")
            parts = []
            for i, role in enumerate(chain):
                if status == "Granted" or i < idx:
                    parts.append(f"~~{role}~~ ✅")
                elif i == idx and status == "Pending":
                    parts.append(f"**{role} ⏳**")
                else:
                    parts.append(role)
            st.markdown("  →  ".join(parts))

        # History
        with st.expander("📜 History", key=f"dv_hist_{rid}_{ctx}"):
            for entry in req.get("history", []):
                t      = _fmt(entry.get("time", ""))
                action = entry.get("action", "")
                by     = entry.get("by", "?")
                st.markdown(
                    f"<div class='hist-entry'>`{t}` &nbsp; <strong>{by}</strong>: {action}</div>",
                    unsafe_allow_html=True,
                )

        # Approver actions
        if show_actions and status == "Pending":
            st.markdown("---")
            note = st.text_input("Note (optional)", key=f"dv_note_{rid}_{ctx}", placeholder="Reason or comment…")
            ac1, ac2, _ = st.columns([1, 1, 4])
            with ac1:
                if st.button("✅ Approve", key=f"dv_ap_{rid}_{ctx}", type="primary", use_container_width=True):
                    _approve_request(req, approver_role, note)
                    st.rerun()
            with ac2:
                if st.button("❌ Reject", key=f"dv_rj_{rid}_{ctx}", use_container_width=True):
                    _reject_request(req, approver_role, note)
                    st.rerun()

        # Admin revoke
        if admin_mode and status == "Granted":
            st.markdown("---")
            if st.button(f"🚫 Revoke Access — #{rid}", key=f"dv_revoke_{rid}_{ctx}"):
                _revoke_access(req)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  SQL for Supabase (reference)
# ══════════════════════════════════════════════════════════════════════════════
DOC_VISIBILITY_SCHEMA_SQL = """
-- Run this in Supabase SQL Editor
CREATE TABLE IF NOT EXISTS doc_visibility (
    id            BIGSERIAL PRIMARY KEY,
    doc_name      TEXT NOT NULL,
    doc_category  TEXT NOT NULL,
    sensitivity   TEXT NOT NULL DEFAULT 'Confidential',
    requester_id  TEXT NOT NULL,
    requester_role TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Pending',
    approved_by   TEXT,
    stage_idx     INTEGER NOT NULL DEFAULT 0,
    chain         JSONB NOT NULL DEFAULT '[]',
    granted_at    TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    history       JSONB NOT NULL DEFAULT '[]'
);
ALTER TABLE doc_visibility DISABLE ROW LEVEL SECURITY;
"""
