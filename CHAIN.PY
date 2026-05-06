"""
chain_tamper.py  —  Chain Tamper Detection & Integrity Verification
====================================================================
Drop this file into your HelpDesk Pro project folder.

HOW IT WORKS:
1. Every time a chain step is saved (approved/rejected), a SHA-256 hash
   is computed from: step data + timestamp + approver_id + secret salt
2. The hash is stored alongside the step in Supabase
3. On verification, each step is re-hashed and compared
4. If ANYONE edits the Supabase record manually, the hash won't match
5. Admin panel shows a 🔴 TAMPERED warning instantly

SUPABASE SETUP (run this SQL in your Supabase SQL editor):
----------------------------------------------------------
ALTER TABLE chain_requests
    ADD COLUMN IF NOT EXISTS steps_log  JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS chain_hash TEXT;

CREATE TABLE IF NOT EXISTS chain_integrity_log (
    id           BIGSERIAL PRIMARY KEY,
    request_id   BIGINT,
    checked_at   TIMESTAMPTZ DEFAULT NOW(),
    result       TEXT,        -- 'ok' | 'tampered' | 'missing'
    details      JSONB        -- which steps failed
);

USAGE in your app.py / admin page:
-----------------------------------
from chain_tamper import (
    sign_chain_step,
    verify_chain_integrity,
    save_signed_step,
    render_integrity_panel,
)

# When approving a step:
signed_step = sign_chain_step(
    request_id=47,
    step_index=2,
    role="Tech Manager",
    action="approved",
    comment="Read-only access only",
    approver_id="admin_priya",
    timestamp=datetime.now(timezone.utc).isoformat(),
)
save_signed_step(request_id=47, signed_step=signed_step)

# In admin panel:
render_integrity_panel(request_id=47)
"""

import hashlib
import json
import streamlit as st
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── Secret salt (move to st.secrets in production) ────────────────────────────
_SALT = "helpdesk_integrity_salt_2026"   # Change this! Keep it secret.

IST = timezone(timedelta(hours=5, minutes=30))


# ══════════════════════════════════════════════════════════════════════════════
#  CORE HASHING
# ══════════════════════════════════════════════════════════════════════════════

def _compute_step_hash(
    request_id: int,
    step_index: int,
    role: str,
    action: str,
    comment: str,
    approver_id: str,
    timestamp: str,
) -> str:
    """
    Deterministically hash one chain step.
    Any change to any field → completely different hash.
    """
    salt = st.secrets.get("CHAIN_SALT", _SALT)
    raw = (
        f"{salt}"
        f"|request_id={request_id}"
        f"|step={step_index}"
        f"|role={role.strip().lower()}"
        f"|action={action.strip().lower()}"
        f"|comment={comment.strip()}"
        f"|approver={approver_id.strip().lower()}"
        f"|ts={timestamp}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compute_chain_hash(steps: list) -> str:
    """
    Hash the ENTIRE chain (all steps combined).
    Detects reordering, deletion, or addition of steps.
    """
    salt = st.secrets.get("CHAIN_SALT", _SALT)
    chain_str = salt + json.dumps(
        [
            {
                "step": s.get("step_index"),
                "hash": s.get("step_hash"),
            }
            for s in steps
        ],
        sort_keys=True,
    )
    return hashlib.sha256(chain_str.encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
#  SIGN A STEP  (call this when admin approves/rejects)
# ══════════════════════════════════════════════════════════════════════════════

def sign_chain_step(
    request_id: int,
    step_index: int,
    role: str,
    action: str,          # "approved" | "rejected" | "delegated"
    comment: str,
    approver_id: str,
    timestamp: Optional[str] = None,
) -> dict:
    """
    Returns a signed step dict ready to be appended to steps_log in Supabase.

    Example return value:
    {
        "step_index":   2,
        "role":         "Tech Manager",
        "action":       "approved",
        "comment":      "Read-only access only",
        "approver_id":  "admin_priya",
        "timestamp":    "2026-05-01T14:30:00+00:00",
        "step_hash":    "a3f8c2d1e9b47f6...",   ← integrity hash
        "short_hash":   "a3f8c2d1",              ← display version
    }
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    step_hash = _compute_step_hash(
        request_id=request_id,
        step_index=step_index,
        role=role,
        action=action,
        comment=comment,
        approver_id=approver_id,
        timestamp=ts,
    )
    return {
        "step_index":  step_index,
        "role":        role,
        "action":      action,
        "comment":     comment,
        "approver_id": approver_id,
        "timestamp":   ts,
        "step_hash":   step_hash,
        "short_hash":  step_hash[:8],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SAVE SIGNED STEP TO SUPABASE
# ══════════════════════════════════════════════════════════════════════════════

def save_signed_step(request_id: int, signed_step: dict) -> bool:
    """
    Appends a signed step to the chain_requests.steps_log JSONB array.
    Also recomputes and saves the overall chain_hash.
    """
    try:
        db = _get_db()
        if db is None:
            return False

        # Fetch current steps
        resp = db.table("chain_requests").select("steps_log").eq("id", request_id).single().execute()
        existing = resp.data or {}
        steps = existing.get("steps_log") or []

        # Append new signed step
        steps.append(signed_step)

        # Recompute overall chain hash
        chain_hash = _compute_chain_hash(steps)

        # Save back
        db.table("chain_requests").update({
            "steps_log":  steps,
            "chain_hash": chain_hash,
        }).eq("id", request_id).execute()

        st.toast(f"🔐 Step signed & saved (hash: {signed_step['short_hash']})", icon="🔒")
        return True

    except Exception as e:
        st.error(f"Failed to save signed step: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  VERIFY INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════

def verify_chain_integrity(request_id: int) -> dict:
    """
    Fetches the chain from Supabase and verifies every step hash.

    Returns:
    {
        "status":          "ok" | "tampered" | "missing" | "empty",
        "total_steps":     4,
        "verified_steps":  4,
        "failed_steps":    [],   # list of step_index values that failed
        "chain_hash_ok":   True,
        "details":         [{"step_index":0, "ok":True, "expected":"...", "stored":"..."}, ...]
    }
    """
    try:
        db = _get_db()
        if db is None:
            return {"status": "missing", "total_steps": 0, "verified_steps": 0,
                    "failed_steps": [], "chain_hash_ok": False, "details": []}

        resp = db.table("chain_requests").select(
            "steps_log, chain_hash, id"
        ).eq("id", request_id).single().execute()

        if not resp.data:
            return {"status": "missing", "total_steps": 0, "verified_steps": 0,
                    "failed_steps": [], "chain_hash_ok": False, "details": []}

        row = resp.data
        steps = row.get("steps_log") or []
        stored_chain_hash = row.get("chain_hash") or ""

        if not steps:
            return {"status": "empty", "total_steps": 0, "verified_steps": 0,
                    "failed_steps": [], "chain_hash_ok": False, "details": []}

        # Verify each step individually
        details = []
        failed_steps = []

        for step in steps:
            idx         = step.get("step_index", -1)
            stored_hash = step.get("step_hash", "")
            expected    = _compute_step_hash(
                request_id=request_id,
                step_index=idx,
                role=step.get("role", ""),
                action=step.get("action", ""),
                comment=step.get("comment", ""),
                approver_id=step.get("approver_id", ""),
                timestamp=step.get("timestamp", ""),
            )
            ok = (expected == stored_hash)
            if not ok:
                failed_steps.append(idx)

            details.append({
                "step_index": idx,
                "role":       step.get("role", "?"),
                "action":     step.get("action", "?"),
                "approver":   step.get("approver_id", "?"),
                "timestamp":  step.get("timestamp", ""),
                "ok":         ok,
                "stored":     stored_hash[:12] + "…",
                "expected":   expected[:12] + "…",
                "short_hash": stored_hash[:8],
            })

        # Verify overall chain hash
        recomputed_chain_hash = _compute_chain_hash(steps)
        chain_hash_ok = (recomputed_chain_hash == stored_chain_hash)

        status = "ok" if (not failed_steps and chain_hash_ok) else "tampered"

        # Log result to Supabase
        _log_integrity_check(request_id, status, failed_steps)

        return {
            "status":          status,
            "total_steps":     len(steps),
            "verified_steps":  len(steps) - len(failed_steps),
            "failed_steps":    failed_steps,
            "chain_hash_ok":   chain_hash_ok,
            "details":         details,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "total_steps": 0,
                "verified_steps": 0, "failed_steps": [], "chain_hash_ok": False, "details": []}


def verify_all_chains() -> list:
    """
    Verify integrity of ALL chain requests. Returns summary list.
    Used for the admin integrity overview dashboard.
    """
    try:
        db = _get_db()
        if db is None:
            return []
        resp = db.table("chain_requests").select("id, steps_log, chain_hash").execute()
        results = []
        for row in (resp.data or []):
            rid = row["id"]
            result = verify_chain_integrity(rid)
            results.append({"request_id": rid, **result})
        return results
    except Exception as e:
        st.error(f"Bulk verify error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  INTEGRITY LOG
# ══════════════════════════════════════════════════════════════════════════════

def _log_integrity_check(request_id: int, result: str, failed_steps: list):
    """Save integrity check result to chain_integrity_log table."""
    try:
        db = _get_db()
        if db:
            db.table("chain_integrity_log").insert({
                "request_id": request_id,
                "result":     result,
                "details":    {"failed_steps": failed_steps},
            }).execute()
    except Exception:
        pass  # Non-critical


def get_integrity_history(request_id: int) -> list:
    """Fetch past integrity check results for a request."""
    try:
        db = _get_db()
        if db is None:
            return []
        resp = db.table("chain_integrity_log").select("*").eq(
            "request_id", request_id
        ).order("checked_at", desc=True).limit(10).execute()
        return resp.data or []
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  STREAMLIT UI — RENDER INTEGRITY PANEL
# ══════════════════════════════════════════════════════════════════════════════

def render_integrity_panel(request_id: int):
    """
    Full Streamlit UI for chain integrity verification.
    Call this inside any admin expander or tab.

    Usage:
        from chain_tamper import render_integrity_panel
        render_integrity_panel(request_id=47)
    """
    st.markdown("""
    <style>
    .integrity-ok {
        background: linear-gradient(135deg, #f0fdf4, #dcfce7);
        border: 2px solid #86efac;
        border-radius: 14px;
        padding: 16px 20px;
    }
    .integrity-tampered {
        background: linear-gradient(135deg, #fff1f2, #ffe4e6);
        border: 2px solid #fda4af;
        border-radius: 14px;
        padding: 16px 20px;
    }
    .integrity-missing {
        background: #fffbeb;
        border: 2px solid #fcd34d;
        border-radius: 14px;
        padding: 16px 20px;
    }
    .step-ok {
        background: white;
        border-left: 4px solid #22c55e;
        border-radius: 8px;
        padding: 10px 16px;
        margin: 6px 0;
        font-size: 13px;
    }
    .step-tampered {
        background: #fff1f2;
        border-left: 4px solid #ef4444;
        border-radius: 8px;
        padding: 10px 16px;
        margin: 6px 0;
        font-size: 13px;
    }
    .hash-display {
        font-family: 'Courier New', monospace;
        font-size: 12px;
        background: #f3f4f6;
        padding: 2px 8px;
        border-radius: 4px;
        color: #374151;
    }
    .chain-hash-ok {
        display: inline-block;
        background: #dcfce7;
        color: #166534;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
    }
    .chain-hash-fail {
        display: inline-block;
        background: #fee2e2;
        color: #991b1b;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("#### 🔐 Chain Integrity Verification")

    col_verify, col_history, _ = st.columns([1.5, 1.5, 3])
    with col_verify:
        run_check = st.button(
            "🔍 Verify Now",
            key=f"verify_btn_{request_id}",
            use_container_width=True
        )
    with col_history:
        show_history = st.button(
            "📋 Check History",
            key=f"history_btn_{request_id}",
            use_container_width=True
        )

    if run_check:
        with st.spinner("🔐 Computing hashes and verifying integrity…"):
            result = verify_chain_integrity(request_id)
        _render_verification_result(result, request_id)

    if show_history:
        history = get_integrity_history(request_id)
        _render_integrity_history(history)


def _render_verification_result(result: dict, request_id: int):
    """Render the full verification result UI."""
    status = result.get("status", "error")

    # ── Status banner ─────────────────────────────────────────────────────────
    if status == "ok":
        st.markdown(f"""
        <div class='integrity-ok'>
            <div style='display:flex; align-items:center; gap:12px;'>
                <span style='font-size:36px;'>✅</span>
                <div>
                    <p style='margin:0; font-weight:800; font-size:17px; color:#14532d;'>
                        Chain Integrity: VERIFIED
                    </p>
                    <p style='margin:4px 0 0; font-size:13px; color:#166534;'>
                        All {result['total_steps']} steps verified.
                        No tampering detected. This chain is authentic.
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif status == "tampered":
        failed = result.get("failed_steps", [])
        st.markdown(f"""
        <div class='integrity-tampered'>
            <div style='display:flex; align-items:center; gap:12px;'>
                <span style='font-size:36px;'>🔴</span>
                <div>
                    <p style='margin:0; font-weight:800; font-size:17px; color:#7f1d1d;'>
                        ⚠️ CHAIN INTEGRITY COMPROMISED
                    </p>
                    <p style='margin:4px 0 0; font-size:13px; color:#991b1b;'>
                        {len(failed)} step(s) failed hash verification.
                        Steps {failed} may have been manually edited in the database.
                        This chain cannot be trusted for audit purposes.
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif status == "missing":
        st.markdown("""
        <div class='integrity-missing'>
            <p style='margin:0; font-weight:700; color:#92400e;'>
                ⚠️ No chain record found for this request ID.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    elif status == "empty":
        st.info("ℹ️ No signed steps found yet. Steps will appear here after approvals.", icon="🔐")
        return

    else:
        st.error(f"Verification error: {result.get('error', 'Unknown')}")
        return

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Metrics row ───────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Steps", result["total_steps"])
    with m2:
        st.metric("Verified ✅", result["verified_steps"])
    with m3:
        failed_count = len(result.get("failed_steps", []))
        st.metric("Tampered 🔴", failed_count)
    with m4:
        chain_ok = result.get("chain_hash_ok", False)
        st.markdown(
            f"<br><span class='{'chain-hash-ok' if chain_ok else 'chain-hash-fail'}'>"
            f"{'✅ Chain Hash OK' if chain_ok else '🔴 Chain Hash FAIL'}</span>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── Per-step breakdown ────────────────────────────────────────────────────
    st.markdown("**Step-by-Step Verification:**")
    for step in result.get("details", []):
        ok        = step["ok"]
        action_icon = "✅" if step["action"] == "approved" else "❌"
        ts_fmt    = _fmt_ts(step["timestamp"])

        if ok:
            st.markdown(f"""
            <div class='step-ok'>
                <strong>Step {step['step_index'] + 1} — {step['role']}</strong>
                &nbsp;{action_icon} {step['action'].upper()}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <span style='color:#6b7280;'>by {step['approver']}</span>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <span style='color:#6b7280;'>{ts_fmt}</span>
                <br>
                <span style='color:#22c55e; font-size:12px;'>✅ Hash verified</span>
                &nbsp;
                <span class='hash-display'>{step['short_hash']}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='step-tampered'>
                <strong>Step {step['step_index'] + 1} — {step['role']}</strong>
                &nbsp;{action_icon} {step['action'].upper()}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <span style='color:#6b7280;'>by {step['approver']}</span>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <span style='color:#6b7280;'>{ts_fmt}</span>
                <br>
                <span style='color:#ef4444; font-size:12px; font-weight:700;'>
                    🔴 HASH MISMATCH — This step may have been tampered with!
                </span>
                <br>
                <span style='font-size:12px; color:#6b7280;'>
                    Stored: <span class='hash-display'>{step['stored']}</span>
                    &nbsp;Expected: <span class='hash-display'>{step['expected']}</span>
                </span>
            </div>
            """, unsafe_allow_html=True)

    # ── What this means ───────────────────────────────────────────────────────
    if status == "tampered":
        st.markdown("---")
        st.markdown("#### 🚨 What Does This Mean?")
        st.markdown("""
        A hash mismatch means the data stored in Supabase **no longer matches**
        what was there when the step was originally approved. This can happen if:

        - Someone edited the Supabase record directly via the dashboard
        - A database migration script modified the data
        - A bug caused data corruption
        - **Intentional tampering with the audit trail**

        **Recommended actions:**
        1. Check Supabase logs for who edited this record and when
        2. Compare with your backup/export CSV
        3. Flag this chain as under review — do not use for compliance
        4. Contact your database administrator
        """)


def _render_integrity_history(history: list):
    """Show past integrity check results."""
    if not history:
        st.info("No integrity checks recorded yet.", icon="📋")
        return

    st.markdown("**Past Integrity Checks:**")
    for row in history:
        result  = row.get("result", "unknown")
        checked = _fmt_ts(row.get("checked_at", ""))
        icon    = "✅" if result == "ok" else "🔴" if result == "tampered" else "⚠️"
        color   = "#166534" if result == "ok" else "#991b1b" if result == "tampered" else "#92400e"
        details = row.get("details", {})
        failed  = details.get("failed_steps", [])

        st.markdown(
            f"<div style='padding:8px 14px; background:white; border-radius:8px; "
            f"margin:4px 0; border-left:3px solid {color}; font-size:13px;'>"
            f"{icon} <strong>{result.upper()}</strong> — {checked}"
            f"{'  |  Failed steps: ' + str(failed) if failed else ''}"
            f"</div>",
            unsafe_allow_html=True
        )


# ══════════════════════════════════════════════════════════════════════════════
#  BULK INTEGRITY DASHBOARD  (for admin overview page)
# ══════════════════════════════════════════════════════════════════════════════

def render_integrity_dashboard():
    """
    Admin-level overview of ALL chain integrity.
    Call this in a dedicated admin tab.

    Usage:
        from chain_tamper import render_integrity_dashboard
        render_integrity_dashboard()
    """
    st.markdown("## 🔐 Chain Integrity Dashboard")
    st.markdown(
        "<p style='color:#6b7280;'>Verify tamper-detection hashes across all chain requests.</p>",
        unsafe_allow_html=True
    )
    st.markdown("---")

    if st.button("🔍 Run Full Integrity Scan", type="primary", key="bulk_verify_btn"):
        with st.spinner("🔐 Scanning all chains… this may take a moment."):
            results = verify_all_chains()

        if not results:
            st.info("No chain requests found.", icon="📭")
            return

        total    = len(results)
        ok       = sum(1 for r in results if r["status"] == "ok")
        tampered = sum(1 for r in results if r["status"] == "tampered")
        empty    = sum(1 for r in results if r["status"] in ("empty", "missing"))

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Chains", total)
        with c2:
            st.metric("✅ Verified", ok)
        with c3:
            st.metric("🔴 Tampered", tampered)
        with c4:
            st.metric("⚠️ No Data", empty)

        if tampered > 0:
            st.error(
                f"🚨 {tampered} chain(s) show signs of tampering! "
                "Review immediately.",
                icon="🔴"
            )
        else:
            st.success("✅ All chains verified. No tampering detected.", icon="🔐")

        st.markdown("---")
        st.markdown("### Scan Results")

        for r in results:
            rid    = r["request_id"]
            status = r["status"]
            icon   = "✅" if status == "ok" else "🔴" if status == "tampered" else "⚠️"
            color  = "#f0fdf4" if status == "ok" else "#fff1f2" if status == "tampered" else "#fffbeb"
            border = "#22c55e" if status == "ok" else "#ef4444" if status == "tampered" else "#fcd34d"

            st.markdown(
                f"<div style='padding:12px 18px; background:{color}; "
                f"border-left:4px solid {border}; border-radius:8px; "
                f"margin:6px 0; display:flex; justify-content:space-between; align-items:center;'>"
                f"<span>{icon} <strong>Request #{rid}</strong> — {status.upper()}</span>"
                f"<span style='font-size:12px; color:#6b7280;'>"
                f"{r['verified_steps']}/{r['total_steps']} steps verified"
                f"{'  |  Failed: ' + str(r['failed_steps']) if r['failed_steps'] else ''}"
                f"</span>"
                f"</div>",
                unsafe_allow_html=True
            )


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER: DEMO / TESTING
# ══════════════════════════════════════════════════════════════════════════════

def demo_sign_and_verify():
    """
    Standalone demo — shows how signing and verification works.
    Call this from a Streamlit page to test without a real DB.
    """
    st.markdown("### 🧪 Tamper Detection Demo")
    st.markdown("This demo shows how hashing works without a real database.")

    st.markdown("#### Step 1 — Sign a step")

    col1, col2 = st.columns(2)
    with col1:
        role        = st.text_input("Role", value="Tech Manager", key="demo_role")
        action      = st.selectbox("Action", ["approved", "rejected"], key="demo_action")
        approver_id = st.text_input("Approver ID", value="admin_priya", key="demo_approver")
    with col2:
        comment     = st.text_area("Comment", value="Approved — read-only access", key="demo_comment", height=68)

    if st.button("🔐 Sign This Step", key="demo_sign_btn"):
        signed = sign_chain_step(
            request_id  = 999,
            step_index  = 0,
            role        = role,
            action      = action,
            comment     = comment,
            approver_id = approver_id,
        )
        st.session_state["demo_signed"] = signed
        st.success("Step signed!")
        st.json(signed)

    # ── Tamper simulation ─────────────────────────────────────────────────────
    if st.session_state.get("demo_signed"):
        st.markdown("---")
        st.markdown("#### Step 2 — Simulate Tampering")
        st.markdown(
            "Imagine someone goes into Supabase and edits the action from "
            "'approved' to 'rejected'. Let's verify what happens:"
        )

        original = st.session_state["demo_signed"]

        # Tampered version — action changed
        tampered = dict(original)
        tampered["action"] = "rejected"   # ← simulated edit in DB

        # Recompute hash on tampered data
        recomputed = _compute_step_hash(
            request_id  = 999,
            step_index  = tampered["step_index"],
            role        = tampered["role"],
            action      = tampered["action"],    # ← now "rejected"
            comment     = tampered["comment"],
            approver_id = tampered["approver_id"],
            timestamp   = tampered["timestamp"],
        )
        stored_hash = original["step_hash"]
        match = (recomputed == stored_hash)

        st.markdown(f"""
        <div style='padding:16px; background:{"#f0fdf4" if match else "#fff1f2"};
             border-left:4px solid {"#22c55e" if match else "#ef4444"};
             border-radius:10px; margin-top:12px;'>
            <p style='margin:0; font-weight:700; font-size:15px; color:{"#166534" if match else "#7f1d1d"}'>
                {"✅ Hash matches — no tampering" if match else "🔴 HASH MISMATCH — Tampering detected!"}
            </p>
            <p style='margin:6px 0 0; font-size:13px; color:#6b7280;'>
                Original action: <strong>approved</strong> → Tampered to: <strong>rejected</strong>
            </p>
            <p style='margin:4px 0 0; font-size:12px; font-family:monospace; color:#374151;'>
                Stored hash:    {stored_hash[:20]}…<br>
                Recomputed:     {recomputed[:20]}…
            </p>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_db():
    """Get Supabase client from your existing app setup."""
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _fmt_ts(ts: str) -> str:
    """Format ISO timestamp to readable IST string."""
    try:
        normalised = ts.strip().replace(" ", "T").replace("Z", "+00:00")
        if "+" not in normalised[10:]:
            normalised += "+00:00"
        dt = datetime.fromisoformat(normalised)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return ts
