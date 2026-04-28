# 🧠 Smart Approval Pipeline

A Streamlit-based agentic change management system with Claude AI agents.

## File Structure

```
smart_pipeline/
├── app.py              ← Entry point (run this)
├── utils.py            ← Shared helpers, DB, constants
├── agents.py           ← All Claude API agent logic
├── requirements.txt
└── pages/
    ├── __init__.py
    ├── submit.py       ← Submit Request page
    ├── pipeline.py     ← Live Pipeline page
    ├── approval.py     ← Your Approval page
    └── history.py      ← History page
```

## Setup & Run

```bash
cd smart_pipeline
pip install -r requirements.txt
streamlit run app.py
```

## Usage

1. **Submit Request** — Fill out the form with change details
2. **Live Pipeline → ⚡ Run Agents Now** — Click to advance tasks through the AI agent chain
3. **Your Approval** — Login with password `admin123` to approve/reject tasks
4. **History** — View completed decisions

## Agent Chain

| Agent | Type | Role |
|-------|------|------|
| 🔍 System Classifier | AUTO | Assigns risk & category |
| 👨‍💼 Senior Agent | AUTO | Reviews quality (auto-pass for low risk) |
| 🧑‍🔧 Tech Lead Agent | AUTO | Validates safety, drafts executive briefing |
| 🏛️ CTO / CEO Agent | AUTO | Makes final call or escalates |
| ✅ Your Approval | **MANUAL** | The only human step |
| 📚 KB Sync | AUTO | Writes to knowledge base |

## Notes

- The app uses `st.session_state` for in-memory storage (resets on restart)
- Admin password: `admin123`
- Agents run when you click **⚡ Run Agents Now** in the Live Pipeline tab
- The Anthropic API key must be set in your environment or Streamlit secrets
