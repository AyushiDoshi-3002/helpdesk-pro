"""
INTEGRATION PATCH — add Doc Visibility tab to your existing app.py
Apply the 4 changes below. No other code needs to change.
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 1 — Add this import near the top of app.py
# (alongside your existing `from approval_pipeline import ...`)
# ══════════════════════════════════════════════════════════════════════════════

from doc_visibility import page_doc_visibility, DOC_VISIBILITY_SCHEMA_SQL


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 2 — Add the new page to the sidebar radio list
# Find this block in your app.py and add the new entry:
# ══════════════════════════════════════════════════════════════════════════════

page = st.radio("Navigation", [
    "🔍 Employee Portal",
    "🛡️ Admin Panel",
    "📊 Analytics",
    "🕳️ Knowledge Gap Report",
    "📋 Approval Pipeline",
    "📂 Doc Visibility",          # ← ADD THIS LINE
    "⚙️ Setup / Config",
], label_visibility="collapsed")


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 3 — Add the routing at the bottom of app.py
# Find the if/elif chain and add:
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📂 Doc Visibility":
    page_doc_visibility()


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 4 — Add the SQL to page_setup() so admins can create the table
# Inside your page_setup() function, find the SCHEMA_SQL expander and add:
# ══════════════════════════════════════════════════════════════════════════════

with st.expander("Create doc_visibility Table (new)", expanded=False):
    st.code(DOC_VISIBILITY_SCHEMA_SQL, language="sql")


# ══════════════════════════════════════════════════════════════════════════════
# SUPABASE — Run this SQL in your Supabase SQL Editor
# ══════════════════════════════════════════════════════════════════════════════
"""
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
