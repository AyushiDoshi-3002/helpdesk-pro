"""
agents.py – all Claude API agent logic
"""
import json
import re
import requests
import streamlit as st

from utils import CHANGE_TYPES, MODEL, update_task, get_by_status


def _call_claude(system: str, user: str, max_tokens: int = 500) -> dict:
    """Call Claude API and return parsed JSON response."""
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=30,
        )
        data = resp.json()
        raw = "".join(b["text"] for b in (data.get("content") or []) if b.get("type") == "text")
        raw = raw.strip()
        # Strip markdown code fences
        raw = re.sub(r"^```json?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        return {"decision": "Escalate_Human", "reason": f"Agent error: {e}", "risk": "Medium"}


# ── Agent runners ─────────────────────────────────────────────────────────────

def run_classifier(task: dict):
    type_info = CHANGE_TYPES.get(task.get("request_type", ""), {})
    result = _call_claude(
        system="""You are a change management classifier. Analyze and return ONLY raw JSON (no markdown):
{
  "category": "one of [docs,tech,security,api,finance,policy,hr,legal]",
  "risk": "one of [Low,Medium,High,Critical]",
  "involves_security": false,
  "involves_external": false,
  "summary": "one-sentence plain English summary max 20 words",
  "routing_note": "one sentence explaining routing decision",
  "auto_pass_senior": false
}""",
        user=f"Title: {task['title']}\nType: {task['request_type']}\nDept: {task['department']}\nDesc: {task['description']}",
        max_tokens=300,
    )

    needs_ceo = (
        result.get("involves_security")
        or result.get("involves_external")
        or type_info.get("needs_ceo", False)
        or result.get("risk") in ("High", "Critical")
    )

    sr = dict(task.get("stage_results", {}))
    sr["classifier"] = {
        "agent": "System Classifier",
        "action": "Classified and routed",
        "decision": "Routed",
        "category": result.get("category", "tech"),
        "risk": result.get("risk", "Medium"),
        "involves_security": result.get("involves_security", False),
        "involves_external": result.get("involves_external", False),
        "summary": result.get("summary", ""),
        "routing_note": result.get("routing_note", ""),
        "auto_pass_senior": result.get("auto_pass_senior", False),
        "needs_ceo": needs_ceo,
    }
    update_task(task["id"], {
        "status": "Senior Review",
        "stage": "senior",
        "risk_level": result.get("risk", "Medium"),
        "stage_results": sr,
    })


def run_senior(task: dict):
    cls = task.get("stage_results", {}).get("classifier", {})
    sr = dict(task.get("stage_results", {}))

    if cls.get("auto_pass_senior"):
        sr["senior"] = {
            "agent": "Senior Agent",
            "action": "Auto-passed (low risk)",
            "decision": "Approve",
            "reason": "Low-risk internal documentation — auto-approved at senior level.",
            "risk": cls.get("risk", "Low"),
            "skipped": True,
        }
        update_task(task["id"], {"status": "TechLead Review", "stage": "techlead", "stage_results": sr})
        return

    result = _call_claude(
        system="""You are a Senior Engineer reviewing a change request. Return ONLY raw JSON:
{"decision":"Approve or Reject","reason":"1-2 sentences","notes":"brief technical note for Tech Lead"}""",
        user=f"Title: {task['title']}\nType: {task['request_type']}\nDept: {task['department']}\nClassifier summary: {cls.get('summary','')}\nRisk: {cls.get('risk','Medium')}\nDesc: {task['description']}",
    )

    sr["senior"] = {
        "agent": "Senior Agent",
        "action": "Reviewed change quality",
        "decision": result.get("decision", "Approve"),
        "reason": result.get("reason", ""),
        "notes": result.get("notes", ""),
        "risk": cls.get("risk", "Medium"),
    }

    if result.get("decision") == "Reject":
        update_task(task["id"], {"status": "Rejected", "stage": "senior", "stage_results": sr})
    else:
        update_task(task["id"], {"status": "TechLead Review", "stage": "techlead", "stage_results": sr})


def run_techlead(task: dict):
    cls = task.get("stage_results", {}).get("classifier", {})
    snr = task.get("stage_results", {}).get("senior", {})
    sr  = dict(task.get("stage_results", {}))
    needs_ceo = cls.get("needs_ceo", False)

    result = _call_claude(
        system="""You are a Tech Lead in a change management pipeline. Return ONLY raw JSON:
{"decision":"Approve or Reject","reason":"1-2 sentences","cto_email_body":"2-3 sentence email to CTO/CEO explaining the change and what they need to decide. Write as if emailing a busy executive — clear, direct, no jargon.","technical_note":"one line technical context"}""",
        user=f"Title: {task['title']}\nType: {task['request_type']}\nDept: {task['department']}\nRisk: {cls.get('risk','Medium')}\nSecurity: {cls.get('involves_security')}\nExternal: {cls.get('involves_external')}\nNeeds CEO: {needs_ceo}\nSenior notes: {snr.get('notes','')}\nDesc: {task['description']}",
        max_tokens=500,
    )

    sr["techlead"] = {
        "agent": "Tech Lead Agent",
        "action": "Validated technical safety",
        "decision": result.get("decision", "Approve"),
        "reason": result.get("reason", ""),
        "cto_email_body": result.get("cto_email_body", ""),
        "technical_note": result.get("technical_note", ""),
        "needs_ceo": needs_ceo,
    }

    if result.get("decision") == "Reject":
        update_task(task["id"], {"status": "Rejected", "stage": "techlead", "stage_results": sr})
        return

    next_status = "CEO Review" if needs_ceo else "CTO Review"
    update_task(task["id"], {"status": next_status, "stage": "cto", "stage_results": sr})


def run_cto(task: dict):
    cls  = task.get("stage_results", {}).get("classifier", {})
    tl   = task.get("stage_results", {}).get("techlead", {})
    sr   = dict(task.get("stage_results", {}))
    needs_ceo = cls.get("needs_ceo", False)
    role = "CEO" if needs_ceo else "CTO"

    result = _call_claude(
        system=f"""You are the {role} reviewing an escalated change. Return ONLY raw JSON:
{{"decision":"Approve or Reject or Escalate_Human","reason":"1-2 sentences","risk_assessment":"Low or Medium or High","requires_human_approval":true}}
Auto-approve ONLY if risk is genuinely Low and routine internal change.""",
        user=f"Briefing from Tech Lead:\n{tl.get('cto_email_body','')}\nTechnical note: {tl.get('technical_note','')}\nTitle: {task['title']}\nType: {task['request_type']}\nRisk: {cls.get('risk','Medium')}\nSecurity: {cls.get('involves_security')}\nExternal: {cls.get('involves_external')}\nDesc: {task['description']}",
    )

    sr["cto"] = {
        "agent": f"{role} Agent",
        "action": f"Final review as {role}",
        "decision": result.get("decision", "Escalate_Human"),
        "reason": result.get("reason", ""),
        "risk": result.get("risk_assessment", "Medium"),
        "role": role,
    }

    decision = result.get("decision", "Escalate_Human")

    if decision == "Reject":
        update_task(task["id"], {"status": "Rejected", "stage": "cto", "stage_results": sr})
        return

    if decision == "Approve" and not result.get("requires_human_approval", True):
        sr["human"] = {
            "agent": "Auto",
            "decision": "Approved",
            "reason": f"Auto-approved by {role} agent (low risk).",
        }
        update_task(task["id"], {"status": "Approved", "stage": "kb", "stage_results": sr})
        run_kb_for_task(task["id"], sr)
        return

    update_task(task["id"], {"status": "Awaiting Approval", "stage": "human", "stage_results": sr})


def run_kb_for_task(task_id: int, sr: dict):
    sr["kb"] = {"status": "updated", "decision": "Done", "written_at": __import__("datetime").datetime.now().isoformat()}
    update_task(task_id, {"status": "Done", "stage_results": sr})


# ── Heartbeat: advance all queued tasks ───────────────────────────────────────

QUEUE = [
    ("Classifying",     run_classifier),
    ("Senior Review",   run_senior),
    ("TechLead Review", run_techlead),
    ("CTO Review",      run_cto),
    ("CEO Review",      run_cto),
]


def run_heartbeat_tick() -> int:
    """Run one heartbeat — advance up to 2 tasks per stage. Returns count processed."""
    processed = 0
    for status, runner in QUEUE:
        tasks = get_by_status(status)[:2]
        for t in tasks:
            try:
                runner(dict(t))   # pass a snapshot so mutations go through update_task
                processed += 1
            except Exception as e:
                st.error(f"Agent error on task #{t['id']}: {e}")
    return processed
