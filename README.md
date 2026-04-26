# 🤖 HelpDesk Pro — Python Q&A + Ticket System

A Streamlit app that lets employees search a Python knowledge base (PDF) powered by Claude AI, and raise support tickets stored in Supabase when no answer is found.

---

## Features

| Feature | Description |
|---|---|
| 🔍 AI Q&A Search | Employees ask questions answered from your PDF using Claude AI |
| 🎫 Ticket Raise | If no answer found, employee fills a form (User ID, Role, Priority) |
| 🛡️ Admin Panel | Admins log in, view all tickets, update status, add notes |
| 🗄️ Supabase DB | All tickets stored and managed in Supabase |
| 📊 Dashboard | Stats — total, open, in-progress, resolved tickets |

---

## Quick Start

### 1. Clone / copy the files

```
qa_system/
├── app.py               # Main Streamlit entry point
├── qa_engine.py         # AI Q&A logic (Claude + PDF)
├── db.py                # Supabase database helpers
├── requirements.txt
├── .streamlit/
│   └── secrets.toml     # Your private keys (DO NOT commit)
└── pages/
    ├── employee_portal.py
    ├── admin_panel.py
    └── setup_page.py
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure secrets

Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and fill in:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
SUPABASE_URL      = "https://xxxx.supabase.co"
SUPABASE_KEY      = "eyJhbGci..."
ADMIN_PASSWORD    = "your_secure_password"
```

### 4. Create Supabase table

In Supabase → SQL Editor, run:

```sql
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
```

### 5. Run

```bash
streamlit run app.py
```

---

## How It Works

1. **Employee searches** → Claude reads the Python PDF and answers
2. **If no answer** → Form appears to create a ticket
3. **Ticket stored** in Supabase with User ID, Job Role, Priority
4. **Admin logs in** (password-protected) → Sees all tickets
5. **Admin updates** status (Open → In Progress → Resolved) and adds notes

---

## Customising the Knowledge Base PDF

Edit `qa_engine.py` and change `PDF_URL` to point to your own document.

---

## Security Notes

- Move `ADMIN_PASSWORD` to `st.secrets` (already done via secrets.toml)
- Never commit `secrets.toml` — add it to `.gitignore`
- For production, consider Supabase Row Level Security (RLS)
