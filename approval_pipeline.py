"""
approval_pipeline.py  –  role-based tabs + Supabase persistence + AI Assistant
                          + Auto-escalation: 1 week (168h) per level
────────────────────────────────────────────────────────────────────────────────
ESCALATION RULE:
  Each approver has 168 hours (7 days / 1 week) to respond.
  If they don't, the request moves UP ONE LEVEL in the chain.
  This repeats at each level until the final approver.
  Only when the final approver also times out does the request Expire.

  Example for Technical doc (chain: Team Lead → Tech Manager → CTO):
    Team Lead ignores for 7 days    → escalates to Tech Manager
    Tech Manager ignores for 7 days → escalates to CTO
    CTO ignores for 7 days          → Expired

TO TEST QUICKLY (without waiting a week):
  Change ESCALATION_HOURS = 0.05  (fires in ~3 minutes)
  Submit a request, wait 3 min, click Refresh → escalation fires instantly.
  Change back to 168 before going live.
"""

import json
import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# ── IST Timezone (UTC+5:30) ───────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Supabase config ───────────────────────────────────────────────────────────
SUPABASE_URL = "https://jvulbphmksdebkkkhgvh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dWxicGhta3NkZWJra2toZ3ZoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxOTg4ODQsImV4cCI6MjA5Mjc3NDg4NH0.REhaZ0M8pg_9hkaIJxYNmErIsy6UARTYyzYkQbr0pT4"
TABLE = "ap_requests"

# ── Role passwords ────────────────────────────────────────────────────────────
ROLE_PASSWORDS = {
    "Team Lead":    "Lead123",
    "Tech Manager": "Manager123",
    "CTO":          "CTO123",
    "CEO":          "CEO123",
}

# ── Escalation timer ──────────────────────────────────────────────────────────
# 168h = 7 days = 1 week. Change to 0.05 for ~3-minute testing.
ESCALATION_HOURS = 168

def _escalation_label():
    """Returns a readable label like '1 week (168h)' or '2 days (48h)'."""
    if ESCALATION_HOURS >= 168 and ESCALATION_HOURS % 168 == 0:
        w = int(ESCALATION_HOURS // 168)
        return f"{w} week{'s' if w > 1 else ''} ({int(ESCALATION_HOURS)}h)"
    elif ESCALATION_HOURS >= 24:
        d = int(ESCALATION_HOURS // 24)
        return f"{d} day{'s' if d > 1 else ''} ({int(ESCALATION_HOURS)}h)"
    else:
        return f"{ESCALATION_HOURS}h"

# ── Document taxonomy ─────────────────────────────────────────────────────────
DOC_CATEGORIES = {
    "Security": {
        "label":    "🔒 Security",
        "subtypes": ["Legal", "Compliance", "Public API", "Financial"],
        "approver": "CEO",
        "auto":     False,
    },
    "Technical": {
        "label":    "⚙️ Technical",
        "subtypes": ["Architecture", "Database", "Tech Stack", "Infrastructure", "Code Standards"],
        "approver": "CTO",
        "auto":     False,
    },
    "Operations": {
        "label":    "🔧 Operations",
        "subtypes": ["Runbooks", "Deployment", "Monitoring", "Setup Guides"],
        "approver": "Tech Manager",
        "auto":     False,
    },
    "Team": {
        "label":    "👥 Team",
        "subtypes": ["Internal Processes", "Troubleshooting", "Setup Guides"],
        "approver": "Team Lead",
        "auto":     False,
    },
    "General": {
        "label":    "📄 General",
        "subtypes": ["FAQs", "Onboarding", "General Info"],
        "approver": "Admin",
        "auto":     True,
    },
}

# ── Approval chains ───────────────────────────────────────────────────────────
# ESCALATION: moves ONE level up after ESCALATION_HOURS of inactivity.
# Each level gets a fresh ESCALATION_HOURS window.
#
# Technical:  Team Lead → Tech Manager → CTO
# Security:   Team Lead → Tech Manager → CTO → CEO
# Operations: Team Lead → Tech Manager
# Team:       Team Lead only
# General:    Auto-approved (no chain)
_CHAINS = {
    "CEO":          ["Team Lead", "Tech Manager", "CTO", "CEO"],
    "CTO":          ["Team Lead", "Tech Manager", "CTO"],
    "Tech Manager": ["Team Lead", "Tech Manager"],
    "Team Lead":    ["Team Lead"],
    "Admin":        [],
}

def _build_chain(category: str) -> list:
    cfg = DOC_CATEGORIES.get(category, {})
    return list(_CHAINS.get(cfg.get("approver", "Team Lead"), ["Team Lead"]))


# ── Supabase client ───────────────────────────────────────────────────────────

@st.cache_resource
def _get_sb() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _dt_to_str(dt):
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return dt

def _str_to_dt(s):
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    if isinstance(s, str):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return s

def _serialize(req: dict) -> dict:
    row = dict(req)
    row["created_at"] = _dt_to_str(row.get("created_at"))
    row["expires_at"] = _dt_to_str(row.get("expires_at"))
    history = []
    for entry in row.get("history", []):
        e = dict(entry)
        e["time"] = _dt_to_str(e.get("time"))
        history.append(e)
    row["history"] = history
    return row

def _deserialize(row: dict) -> dict:
    req = dict(row)
    req["created_at"] = _str_to_dt(req.get("created_at"))
    req["expires_at"] = _str_to_dt(req.get("expires_at"))
    history = []
    for entry in (req.get("history") or []):
        e = dict(entry)
        e["time"] = _str_to_dt(e.get("time"))
        history.append(e)
    req["history"] = history
    if not isinstance(req.get("chain"), list):
        req["chain"] = json.loads(req["chain"]) if req.get("chain") else []
    return req

def _migrate_chain(req: dict) -> bool:
    """
    Fix records created with the old broken chains (e.g. Technical had ["Team Lead","CTO"],
    skipping Tech Manager). Repairs the chain in-place and patches stage_idx if needed.
    Returns True if a fix was applied (so caller can persist it).
    """
    if req.get("done"):
        return False
    category = req.get("category","")
    correct  = _build_chain(category)
    current  = req.get("chain", [])
    if current == correct:
        return False  # already correct

    old_role = current[req["stage_idx"]] if req["stage_idx"] < len(current) else None
    req["chain"] = correct
    # Keep stage_idx pointing at the same role if possible, else reset to 0
    if old_role and old_role in correct:
        req["stage_idx"] = correct.index(old_role)
    else:
        req["stage_idx"] = 0
    req["history"].append({
        "time":   _now(),
        "by":     "System",
        "action": (
            f"🔧 Chain auto-corrected from [{', '.join(current)}] "
            f"to [{', '.join(correct)}]. Stage: {correct[req['stage_idx']]}."
        ),
    })
    return True


def _db_insert(req):
    try:
        res = _get_sb().table(TABLE).insert(_serialize(req)).execute()
        if res.data:
            st.toast(f"✅ Saved: {req['id']}", icon="🗄️")
    except Exception as e:
        st.error(f"DB insert error: {e}")

def _db_update(req):
    try:
        res = _get_sb().table(TABLE).upsert(_serialize(req)).execute()
        if res.data:
            st.toast(f"✅ Updated: {req['id']}", icon="🗄️")
    except Exception as e:
        st.error(f"DB update error: {e}")

def _db_delete(rid):
    try:
        _get_sb().table(TABLE).delete().eq("id", rid).execute()
        st.toast(f"🗑️ Deleted {rid}", icon="🗄️")
    except Exception as e:
        st.error(f"DB delete error: {e}")

def _db_load_all():
    try:
        res = _get_sb().table(TABLE).select("*").order("created_at", desc=False).execute()
        rows = res.data or []
        st.caption(f"🗄️ Loaded {len(rows)} record(s) from Supabase.")
        return [_deserialize(r) for r in rows]
    except Exception as e:
        st.error(f"DB load error: {e}")
        return []


# ── Time helpers ──────────────────────────────────────────────────────────────

def _now():
    return datetime.now(IST)

def _fmt(dt):
    try:
        if isinstance(dt, str):
            dt = _str_to_dt(dt)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return str(dt)

def _time_left(expires_at):
    if isinstance(expires_at, str):
        expires_at = _str_to_dt(expires_at)
    secs = int((expires_at - _now()).total_seconds())
    if secs <= 0:
        return "⚠️ Escalating now…"
    h, rem = divmod(secs, 3600)
    m      = rem // 60
    if h >= 24:
        d = h // 24; hr = h % 24
        return f"⏳ {d}d {hr}h before auto-escalation"
    return f"⏳ {h}h {m}m before auto-escalation" if h else f"⏳ {m}m before auto-escalation"

def _deadline_str(expires_at):
    try:
        if isinstance(expires_at, str):
            expires_at = _str_to_dt(expires_at)
        return "Deadline: " + expires_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return ""


# ── Session state ─────────────────────────────────────────────────────────────

def _init():
    for k, v in {
        "ap_role_auth": {}, "ap_loaded": False, "ap_confirm_delete": {},
        "ap_ai_chat_history": [], "ap_ai_result": None,
        "ap_ai_prefill": None, "ap_show_prefill_form": False,
        "ap_escalation_msgs": [],   # banners to show after rerun
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _load_requests():
    rows = _db_load_all()
    st.session_state.ap_requests = rows
    ids = [int(r["id"].split("-")[1]) for r in rows if r.get("id","").startswith("REQ-")]
    st.session_state.ap_next_id = (max(ids) + 1) if ids else 1
    st.session_state.ap_loaded  = True


# ── Core actions ──────────────────────────────────────────────────────────────

def _create(title, category, subtype, description, urgency, requester):
    rid  = f"REQ-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now  = _now()
    cfg  = DOC_CATEGORIES[category]
    chain = _build_chain(category)

    if cfg["auto"]:
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": [], "stage_idx": 0, "status": "Approved",
            "created_at": now, "expires_at": now, "done": True,
            "history": [
                {"time": now, "by": "System", "action": "Submitted"},
                {"time": now, "by": "Admin",  "action": "Auto-approved (General document)"},
            ],
        }
    else:
        deadline = now + timedelta(hours=ESCALATION_HOURS)
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": chain, "stage_idx": 0, "status": "Pending",
            "created_at": now, "expires_at": deadline, "done": False,
            "history": [{
                "time": now, "by": "System",
                "action": (
                    f"Submitted → routed to {chain[0]}. "
                    f"Auto-escalates to next level if no response within {_escalation_label()}. "
                    f"Full chain: {' → '.join(chain)}. "
                    f"Deadline: {_fmt(deadline)}."
                ),
            }],
        }

    st.session_state.ap_requests.append(req)
    _db_insert(req)
    return req


def _approve(req, note):
    stage    = req["chain"][req["stage_idx"]]
    next_idx = req["stage_idx"] + 1
    req["history"].append({"time": _now(), "by": stage, "action": "Approved", "note": note})

    if next_idx >= len(req["chain"]):
        req["status"] = "Approved"
        req["done"]   = True
        req["history"].append({"time": _now(), "by": "System", "action": "All levels approved — COMPLETE ✅"})
    else:
        deadline  = _now() + timedelta(hours=ESCALATION_HOURS)
        next_role = req["chain"][next_idx]
        req["stage_idx"]  = next_idx
        req["expires_at"] = deadline
        req["history"].append({
            "time": _now(), "by": "System",
            "action": (
                f"✅ Approved by {stage} → forwarded to {next_role}. "
                f"Auto-escalates to next level if no response within {_escalation_label()}. "
                f"Deadline: {_fmt(deadline)}."
            ),
        })
    _db_update(req)


def _reject(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["status"] = "Rejected"
    req["done"]   = True
    req["history"].append({"time": _now(), "by": stage, "action": "Rejected", "note": note})
    _db_update(req)


def _check_expiry(req):
    """
    Auto-escalation — called on every page load / refresh.

    Moves the request UP ONE LEVEL after ESCALATION_HOURS of inactivity.
    Each level gets a fresh ESCALATION_HOURS window.

    Technical doc  [Team Lead, Tech Manager, CTO]:
      Team Lead times out    → escalates to Tech Manager (fresh 1-week window)
      Tech Manager times out → escalates to CTO          (fresh 1-week window)
      CTO times out          → Expired

    Security doc  [Team Lead, Tech Manager, CTO, CEO]:
      Team Lead times out    → Tech Manager
      Tech Manager times out → CTO
      CTO times out          → CEO
      CEO times out          → Expired

    Operations doc [Team Lead, Tech Manager]:
      Team Lead times out    → Tech Manager
      Tech Manager times out → Expired

    Team doc [Team Lead]:
      Team Lead times out    → Expired
    """
    if req["done"]:
        return
    if _now() <= req["expires_at"]:
        return  # still within window

    current   = req["chain"][req["stage_idx"]]
    next_idx  = req["stage_idx"] + 1
    final_idx = len(req["chain"]) - 1

    # Already at final approver → Expire
    if req["stage_idx"] >= final_idx:
        req["status"] = "Expired"
        req["done"]   = True
        req["history"].append({
            "time": _now(), "by": "System",
            "action": (
                f"⏰ EXPIRED — {current} (final approver) did not respond within "
                f"{_escalation_label()}. No further escalation possible."
            ),
        })
        _db_update(req)
        return

    # Move up exactly one level
    deadline  = _now() + timedelta(hours=ESCALATION_HOURS)
    next_role = req["chain"][next_idx]

    req["history"].append({
        "time": _now(), "by": "System",
        "action": (
            f"⚠️ AUTO-ESCALATED — {current} did not respond within "
            f"{_escalation_label()}. Automatically forwarded to {next_role}. "
            f"New deadline: {_fmt(deadline)}."
        ),
    })
    req["stage_idx"]  = next_idx
    req["expires_at"] = deadline
    _db_update(req)


def _delete_request(rid):
    st.session_state.ap_requests = [r for r in st.session_state.ap_requests if r["id"] != rid]
    st.session_state.ap_confirm_delete.pop(rid, None)
    _db_delete(rid)


# ── Classifier ────────────────────────────────────────────────────────────────

_RULES = [
    (["security policy","security doc"],            "Security",  "Compliance",      "Security Policy Document"),
    (["legal","contract","nda","agreement"],         "Security",  "Legal",           "Legal Document"),
    (["compliance","gdpr","audit","regulation"],     "Security",  "Compliance",      "Compliance Document"),
    (["public api","api security","api access"],     "Security",  "Public API",      "Public API Security Document"),
    (["financial","budget","invoice","payment"],     "Security",  "Financial",       "Financial Document"),
    (["java doc","javadoc","java documentation"],    "Technical", "Code Standards",  "Java Documentation"),
    (["api doc","api documentation","swagger","openapi","rest api doc"],"Technical","Code Standards","API Documentation"),
    (["code doc","code documentation","code standard","coding standard"],"Technical","Code Standards","Code Standards Document"),
    (["architecture","system design","tech design","design doc"],       "Technical","Architecture",  "Architecture Document"),
    (["database","db schema","schema","data model","erd"],              "Technical","Database",      "Database Design Document"),
    (["tech stack","technology stack","framework","library choice"],    "Technical","Tech Stack",    "Tech Stack Document"),
    (["infrastructure","server","cloud","aws","gcp","azure setup"],     "Technical","Infrastructure","Infrastructure Document"),
    (["runbook","run book","incident response"],                        "Operations","Runbooks",     "Runbook"),
    (["deployment","deploy guide","release guide","ci/cd","pipeline doc"],"Operations","Deployment","Deployment Guide"),
    (["monitoring","alerting","logging","observability"],               "Operations","Monitoring",   "Monitoring Guide"),
    (["setup guide","installation guide","how to setup","environment setup"],"Operations","Setup Guides","Setup Guide"),
    (["internal process","team process","workflow doc","sop"],          "Team","Internal Processes", "Internal Process Document"),
    (["troubleshoot","debug guide","issue guide","error guide"],        "Team","Troubleshooting",    "Troubleshooting Guide"),
    (["team setup","team guide","team wiki"],                           "Team","Setup Guides",       "Team Setup Guide"),
    (["faq","faqs","frequently asked"],                                 "General","FAQs",            "FAQ Document"),
    (["onboarding","new joinee","new employee","induction"],            "General","Onboarding",      "Onboarding Document"),
    (["general info","general doc","general document"],                 "General","General Info",    "General Information Document"),
]
_URGENCY_CRITICAL = ["critical","emergency","asap","immediately","right now"]
_URGENCY_URGENT   = ["urgent","priority","soon","quickly","fast","high priority"]

def _classify_request(text: str) -> dict:
    lower = text.lower().strip()
    doc_words = ["create","make","write","need","want","request","prepare","document","doc","guide","policy","documentation","submit"]
    if not any(w in lower for w in doc_words):
        return {
            "needs_document": False,
            "message": "It looks like you're asking a general question. Try: \"I need a deployment guide\" or \"I want to create a compliance doc\".",
            "suggested_title":"","category":"","subtype":"","urgency":"Normal","approval_route":"",
        }
    matched_category = matched_subtype = matched_title = None
    for keywords, cat, sub, title in _RULES:
        if any(kw in lower for kw in keywords):
            matched_category, matched_subtype, matched_title = cat, sub, title
            break
    if not matched_category:
        if any(w in lower for w in ["security","legal","compliance","financial"]):
            matched_category,matched_subtype,matched_title = "Security","Compliance","Security Document"
        elif any(w in lower for w in ["technical","code","software","system","api"]):
            matched_category,matched_subtype,matched_title = "Technical","Code Standards","Technical Document"
        elif any(w in lower for w in ["deploy","monitor","run","operation","infra"]):
            matched_category,matched_subtype,matched_title = "Operations","Runbooks","Operations Document"
        elif any(w in lower for w in ["team","internal","process","wiki","sop"]):
            matched_category,matched_subtype,matched_title = "Team","Internal Processes","Team Document"
        else:
            matched_category,matched_subtype,matched_title = "General","General Info","General Document"

    urgency = "CRITICAL" if any(w in lower for w in _URGENCY_CRITICAL) else "URGENT" if any(w in lower for w in _URGENCY_URGENT) else "Normal"
    chain   = _build_chain(matched_category)
    cfg     = DOC_CATEGORIES[matched_category]
    route   = "Auto-approved instantly ✅" if cfg["auto"] else " → ".join(chain)

    return {
        "needs_document":  True,
        "message": (
            f"Got it! This looks like a **{cfg['label']} › {matched_subtype}** document. "
            f"Approval route: **{route}**. "
            f"Each approver has **{_escalation_label()}** to respond — if no response, "
            f"it escalates to the next level in the chain. "
            f"Pre-filled the form below!"
        ),
        "suggested_title": matched_title,
        "category":        matched_category,
        "subtype":         matched_subtype,
        "urgency":         urgency,
        "approval_route":  route,
    }


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
<style>
.ai-panel {
    background: linear-gradient(135deg,#f0f4ff,#e8f0fe);
    border:1.5px solid #c7d7fd; border-radius:16px; padding:20px 24px 16px; margin-bottom:24px;
}
.ai-panel-title   { font-size:17px; font-weight:700; color:#1e3a8a; margin:0; }
.ai-panel-subtitle{ font-size:12.5px; color:#6b7280; margin:0; }
.chat-bubble-user {
    background:#1e3a8a; color:white; border-radius:14px 14px 4px 14px;
    padding:10px 15px; margin:6px 0 6px 60px; font-size:14px;
}
.chat-bubble-ai {
    background:white; border:1px solid #dbeafe; color:#1e293b;
    border-radius:14px 14px 14px 4px; padding:10px 15px; margin:6px 60px 6px 0;
    font-size:14px; line-height:1.6;
}
.route-badge {
    display:inline-block; background:#eff6ff; border:1px solid #93c5fd;
    color:#1d4ed8; border-radius:20px; font-size:12px; font-weight:600;
    padding:2px 10px; margin:4px 2px 0;
}
.ai-suggestion-box {
    background:#f0fdf4; border:1.5px solid #86efac; border-radius:12px;
    padding:14px 18px; margin:10px 0 4px;
}
.ai-suggestion-box .label { font-size:11px; font-weight:700; color:#166534; text-transform:uppercase; }
.ai-suggestion-box .value { font-size:15px; font-weight:600; color:#14532d; }
.ai-no-doc-box {
    background:#fefce8; border:1.5px solid #fde68a; border-radius:12px;
    padding:12px 16px; margin:8px 0 0; font-size:14px; color:#713f12;
}
.policy-box {
    background:linear-gradient(135deg,#fffbeb,#fef3c7);
    border:1.5px solid #fcd34d; border-radius:14px; padding:16px 20px; margin:12px 0;
}
.policy-box .title { font-size:15px; font-weight:700; color:#92400e; margin-bottom:6px; }
.chain-role  { background:white; border:1.5px solid #fcd34d; border-radius:10px; padding:6px 14px; font-size:13px; font-weight:600; color:#92400e; display:inline-block; margin:2px; }
.chain-arrow { font-size:18px; color:#d97706; margin:0 2px; }
.timer-chip  { background:#fef3c7; border:1px solid #fcd34d; border-radius:8px; padding:2px 8px; font-size:11px; font-weight:700; color:#92400e; display:inline-block; margin:2px; }
.escalation-banner {
    background:linear-gradient(135deg,#fff7ed,#ffedd5);
    border:1.5px solid #fed7aa; border-radius:12px; padding:14px 18px;
    margin:10px 0; font-size:13px; color:#9a3412; line-height:1.7;
}
.esc-item {
    background:#fff7ed; border-left:3px solid #f97316;
    border-radius:0 8px 8px 0; padding:8px 14px; margin:6px 0;
    font-size:13px; color:#9a3412;
}
.deadline-chip {
    display:inline-block; background:#fef9c3; border:1px solid #fde047;
    border-radius:8px; padding:3px 10px; font-size:12px; color:#713f12; margin-top:4px;
}
.role-reminder {
    background:#fffbeb; border:1.5px solid #fcd34d; border-radius:10px;
    padding:12px 16px; margin-bottom:12px; font-size:13px; color:#92400e;
}
</style>
"""


# ── AI Assistant render ───────────────────────────────────────────────────────

def _render_ai_assistant():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
    <div class="ai-panel">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <span style="font-size:26px">💬</span>
        <div>
          <p class="ai-panel-title">Need a Document Created?</p>
          <p class="ai-panel-subtitle">
            Describe what you need in plain English. The system figures out the category,
            approval chain, and routing automatically.
          </p>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    for turn in st.session_state.ap_ai_chat_history:
        if turn["role"] == "user":
            st.markdown(f"<div class='chat-bubble-user'>{turn['content']}</div>", unsafe_allow_html=True)
        else:
            try:
                _render_ai_bubble(json.loads(turn["content"]))
            except Exception:
                st.markdown(f"<div class='chat-bubble-ai'>🤖 {turn['content']}</div>", unsafe_allow_html=True)

    result = st.session_state.get("ap_ai_result")
    if result and result.get("needs_document") and not st.session_state.get("ap_show_prefill_form"):
        c1, c2, _ = st.columns([2.2, 1, 3])
        with c1:
            if st.button("📝 Pre-fill the Form Below", key="ai_prefill_btn",
                         use_container_width=True, type="primary"):
                st.session_state.ap_ai_prefill = {
                    "title":    result.get("suggested_title",""),
                    "category": result.get("category","General"),
                    "subtype":  result.get("subtype",""),
                    "urgency":  result.get("urgency","Normal"),
                }
                st.session_state.ap_show_prefill_form = True
                st.rerun()
        with c2:
            if st.button("🗑️ Clear", key="ai_clear_btn", use_container_width=True):
                st.session_state.ap_ai_chat_history   = []
                st.session_state.ap_ai_result         = None
                st.session_state.ap_ai_prefill        = None
                st.session_state.ap_show_prefill_form = False
                st.rerun()

    with st.form("ai_chat_form", clear_on_submit=True):
        user_input = st.text_area("desc", height=90, label_visibility="collapsed",
            placeholder='e.g. "I need a deployment guide" or "Create a security compliance doc"')
        c, _ = st.columns([1,4])
        with c:
            go = st.form_submit_button("🔍 Check & Route", use_container_width=True, type="primary")

    if go and user_input.strip():
        res = _classify_request(user_input.strip())
        st.session_state.ap_ai_chat_history += [
            {"role": "user",      "content": user_input.strip()},
            {"role": "assistant", "content": json.dumps(res)},
        ]
        st.session_state.ap_ai_result = res
        st.rerun()
    elif go:
        st.warning("Please describe what document you need.")


def _render_ai_bubble(data: dict):
    if not data.get("needs_document"):
        st.markdown(f"<div class='chat-bubble-ai'>🤖 {data.get('message','')}</div>", unsafe_allow_html=True)
        st.markdown("<div class='ai-no-doc-box'>No document approval needed. You can still submit manually below.</div>", unsafe_allow_html=True)
        return
    category  = data.get("category","")
    subtype   = data.get("subtype","")
    title     = data.get("suggested_title","")
    route     = data.get("approval_route","")
    urgency   = data.get("urgency","Normal")
    cat_label = DOC_CATEGORIES.get(category,{}).get("label",category)
    urg_color = {"URGENT":"#f59e0b","CRITICAL":"#ef4444"}.get(urgency,"#6b7280")
    st.markdown(f"""
    <div class="chat-bubble-ai">
      🤖 {data.get('message','')}
      <br>
      <span class="route-badge">{cat_label} › {subtype}</span>
      <span class="route-badge">{route}</span>
      <span class="route-badge" style="color:{urg_color};border-color:{urg_color};">⚡ {urgency}</span>
    </div>
    <div class="ai-suggestion-box">
      <div class="label">Suggested Document Title</div>
      <div class="value">📄 {title}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_policy_box():
    st.markdown(f"""
    <div class="policy-box">
      <div class="title">⏳ Auto-Escalation Policy — {_escalation_label()} per approver, then moves to the next level</div>
      <p style="font-size:13px;color:#92400e;margin:0 0 12px;">
        Each approver has <strong>{_escalation_label()}</strong> to respond.
        If they don't, the request <strong>moves up one level</strong> automatically.
        Each level gets a <strong>fresh {_escalation_label()} window</strong>.
        If the final approver also times out, the request is <strong>Expired</strong>.
      </p>
      <table style="font-size:13px;color:#92400e;border-collapse:collapse;width:100%">
        <tr style="border-bottom:1px solid #fcd34d">
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">⚙️ Technical</td>
          <td style="padding:6px 10px;">
            <span class="chain-role">Team Lead</span>
            <span class="chain-arrow">→</span>
            <span class="timer-chip">⏳ {_escalation_label()}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-role">Tech Manager</span>
            <span class="chain-arrow">→</span>
            <span class="timer-chip">⏳ {_escalation_label()}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-role">CTO</span>
          </td>
        </tr>
        <tr style="border-bottom:1px solid #fcd34d">
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">🔧 Operations</td>
          <td style="padding:6px 10px;">
            <span class="chain-role">Team Lead</span>
            <span class="chain-arrow">→</span>
            <span class="timer-chip">⏳ {_escalation_label()}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-role">Tech Manager</span>
          </td>
        </tr>
        <tr style="border-bottom:1px solid #fcd34d">
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">🔒 Security</td>
          <td style="padding:6px 10px;">
            <span class="chain-role">Team Lead</span>
            <span class="chain-arrow">→</span>
            <span class="timer-chip">⏳ {_escalation_label()}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-role">Tech Manager</span>
            <span class="chain-arrow">→</span>
            <span class="timer-chip">⏳ {_escalation_label()}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-role">CTO</span>
            <span class="chain-arrow">→</span>
            <span class="timer-chip">⏳ {_escalation_label()}</span>
            <span class="chain-arrow">→</span>
            <span class="chain-role">CEO</span>
          </td>
        </tr>
        <tr>
          <td style="padding:6px 10px;font-weight:700;white-space:nowrap;">👥 Team</td>
          <td style="padding:6px 10px;">
            <span class="chain-role">Team Lead</span>
            <span style="font-size:11px;color:#b45309;margin-left:8px;">Single approver — expires if no response</span>
          </td>
        </tr>
      </table>
    </div>
    """, unsafe_allow_html=True)


# ── Main entry ────────────────────────────────────────────────────────────────

def page_approval_pipeline():
    _init()
    st.markdown(_CSS, unsafe_allow_html=True)

    try:
        _get_sb().table(TABLE).select("id").limit(1).execute()
        st.success(f"🟢 Supabase connected — table `{TABLE}` reachable.")
    except Exception as e:
        st.error(f"🔴 Supabase FAILED: {e}")
        st.stop()

    if not st.session_state.ap_loaded:
        _load_requests()

    # ── Step 1: migrate any records with stale/wrong chains ───────────────────
    for r in st.session_state.ap_requests:
        if _migrate_chain(r):
            _db_update(r)

    # ── Step 2: run auto-escalation on every load ─────────────────────────────
    escalated = []
    for r in st.session_state.ap_requests:
        bi, bd = r.get("stage_idx",0), r.get("done",False)
        _check_expiry(r)
        if r.get("stage_idx",0) != bi or (r.get("done") and not bd):
            escalated.append(r)

    # ── Step 3: if anything changed, rerun so tabs/inboxes reflect new state ──
    if escalated:
        msgs = []
        for r in escalated:
            last = r["history"][-1] if r["history"] else {}
            msgs.append(f"⚠️ **Auto-escalated {r['id']}: {r['title']}** — {last.get('action','')}")
        st.session_state.ap_escalation_msgs = msgs
        st.rerun()  # forces tabs + inbox counts to update immediately

    # ── Step 4: show any escalation banners carried over from the rerun ───────
    for msg in st.session_state.get("ap_escalation_msgs", []):
        st.markdown(f"<div class='escalation-banner'>{msg}</div>", unsafe_allow_html=True)
    st.session_state.ap_escalation_msgs = []  # clear after displaying

    hc, rc = st.columns([5,1])
    with hc: st.title("📋 Document Approval Pipeline")
    with rc:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True):
            _load_requests(); st.rerun()

    _render_policy_box()

    def _n(role):
        return sum(1 for r in st.session_state.ap_requests
                   if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role)

    tabs = st.tabs([
        "📝 Submit",
        f"👨‍💼 Team Lead ({_n('Team Lead')})",
        f"👩‍💻 Tech Manager ({_n('Tech Manager')})",
        f"🧑‍🔬 CTO ({_n('CTO')})",
        f"👑 CEO ({_n('CEO')})",
    ])
    with tabs[0]: _view_submit()
    with tabs[1]: _view_role("Team Lead")
    with tabs[2]: _view_role("Tech Manager")
    with tabs[3]: _view_role("CTO")
    with tabs[4]: _view_role("CEO")


# ── Submit tab ────────────────────────────────────────────────────────────────

def _view_submit():
    _render_ai_assistant()
    st.divider()

    prefill      = st.session_state.get("ap_ai_prefill") or {}
    show_prefill = st.session_state.get("ap_show_prefill_form", False)

    st.markdown(
        "### Submit Request" + (
            "  <small style='background:#d1fae5;color:#065f46;border-radius:8px;"
            "padding:2px 10px;font-size:12px;font-weight:600;'>✨ Pre-filled by AI</small>"
            if show_prefill and prefill else ""
        ), unsafe_allow_html=True,
    )

    cat_keys    = list(DOC_CATEGORIES.keys())
    pre_cat     = prefill.get("category", cat_keys[0])
    if pre_cat not in cat_keys: pre_cat = cat_keys[0]
    pre_cat_idx = cat_keys.index(pre_cat)

    with st.form("ap_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            requester = st.text_input("Your Name / Employee ID", placeholder="e.g. Priya K · EMP-042")
            category  = st.selectbox("Document Category", cat_keys, index=pre_cat_idx,
                                     format_func=lambda c: DOC_CATEGORIES[c]["label"])
        with c2:
            title   = st.text_input("Document Title", value=prefill.get("title",""),
                                    placeholder="e.g. Database Backup Procedure")
            urg_opts = ["Normal","URGENT","CRITICAL"]
            urg_idx  = urg_opts.index(prefill.get("urgency","Normal")) if prefill.get("urgency") in urg_opts else 0
            urgency  = st.selectbox("Urgency", urg_opts, index=urg_idx)

        avail_sub = DOC_CATEGORIES[category]["subtypes"]
        pre_sub   = prefill.get("subtype","")
        subtype   = st.selectbox("Document Subtype", avail_sub,
                                 index=avail_sub.index(pre_sub) if pre_sub in avail_sub else 0)
        description = st.text_area("What does this document need to cover?",
                                   placeholder="Describe the purpose and scope…", height=90)

        cfg   = DOC_CATEGORIES[category]
        chain = _build_chain(category)
        if cfg["auto"]:
            route_str = "Auto-approved instantly"
        else:
            route_str = " → ".join(chain) + f"  ·  {_escalation_label()} per level"
        st.caption(f"Approval route: {route_str}")

        bc1, bc2, _ = st.columns([2,1,3])
        with bc1: submitted = st.form_submit_button("🚀 Submit Request", type="primary", use_container_width=True)
        with bc2: cancel    = st.form_submit_button("✖ Clear Prefill", use_container_width=True) if show_prefill else False

    if cancel:
        st.session_state.ap_ai_prefill = None; st.session_state.ap_show_prefill_form = False; st.rerun()

    if submitted:
        errs = []
        if not requester.strip():   errs.append("Name / Employee ID required.")
        if not title.strip():       errs.append("Document title required.")
        if not description.strip(): errs.append("Description required.")
        for e in errs: st.error(e)
        if not errs:
            req = _create(title.strip(), category, subtype, description.strip(), urgency, requester.strip())
            st.session_state.ap_ai_prefill = None; st.session_state.ap_show_prefill_form = False
            if req["done"]:
                st.success(f"✅ **{req['id']}** auto-approved instantly.")
            else:
                chain = req["chain"]
                st.success(
                    f"✅ **{req['id']}** submitted → **{chain[0]}** must respond by "
                    f"**{_fmt(req['expires_at'])}**. "
                    f"Full chain: **{' → '.join(chain)}** — each level gets {_escalation_label()}."
                )

    all_reqs = list(reversed(st.session_state.ap_requests))
    if not all_reqs: st.info("No requests yet."); return

    st.divider()
    counts = {"Pending":0,"Approved":0,"Rejected":0,"Expired":0}
    for r in all_reqs: counts[r["status"]] = counts.get(r["status"],0) + 1
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🟡 Pending",  counts["Pending"])
    c2.metric("🟢 Approved", counts["Approved"])
    c3.metric("🔴 Rejected", counts["Rejected"])
    c4.metric("⏰ Expired",  counts["Expired"])

    st.divider()
    st.markdown("### 📋 All Requests")
    bc1, bc2, _ = st.columns([2,2,4])
    with bc1:
        if st.button("🗑️ Delete All Rejected", use_container_width=True):
            ids = [r["id"] for r in all_reqs if r["status"]=="Rejected"]
            for rid in ids: _delete_request(rid)
            (st.success(f"Deleted {len(ids)}.") if ids else st.info("None.")); (st.rerun() if ids else None)
    with bc2:
        if st.button("🗑️ Delete All Expired", use_container_width=True):
            ids = [r["id"] for r in all_reqs if r["status"]=="Expired"]
            for rid in ids: _delete_request(rid)
            (st.success(f"Deleted {len(ids)}.") if ids else st.info("None.")); (st.rerun() if ids else None)

    st.divider()
    for req in all_reqs: _card_with_delete(req)


# ── Cards ─────────────────────────────────────────────────────────────────────

def _card_with_delete(req: dict):
    rid   = req["id"]; k = f"sub_{rid}"
    label = _card_label(req)
    with st.expander(label, expanded=False):
        _card_body(req)
        st.divider()
        if not st.session_state.ap_confirm_delete.get(rid):
            dc, _ = st.columns([1,5])
            with dc:
                if st.button("🗑️ Delete", key=f"del_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = True; st.rerun()
        else:
            st.warning(f"⚠️ Delete **{rid}**? Cannot be undone.")
            yc, nc, _ = st.columns([1,1,4])
            with yc:
                if st.button("✅ Yes", key=f"dy_{k}", use_container_width=True):
                    _delete_request(rid); st.rerun()
            with nc:
                if st.button("✖ No",  key=f"dn_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = False; st.rerun()


def _request_card(req: dict, show_actions: bool, ctx: str = ""):
    k = f"{ctx}_{req['id']}"
    with st.expander(_card_label(req), expanded=(show_actions and not req["done"])):
        _card_body(req)
        if show_actions and not req["done"]:
            note = st.text_input("Note (optional)", key=f"note_{k}", placeholder="Reason or comment…")
            ac, rc, _ = st.columns([1,1,4])
            with ac:
                if st.button("✅ Approve", key=f"ap_{k}", type="primary", use_container_width=True):
                    _approve(req, note); st.rerun()
            with rc:
                if st.button("❌ Reject", key=f"rj_{k}", use_container_width=True):
                    _reject(req, note); st.rerun()


def _card_label(req: dict) -> str:
    status_icon = {"Pending":"🟡","Approved":"🟢","Rejected":"🔴","Expired":"⏰"}.get(req["status"],"⚪")
    urg_icon    = {"URGENT":"🟡","CRITICAL":"🔴"}.get(req["urgency"],"")
    esc_count   = sum(1 for e in req.get("history",[]) if "AUTO-ESCALATED" in e.get("action",""))
    label = f"{status_icon} {req['id']}  ·  {req['title']}  {urg_icon}"
    if esc_count: label += f"  ·  ⚠️ {esc_count} escalation(s)"
    if not req["done"]: label += f"  ·  {_time_left(req['expires_at'])}"
    return label


def _card_body(req: dict):
    stage = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f"**Requester**  \n{req['requester']}")
    c2.markdown(f"**Category**  \n{req.get('category','—')} › {req.get('subtype','—')}")
    c3.markdown(f"**Stage**  \n{stage}")
    c4.markdown(f"**Status**  \n{req['status']}")

    if not req["done"]:
        st.markdown(f"<span class='deadline-chip'>📅 {_deadline_str(req['expires_at'])}</span>",
                    unsafe_allow_html=True)

    st.markdown(f"> {req['description']}")

    # Escalation trail
    esc_entries = [e for e in req.get("history",[]) if "AUTO-ESCALATED" in e.get("action","")]
    if esc_entries:
        esc_html = "".join(
            f"<div class='esc-item'>⚠️ <b>{_fmt(e['time'])}</b> — {e['action']}</div>"
            for e in esc_entries
        )
        st.markdown(
            f"<div style='margin:8px 0'>"
            f"<p style='font-size:13px;font-weight:700;color:#9a3412;margin-bottom:4px'>"
            f"⚠️ Auto-Escalation History ({len(esc_entries)} event(s))</p>"
            f"{esc_html}</div>",
            unsafe_allow_html=True,
        )

    # Chain progress
    if req["chain"]:
        parts = []
        for i, s in enumerate(req["chain"]):
            was_esc = any(s in e.get("action","") and "AUTO-ESCALATED" in e.get("action","")
                          for e in req.get("history",[]))
            if req["status"] == "Approved" or i < req["stage_idx"]:
                parts.append(f"~~{s}~~ {'⚠️' if was_esc else '✅'}")
            elif i == req["stage_idx"] and not req["done"]:
                parts.append(f"**{s} ⏳**")
            elif req["done"] and i == req["stage_idx"]:
                parts.append(f"**{s} {'❌' if req['status']=='Rejected' else '⏰'}**")
            else:
                parts.append(s)
        st.markdown("  →  ".join(parts))
    else:
        st.caption("Auto-approved — no chain required.")

    with st.expander("📜 History", key=f"hist_{req['id']}_{id(req)}"):
        for entry in req["history"]:
            t      = _fmt(entry.get("time",""))
            note   = f" — {entry['note']}" if entry.get("note") else ""
            action = entry["action"]
            if "AUTO-ESCALATED" in action:
                st.markdown(f"<div class='esc-item'>`{t}`  **{entry['by']}**: {action}{note}</div>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"`{t}`  **{entry['by']}**: {action}{note}")


# ── Role tab ──────────────────────────────────────────────────────────────────

def _view_role(role: str):
    if not st.session_state.ap_role_auth.get(role):
        st.subheader(f"{role} Login")
        col, _ = st.columns([1.5,3])
        with col:
            pwd = st.text_input("Password", type="password", key=f"pwd_{role}")
            if st.button("Log in", type="primary", use_container_width=True, key=f"login_{role}"):
                if pwd == ROLE_PASSWORDS.get(role,""):
                    st.session_state.ap_role_auth[role] = True; st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    hc, lc = st.columns([6,1])
    with hc: st.subheader(f"Inbox — {role}")
    with lc:
        if st.button("Log out", key=f"logout_{role}"):
            st.session_state.ap_role_auth[role] = False; st.rerun()

    st.markdown(f"""
    <div class="role-reminder">
      ⏳ <strong>You have {_escalation_label()} to respond to each request.</strong>
      If you don't approve or reject in time, the request will be
      <strong>automatically escalated to the next level</strong> in the chain — no action needed from you.
    </div>
    """, unsafe_allow_html=True)

    ctx = role.replace(" ","_").lower()

    mine = [r for r in reversed(st.session_state.ap_requests)
            if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role]
    handled = [r for r in reversed(st.session_state.ap_requests)
               if r["done"] and any(e.get("by") == role for e in r["history"])]
    esc_past = [r for r in reversed(st.session_state.ap_requests)
                if any(role in e.get("action","") and "AUTO-ESCALATED" in e.get("action","")
                       for e in r.get("history",[]))]

    if not mine:
        st.success("✅ Nothing waiting for your approval right now.")
    else:
        st.markdown(f"**{len(mine)} request(s) awaiting your decision**")
        for req in mine: _request_card(req, show_actions=True, ctx=ctx)

    if esc_past:
        st.divider()
        with st.expander(f"⚠️ Escalated past your level ({len(esc_past)}) — timed out"):
            st.markdown(f"<small style='color:#9a3412'>No response received within {_escalation_label()}.</small>",
                        unsafe_allow_html=True)
            for req in esc_past: _request_card(req, show_actions=False, ctx=f"{ctx}_esc")

    if handled:
        st.divider()
        with st.expander(f"Previously handled ({len(handled)})"):
            for req in handled: _request_card(req, show_actions=False, ctx=f"{ctx}_done")
