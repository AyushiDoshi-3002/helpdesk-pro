"""
approval_pipeline.py  –  role-based tabs + Supabase persistence + AI Assistant
────────────────────────────────────────────────────────────────────────────────
Install dependency:  pip install supabase anthropic

Run this SQL once in your Supabase SQL editor to create the table:
──────────────────────────────────────────────────────────────────
create table if not exists ap_requests (
    id          text primary key,
    title       text,
    category    text,
    subtype     text,
    description text,
    urgency     text,
    requester   text,
    chain       jsonb,
    stage_idx   integer default 0,
    status      text,
    created_at  timestamptz,
    expires_at  timestamptz,
    history     jsonb,
    done        boolean default false
);
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

TIMEOUT_HOURS = 2

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


# ── Supabase client (cached) ──────────────────────────────────────────────────

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

def _db_insert(req: dict):
    try:
        row = _serialize(req)
        res = _get_sb().table(TABLE).insert(row).execute()
        if hasattr(res, "data") and res.data:
            st.toast(f"✅ Saved to Supabase: {req['id']}", icon="🗄️")
        else:
            st.warning(f"⚠️ Insert returned no data. Response: {res}")
    except Exception as e:
        st.error(f"❌ DB insert error for {req.get('id')}: {type(e).__name__}: {e}")

def _db_update(req: dict):
    try:
        row = _serialize(req)
        res = _get_sb().table(TABLE).upsert(row).execute()
        if hasattr(res, "data") and res.data:
            st.toast(f"✅ Updated in Supabase: {req['id']}", icon="🗄️")
        else:
            st.warning(f"⚠️ Upsert returned no data. Response: {res}")
    except Exception as e:
        st.error(f"❌ DB update error for {req.get('id')}: {type(e).__name__}: {e}")

def _db_delete(rid: str):
    try:
        _get_sb().table(TABLE).delete().eq("id", rid).execute()
        st.toast(f"🗑️ Deleted {rid} from Supabase", icon="🗄️")
    except Exception as e:
        st.error(f"❌ DB delete error for {rid}: {type(e).__name__}: {e}")

def _db_load_all() -> list:
    try:
        res = _get_sb().table(TABLE).select("*").order("created_at", desc=False).execute()
        rows = res.data or []
        st.caption(f"🗄️ Loaded {len(rows)} record(s) from Supabase.")
        return [_deserialize(row) for row in rows]
    except Exception as e:
        st.error(f"❌ DB load error: {type(e).__name__}: {e}")
        return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(IST)

def _fmt(dt):
    try:
        if isinstance(dt, str):
            dt = _str_to_dt(dt)
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return str(dt)

def _time_left(expires_at):
    if isinstance(expires_at, str):
        expires_at = _str_to_dt(expires_at)
    diff = expires_at - _now()
    secs = int(diff.total_seconds())
    if secs <= 0:
        return "Expired"
    h, rem = divmod(secs, 3600)
    m, _   = divmod(rem, 60)
    return f"{h}h {m}m left" if h else f"{m}m left"


# ── Session-state init ────────────────────────────────────────────────────────

def _init():
    defaults = {
        "ap_role_auth":             {},
        "ap_loaded":                False,
        "ap_confirm_delete":        {},
        # AI Assistant state
        "ap_ai_chat_history":       [],   # list of {"role": "user"|"assistant", "content": str}
        "ap_ai_result":             None, # dict with parsed AI suggestion
        "ap_ai_prefill":            None, # dict to prefill the submit form
        "ap_show_prefill_form":     False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _load_requests():
    rows = _db_load_all()
    st.session_state.ap_requests = rows
    ids = [int(r["id"].split("-")[1]) for r in rows if r.get("id", "").startswith("REQ-")]
    st.session_state.ap_next_id = (max(ids) + 1) if ids else 1
    st.session_state.ap_loaded  = True


# ── Core actions ──────────────────────────────────────────────────────────────

def _create(title, category, subtype, description, urgency, requester):
    rid   = f"REQ-{st.session_state.ap_next_id:03d}"
    st.session_state.ap_next_id += 1
    now   = _now()
    cfg   = DOC_CATEGORIES[category]
    chain = _build_chain(category)
    auto  = cfg["auto"]

    if auto:
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": [], "stage_idx": 0, "status": "Approved",
            "created_at": now, "expires_at": now,
            "history": [
                {"time": now, "by": "System", "action": "Submitted"},
                {"time": now, "by": "Admin",  "action": "Auto-approved (General document)"},
            ],
            "done": True,
        }
    else:
        req = {
            "id": rid, "title": title, "category": category, "subtype": subtype,
            "description": description, "urgency": urgency, "requester": requester,
            "chain": chain, "stage_idx": 0, "status": "Pending",
            "created_at": now, "expires_at": now + timedelta(hours=TIMEOUT_HOURS),
            "history": [{"time": now, "by": "System",
                         "action": f"Submitted → routed to {chain[0]}"}],
            "done": False,
        }

    st.session_state.ap_requests.append(req)
    _db_insert(req)
    return req

def _approve(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["history"].append({"time": _now(), "by": stage, "action": "Approved", "note": note})
    next_idx = req["stage_idx"] + 1
    if next_idx >= len(req["chain"]):
        req["status"] = "Approved"
        req["done"]   = True
        req["history"].append({"time": _now(), "by": "System",
                                "action": "All levels approved — COMPLETE ✅"})
    else:
        req["stage_idx"]  = next_idx
        req["expires_at"] = _now() + timedelta(hours=TIMEOUT_HOURS)
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Forwarded to {req['chain'][next_idx]}"})
    _db_update(req)

def _reject(req, note):
    stage = req["chain"][req["stage_idx"]]
    req["status"] = "Rejected"
    req["done"]   = True
    req["history"].append({"time": _now(), "by": stage, "action": "Rejected", "note": note})
    _db_update(req)

def _check_expiry(req):
    if not req["done"] and _now() > req["expires_at"]:
        stage         = req["chain"][req["stage_idx"]]
        req["status"] = "Expired"
        req["done"]   = True
        req["history"].append({"time": _now(), "by": "System",
                                "action": f"Expired — no response from {stage}"})
        _db_update(req)

def _delete_request(rid: str):
    st.session_state.ap_requests = [
        r for r in st.session_state.ap_requests if r["id"] != rid
    ]
    st.session_state.ap_confirm_delete.pop(rid, None)
    _db_delete(rid)


# ════════════════════════════════════════════════════════════════════════════
#  SMART CLASSIFIER — keyword-based, zero API key needed
# ════════════════════════════════════════════════════════════════════════════

# Each entry: (keywords_that_must_match, category, subtype, title_template)
_RULES = [
    # ── Security ──────────────────────────────────────────────────────────
    (["security policy", "security doc"],           "Security", "Compliance",  "Security Policy Document"),
    (["legal", "contract", "nda", "agreement"],     "Security", "Legal",       "Legal Document"),
    (["compliance", "gdpr", "audit", "regulation"], "Security", "Compliance",  "Compliance Document"),
    (["public api", "api security", "api access"],  "Security", "Public API",  "Public API Security Document"),
    (["financial", "budget", "invoice", "payment"], "Security", "Financial",   "Financial Document"),

    # ── Technical ─────────────────────────────────────────────────────────
    (["java doc", "javadoc", "java documentation"], "Technical", "Code Standards", "Java Documentation"),
    (["api doc", "api documentation", "swagger", "openapi", "rest api doc"], "Technical", "Code Standards", "API Documentation"),
    (["code doc", "code documentation", "code standard", "coding standard"],  "Technical", "Code Standards", "Code Standards Document"),
    (["architecture", "system design", "tech design", "design doc"],          "Technical", "Architecture",   "Architecture Document"),
    (["database", "db schema", "schema", "data model", "erd"],                "Technical", "Database",       "Database Design Document"),
    (["tech stack", "technology stack", "framework", "library choice"],       "Technical", "Tech Stack",     "Tech Stack Document"),
    (["infrastructure", "server", "cloud", "aws", "gcp", "azure setup"],      "Technical", "Infrastructure", "Infrastructure Document"),

    # ── Operations ────────────────────────────────────────────────────────
    (["runbook", "run book", "incident response"],           "Operations", "Runbooks",    "Runbook"),
    (["deployment", "deploy guide", "release guide", "ci/cd", "pipeline doc"], "Operations", "Deployment", "Deployment Guide"),
    (["monitoring", "alerting", "logging", "observability"], "Operations", "Monitoring",  "Monitoring Guide"),
    (["setup guide", "installation guide", "how to setup", "environment setup"], "Operations", "Setup Guides", "Setup Guide"),

    # ── Team ──────────────────────────────────────────────────────────────
    (["internal process", "team process", "workflow doc", "sop"],   "Team", "Internal Processes", "Internal Process Document"),
    (["troubleshoot", "debug guide", "issue guide", "error guide"], "Team", "Troubleshooting",    "Troubleshooting Guide"),
    (["team setup", "team guide", "team wiki"],                     "Team", "Setup Guides",       "Team Setup Guide"),

    # ── General ───────────────────────────────────────────────────────────
    (["faq", "faqs", "frequently asked"],           "General", "FAQs",         "FAQ Document"),
    (["onboarding", "new joinee", "new employee", "induction"], "General", "Onboarding", "Onboarding Document"),
    (["general info", "general doc", "general document"],       "General", "General Info", "General Information Document"),
]

# Urgency keywords
_URGENCY_CRITICAL = ["critical", "emergency", "urgent urgent", "asap", "immediately", "right now"]
_URGENCY_URGENT   = ["urgent", "priority", "soon", "quickly", "fast", "high priority"]

# Words that indicate NO document is needed
_NO_DOC_KEYWORDS = [
    "what is", "how does", "can you explain", "tell me", "who is",
    "when is", "where is", "define", "meaning of", "help me understand",
]


def _classify_request(text: str) -> dict:
    """
    Pure keyword-based classifier. No API key needed.
    Returns same structure as the old AI call.
    """
    lower = text.lower().strip()

    # Check if it's just a question with no document intent
    doc_intent_words = [
        "create", "make", "write", "need", "want", "request", "prepare",
        "document", "doc", "guide", "policy", "documentation", "submit"
    ]
    has_doc_intent = any(w in lower for w in doc_intent_words)

    if not has_doc_intent:
        return {
            "needs_document": False,
            "message": (
                "It looks like you're asking a general question rather than requesting "
                "a document. If you'd like to request a document to be created, try phrasing "
                "it like: \"I want to create a Java documentation\" or \"I need a deployment guide\"."
            ),
            "suggested_title": "", "category": "", "subtype": "",
            "urgency": "Normal", "approval_route": "",
        }

    # Match against rules
    matched_category = None
    matched_subtype  = None
    matched_title    = None

    for keywords, category, subtype, title in _RULES:
        if any(kw in lower for kw in keywords):
            matched_category = category
            matched_subtype  = matched_subtype or subtype
            matched_title    = title
            break  # first match wins

    # Fallback: look for broad category hints if no rule matched
    if not matched_category:
        if any(w in lower for w in ["security", "legal", "compliance", "financial"]):
            matched_category, matched_subtype, matched_title = "Security", "Compliance", "Security Document"
        elif any(w in lower for w in ["technical", "code", "software", "system", "api", "doc"]):
            matched_category, matched_subtype, matched_title = "Technical", "Code Standards", "Technical Document"
        elif any(w in lower for w in ["deploy", "monitor", "run", "operation", "infra"]):
            matched_category, matched_subtype, matched_title = "Operations", "Runbooks", "Operations Document"
        elif any(w in lower for w in ["team", "internal", "process", "wiki", "sop"]):
            matched_category, matched_subtype, matched_title = "Team", "Internal Processes", "Team Document"
        else:
            matched_category, matched_subtype, matched_title = "General", "General Info", "General Document"

    # Detect urgency
    if any(w in lower for w in _URGENCY_CRITICAL):
        urgency = "CRITICAL"
    elif any(w in lower for w in _URGENCY_URGENT):
        urgency = "URGENT"
    else:
        urgency = "Normal"

    # Build approval route string
    chain     = _build_chain(matched_category)
    cfg       = DOC_CATEGORIES[matched_category]
    if cfg["auto"]:
        route_str = "Auto-approved instantly ✅"
    else:
        route_str = " → ".join(chain)

    # Build friendly message
    cat_label = DOC_CATEGORIES[matched_category]["label"]
    message = (
        f"Got it! This looks like a **{cat_label} › {matched_subtype}** document. "
        f"Once you submit, it will go through: **{route_str}**. "
        f"I've pre-filled the form below — just add your name and description and hit Submit!"
    )

    return {
        "needs_document": True,
        "message":        message,
        "suggested_title": matched_title,
        "category":        matched_category,
        "subtype":         matched_subtype,
        "urgency":         urgency,
        "approval_route":  route_str,
    }


# ── CSS for the AI chat panel ─────────────────────────────────────────────────

_AI_CHAT_CSS = """
<style>
.ai-panel {
    background: linear-gradient(135deg, #f0f4ff 0%, #e8f0fe 100%);
    border: 1.5px solid #c7d7fd;
    border-radius: 16px;
    padding: 20px 24px 16px 24px;
    margin-bottom: 24px;
}
.ai-panel-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
}
.ai-panel-title {
    font-size: 17px;
    font-weight: 700;
    color: #1e3a8a;
    margin: 0;
}
.ai-panel-subtitle {
    font-size: 12.5px;
    color: #6b7280;
    margin: 0;
}
.chat-bubble-user {
    background: #1e3a8a;
    color: white;
    border-radius: 14px 14px 4px 14px;
    padding: 10px 15px;
    margin: 6px 0 6px 60px;
    font-size: 14px;
    line-height: 1.5;
}
.chat-bubble-ai {
    background: white;
    border: 1px solid #dbeafe;
    color: #1e293b;
    border-radius: 14px 14px 14px 4px;
    padding: 10px 15px;
    margin: 6px 60px 6px 0;
    font-size: 14px;
    line-height: 1.6;
}
.chat-bubble-ai .route-badge {
    display: inline-block;
    background: #eff6ff;
    border: 1px solid #93c5fd;
    color: #1d4ed8;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 10px;
    margin-top: 6px;
}
.ai-suggestion-box {
    background: #f0fdf4;
    border: 1.5px solid #86efac;
    border-radius: 12px;
    padding: 14px 18px;
    margin: 10px 0 4px 0;
}
.ai-suggestion-box .label {
    font-size: 11px;
    font-weight: 700;
    color: #166534;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.ai-suggestion-box .value {
    font-size: 15px;
    font-weight: 600;
    color: #14532d;
}
.ai-no-doc-box {
    background: #fefce8;
    border: 1.5px solid #fde68a;
    border-radius: 12px;
    padding: 12px 16px;
    margin: 8px 0 0 0;
    font-size: 14px;
    color: #713f12;
}
</style>
"""


def _render_ai_assistant():
    """Render the smart document request box at the top of the Submit tab."""
    st.markdown(_AI_CHAT_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="ai-panel">
      <div class="ai-panel-header">
        <span style="font-size:26px">💬</span>
        <div>
          <p class="ai-panel-title">Need a Document Created?</p>
          <p class="ai-panel-subtitle">
            Just describe what you need in plain English — e.g. <em>"I want to create Java documentation
            for our new service"</em> or <em>"I need a deployment guide"</em>. The system will
            automatically figure out the category and approval route for you.
          </p>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Render previous request + result if any ───────────────────────────────
    history = st.session_state.ap_ai_chat_history
    if history:
        for turn in history:
            if turn["role"] == "user":
                st.markdown(
                    f"<div class='chat-bubble-user'>🧑 {turn['content']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                try:
                    data = json.loads(turn["content"])
                    _render_ai_bubble(data)
                except Exception:
                    st.markdown(
                        f"<div class='chat-bubble-ai'>🤖 {turn['content']}</div>",
                        unsafe_allow_html=True,
                    )

    # ── Pre-fill button after a document is detected ──────────────────────────
    result = st.session_state.get("ap_ai_result")
    if result and result.get("needs_document") and not st.session_state.get("ap_show_prefill_form"):
        col_prefill, col_clear, _ = st.columns([2.2, 1, 3])
        with col_prefill:
            if st.button(
                "📝 Pre-fill the Form Below with This Suggestion",
                key="ai_prefill_btn",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.ap_ai_prefill = {
                    "title":    result.get("suggested_title", ""),
                    "category": result.get("category", "General"),
                    "subtype":  result.get("subtype", ""),
                    "urgency":  result.get("urgency", "Normal"),
                }
                st.session_state.ap_show_prefill_form = True
                st.rerun()
        with col_clear:
            if st.button("🗑️ Clear", key="ai_clear_btn", use_container_width=True):
                st.session_state.ap_ai_chat_history   = []
                st.session_state.ap_ai_result         = None
                st.session_state.ap_ai_prefill        = None
                st.session_state.ap_show_prefill_form = False
                st.rerun()

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form("ai_chat_form", clear_on_submit=True):
        user_input = st.text_area(
            "Describe what document you need",
            placeholder=(
                'e.g. "I want to create Java API documentation for our payment service"\n'
                'e.g. "We need a security compliance doc for GDPR"\n'
                'e.g. "Can someone make a deployment guide for our new release?"'
            ),
            height=90,
            label_visibility="collapsed",
        )
        col_btn, _ = st.columns([1, 4])
        with col_btn:
            submitted = st.form_submit_button(
                "🔍 Check & Route", use_container_width=True, type="primary"
            )

    if submitted and user_input.strip():
        result = _classify_request(user_input.strip())
        st.session_state.ap_ai_chat_history.append(
            {"role": "user", "content": user_input.strip()}
        )
        st.session_state.ap_ai_chat_history.append(
            {"role": "assistant", "content": json.dumps(result)}
        )
        st.session_state.ap_ai_result = result
        st.rerun()
    elif submitted:
        st.warning("Please describe what document you need.")

    # Clear button when result shows no doc needed
    if history and result and not result.get("needs_document"):
        if st.button("🗑️ Clear", key="ai_clear_btn_bottom"):
            st.session_state.ap_ai_chat_history   = []
            st.session_state.ap_ai_result         = None
            st.session_state.ap_ai_prefill        = None
            st.session_state.ap_show_prefill_form = False
            st.rerun()


def _render_ai_bubble(data: dict):
    """Render the AI's structured response as a styled chat bubble."""
    msg = data.get("message", "")
    needs_doc = data.get("needs_document", False)

    if needs_doc:
        category      = data.get("category", "")
        subtype       = data.get("subtype", "")
        title         = data.get("suggested_title", "")
        route         = data.get("approval_route", "")
        urgency       = data.get("urgency", "Normal")
        cat_cfg       = DOC_CATEGORIES.get(category, {})
        cat_label     = cat_cfg.get("label", category)
        urgency_color = {"URGENT": "#f59e0b", "CRITICAL": "#ef4444"}.get(urgency, "#6b7280")

        st.markdown(f"""
        <div class="chat-bubble-ai">
          🤖 {msg}
          <br><br>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;">
            <span class="route-badge">📁 {cat_label} › {subtype}</span>
            <span class="route-badge">🔀 {route}</span>
            <span class="route-badge" style="color:{urgency_color};border-color:{urgency_color};">⚡ {urgency}</span>
          </div>
        </div>
        <div class="ai-suggestion-box">
          <div class="label">Suggested Document Title</div>
          <div class="value">📄 {title}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='chat-bubble-ai'>🤖 {msg}</div>",
            unsafe_allow_html=True,
        )
        if not msg.startswith("⚠️"):
            st.markdown(
                "<div class='ai-no-doc-box'>ℹ️ No document approval needed for this request. "
                "You can still use the form below to submit one manually if needed.</div>",
                unsafe_allow_html=True,
            )


# ── Main entry ────────────────────────────────────────────────────────────────

def page_approval_pipeline():
    _init()

    try:
        test = _get_sb().table(TABLE).select("id").limit(1).execute()
        st.success(f"🟢 Supabase connected — table `{TABLE}` is reachable.")
    except Exception as e:
        st.error(f"🔴 Supabase connection FAILED: {type(e).__name__}: {e}")
        st.stop()

    if not st.session_state.ap_loaded:
        _load_requests()

    for r in st.session_state.ap_requests:
        _check_expiry(r)

    hcol, rcol = st.columns([5, 1])
    with hcol:
        st.title("Document Approval Pipeline")
    with rcol:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True):
            _load_requests()
            st.rerun()

    def _n(role):
        return sum(
            1 for r in st.session_state.ap_requests
            if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role
        )

    tabs = st.tabs([
        "📝 Submit",
        f"👤 Team Lead ({_n('Team Lead')})",
        f"🔧 Tech Manager ({_n('Tech Manager')})",
        f"⚙️ CTO ({_n('CTO')})",
        f"👑 CEO ({_n('CEO')})",
    ])

    with tabs[0]: _view_submit()
    with tabs[1]: _view_role("Team Lead")
    with tabs[2]: _view_role("Tech Manager")
    with tabs[3]: _view_role("CTO")
    with tabs[4]: _view_role("CEO")


# ── Submit + tracker (public) ─────────────────────────────────────────────────

def _view_submit():
    # ── AI Assistant at the top ───────────────────────────────────────────────
    _render_ai_assistant()

    st.divider()

    # ── Determine prefill values ──────────────────────────────────────────────
    prefill = st.session_state.get("ap_ai_prefill") or {}
    show_prefill = st.session_state.get("ap_show_prefill_form", False)

    if show_prefill and prefill:
        st.markdown(
            "### 📝 Submit Request  "
            "<small style='background:#d1fae5;color:#065f46;border-radius:8px;"
            "padding:2px 10px;font-size:12px;font-weight:600;'>✨ Pre-filled by AI</small>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### 📝 Submit Request")

    # Resolve prefill category safely
    prefill_category = prefill.get("category", list(DOC_CATEGORIES.keys())[0])
    if prefill_category not in DOC_CATEGORIES:
        prefill_category = list(DOC_CATEGORIES.keys())[0]
    cat_keys = list(DOC_CATEGORIES.keys())
    prefill_cat_idx = cat_keys.index(prefill_category) if prefill_category in cat_keys else 0

    with st.form("ap_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            requester = st.text_input(
                "Your Name / Employee ID",
                placeholder="e.g. Priya K · EMP-042",
            )
            category = st.selectbox(
                "Document Category",
                cat_keys,
                index=prefill_cat_idx,
                format_func=lambda c: DOC_CATEGORIES[c]["label"],
            )
        with col2:
            title = st.text_input(
                "Document Title",
                value=prefill.get("title", ""),
                placeholder="e.g. Database Backup Procedure",
            )
            urgency_opts = ["Normal", "URGENT", "CRITICAL"]
            prefill_urgency = prefill.get("urgency", "Normal")
            urgency_idx = urgency_opts.index(prefill_urgency) if prefill_urgency in urgency_opts else 0
            urgency = st.selectbox("Urgency", urgency_opts, index=urgency_idx)

        # Subtype — try to match AI suggestion
        available_subtypes = DOC_CATEGORIES[category]["subtypes"]
        prefill_subtype    = prefill.get("subtype", "")
        subtype_idx        = 0
        if prefill_subtype in available_subtypes:
            subtype_idx = available_subtypes.index(prefill_subtype)
        subtype = st.selectbox("Document Subtype", available_subtypes, index=subtype_idx)

        description = st.text_area(
            "What does this document need to cover?",
            placeholder="Describe the purpose and scope…",
            height=90,
        )

        cfg       = DOC_CATEGORIES[category]
        chain     = _build_chain(category)
        route_str = (
            "Auto-approved instantly"
            if cfg["auto"]
            else "  →  ".join(chain) + f"  ·  {TIMEOUT_HOURS}h per level"
        )
        st.caption(f"Approval route: {route_str}")

        btn_cols = st.columns([2, 1, 3])
        with btn_cols[0]:
            submitted = st.form_submit_button(
                "Submit Request", type="primary", use_container_width=True
            )
        with btn_cols[1]:
            if show_prefill:
                cancel_prefill = st.form_submit_button(
                    "✖ Clear Prefill", use_container_width=True
                )
            else:
                cancel_prefill = False

    if cancel_prefill:
        st.session_state.ap_ai_prefill        = None
        st.session_state.ap_show_prefill_form = False
        st.rerun()

    if submitted:
        errors = []
        if not requester.strip():   errors.append("Name / Employee ID required.")
        if not title.strip():       errors.append("Document title required.")
        if not description.strip(): errors.append("Description required.")
        for e in errors:
            st.error(e)
        if not errors:
            req = _create(
                title.strip(), category, subtype,
                description.strip(), urgency, requester.strip()
            )
            # Clear prefill state after successful submit
            st.session_state.ap_ai_prefill        = None
            st.session_state.ap_show_prefill_form = False
            if req["done"]:
                st.success(f"**{req['id']}** auto-approved instantly. ✅")
            else:
                st.success(
                    f"**{req['id']}** submitted — first stop: **{req['chain'][0]}**"
                )

    all_reqs = list(reversed(st.session_state.ap_requests))
    if not all_reqs:
        st.info("No requests yet.")
        return

    st.divider()

    # ── Summary metrics ───────────────────────────────────────────────────────
    counts = {"Pending": 0, "Approved": 0, "Rejected": 0, "Expired": 0}
    for r in all_reqs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending",  counts["Pending"])
    c2.metric("Approved", counts["Approved"])
    c3.metric("Rejected", counts["Rejected"])
    c4.metric("Expired",  counts["Expired"])

    # ── Bulk delete controls ──────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📋 All Requests")

    bulk_col1, bulk_col2, bulk_col3 = st.columns([2, 2, 4])
    with bulk_col1:
        if st.button("🗑️ Delete All Rejected", use_container_width=True):
            rejected_ids = [r["id"] for r in all_reqs if r["status"] == "Rejected"]
            for rid in rejected_ids:
                _delete_request(rid)
            if rejected_ids:
                st.success(f"Deleted {len(rejected_ids)} rejected request(s).")
                st.rerun()
            else:
                st.info("No rejected requests to delete.")
    with bulk_col2:
        if st.button("🗑️ Delete All Expired", use_container_width=True):
            expired_ids = [r["id"] for r in all_reqs if r["status"] == "Expired"]
            for rid in expired_ids:
                _delete_request(rid)
            if expired_ids:
                st.success(f"Deleted {len(expired_ids)} expired request(s).")
                st.rerun()
            else:
                st.info("No expired requests to delete.")

    st.divider()

    for req in all_reqs:
        _request_card_with_delete(req, ctx="sub")


# ── Request card with delete button ──────────────────────────────────────────

def _request_card_with_delete(req: dict, ctx: str = "sub"):
    stage    = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    timer    = _time_left(req["expires_at"]) if not req["done"] else ""
    urg_icon = {"URGENT": "🟡", "CRITICAL": "🔴"}.get(req["urgency"], "")
    rid = req["id"]
    k   = f"{ctx}_{rid}"

    status_icon = {
        "Pending":  "🟡",
        "Approved": "🟢",
        "Rejected": "🔴",
        "Expired":  "⏰",
    }.get(req["status"], "⚪")

    label = f"{status_icon} {rid}  ·  {req['title']}  {urg_icon}"
    if timer:
        label += f"  ·  ⏳ {timer}"

    with st.expander(label, expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Requester**  \n{req['requester']}")
        c2.markdown(f"**Category**  \n{req.get('category','—')} › {req.get('subtype','—')}")
        c3.markdown(f"**Stage**  \n{stage}")
        c4.markdown(f"**Status**  \n{req['status']}")

        st.markdown(f"> {req['description']}")

        if req["chain"]:
            parts = []
            for i, s in enumerate(req["chain"]):
                if req["status"] == "Approved" or i < req["stage_idx"]:
                    parts.append(f"~~{s}~~ ✅")
                elif i == req["stage_idx"] and not req["done"]:
                    parts.append(f"**{s} ⏳**")
                elif req["done"] and i == req["stage_idx"]:
                    parts.append(f"**{s} {'❌' if req['status'] == 'Rejected' else '⏰'}**")
                else:
                    parts.append(s)
            st.markdown("  →  ".join(parts))
        else:
            st.caption("Auto-approved — no chain required.")

        with st.expander("History", key=f"hist_{k}"):
            for entry in req["history"]:
                t    = _fmt(entry.get("time", ""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"`{t}`  **{entry['by']}**: {entry['action']}{note}")

        st.divider()

        confirm_key = f"confirm_del_{rid}"
        is_pending_confirm = st.session_state.ap_confirm_delete.get(rid, False)

        if not is_pending_confirm:
            del_col, _ = st.columns([1, 5])
            with del_col:
                if st.button("🗑️ Delete", key=f"del_btn_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = True
                    st.rerun()
        else:
            st.warning(f"⚠️ Are you sure you want to delete **{rid} — {req['title']}**? This cannot be undone.")
            conf_col1, conf_col2, _ = st.columns([1, 1, 4])
            with conf_col1:
                if st.button("✅ Yes, Delete", key=f"confirm_yes_{k}", use_container_width=True):
                    _delete_request(rid)
                    st.success(f"🗑️ {rid} deleted.")
                    st.rerun()
            with conf_col2:
                if st.button("✖ Cancel", key=f"confirm_no_{k}", use_container_width=True):
                    st.session_state.ap_confirm_delete[rid] = False
                    st.rerun()


# ── Role tab ──────────────────────────────────────────────────────────────────

def _view_role(role: str):
    authed = st.session_state.ap_role_auth.get(role, False)

    if not authed:
        st.subheader(f"🔐 {role} Login")
        col, _ = st.columns([1.5, 3])
        with col:
            pwd = st.text_input("Password", type="password", key=f"pwd_{role}")
            if st.button("Log in", type="primary", use_container_width=True,
                         key=f"login_{role}"):
                if pwd == ROLE_PASSWORDS.get(role, ""):
                    st.session_state.ap_role_auth[role] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        return

    hcol, lcol = st.columns([6, 1])
    with hcol:
        st.subheader(f"Inbox — {role}")
    with lcol:
        if st.button("Log out", key=f"logout_{role}"):
            st.session_state.ap_role_auth[role] = False
            st.rerun()

    ctx = role.replace(" ", "_").lower()

    mine = [
        r for r in reversed(st.session_state.ap_requests)
        if not r["done"] and r["chain"] and r["chain"][r["stage_idx"]] == role
    ]
    handled = [
        r for r in reversed(st.session_state.ap_requests)
        if r["done"] and any(e.get("by") == role for e in r["history"])
    ]

    if not mine:
        st.success("Nothing waiting for your approval right now.")
    else:
        st.markdown(f"**{len(mine)} request(s) awaiting your decision**")
        for req in mine:
            _request_card(req, show_actions=True, ctx=ctx)

    if handled:
        st.divider()
        with st.expander(f"Previously handled ({len(handled)})"):
            for req in handled:
                _request_card(req, show_actions=False, ctx=f"{ctx}_done")


# ── Original request card (used in role tabs — no delete) ─────────────────────

def _request_card(req: dict, show_actions: bool, ctx: str = ""):
    stage    = req["chain"][req["stage_idx"]] if not req["done"] else "—"
    timer    = _time_left(req["expires_at"]) if not req["done"] else ""
    urg_icon = {"URGENT": "🟡", "CRITICAL": "🔴"}.get(req["urgency"], "")
    rid = req["id"]
    k   = f"{ctx}_{rid}"

    label = f"{rid}  ·  {req['title']}  {urg_icon}"
    if timer:
        label += f"  ·  ⏳ {timer}"

    with st.expander(label, expanded=(show_actions and not req["done"])):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Requester**  \n{req['requester']}")
        c2.markdown(f"**Category**  \n{req.get('category','—')} › {req.get('subtype','—')}")
        c3.markdown(f"**Stage**  \n{stage}")
        c4.markdown(f"**Status**  \n{req['status']}")

        st.markdown(f"> {req['description']}")

        if req["chain"]:
            parts = []
            for i, s in enumerate(req["chain"]):
                if req["status"] == "Approved" or i < req["stage_idx"]:
                    parts.append(f"~~{s}~~ ✅")
                elif i == req["stage_idx"] and not req["done"]:
                    parts.append(f"**{s} ⏳**")
                elif req["done"] and i == req["stage_idx"]:
                    parts.append(f"**{s} {'❌' if req['status'] == 'Rejected' else '⏰'}**")
                else:
                    parts.append(s)
            st.markdown("  →  ".join(parts))
        else:
            st.caption("Auto-approved — no chain required.")

        with st.expander("History", key=f"hist_{k}"):
            for entry in req["history"]:
                t    = _fmt(entry.get("time", ""))
                note = f" — {entry['note']}" if entry.get("note") else ""
                st.markdown(f"`{t}`  **{entry['by']}**: {entry['action']}{note}")

        if show_actions and not req["done"]:
            note = st.text_input("Note (optional)", key=f"note_{k}",
                                 placeholder="Reason or comment…")
            ca, cr, _ = st.columns([1, 1, 4])
            with ca:
                if st.button("✅ Approve", key=f"ap_{k}", type="primary",
                             use_container_width=True):
                    _approve(req, note)
                    st.rerun()
            with cr:
                if st.button("❌ Reject", key=f"rj_{k}", use_container_width=True):
                    _reject(req, note)
                    st.rerun()
