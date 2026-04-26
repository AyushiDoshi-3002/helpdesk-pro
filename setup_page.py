"""
Setup & Configuration page – no Anthropic API needed.
"""
import streamlit as st
import db


def show():
    st.markdown("# ⚙️ Setup & Configuration")
    st.markdown(
        "<p style='color:#6b7280'>Follow these steps to get HelpDesk Pro fully running.</p>",
        unsafe_allow_html=True,
    )

    with st.expander("📁 Step 1 — Configure Secrets (.streamlit/secrets.toml)", expanded=True):
        st.markdown("Create **`.streamlit/secrets.toml`** in your project root:")
        st.code(
            '[secrets]\nSUPABASE_URL   = "https://xxxx.supabase.co"\nSUPABASE_KEY   = "eyJhbGci..."\nADMIN_PASSWORD = "your_secure_password"',
            language="toml",
        )
        st.info("Get Supabase URL & Key from your project → Settings → API.", icon="ℹ️")

    with st.expander("🗄️ Step 2 — Create Supabase Table", expanded=True):
        st.markdown("Go to **Supabase Dashboard → SQL Editor** and run:")
        st.code(db.SCHEMA_SQL, language="sql")

    with st.expander("📦 Step 3 — Install Python Dependencies"):
        st.code("pip install streamlit supabase PyPDF2 requests", language="bash")
        st.info("No AI API keys required — answers matched directly from the PDF!", icon="✅")

    with st.expander("▶️ Step 4 — Run the App"):
        st.code("streamlit run app.py", language="bash")

    st.markdown("---")
    st.markdown("### 🔌 Connection Status")

    col1, col2 = st.columns(2)
    with col1:
        if st.secrets.get("SUPABASE_URL", ""):
            st.success("✅ Supabase URL configured")
        else:
            st.error("❌ Supabase URL missing")
    with col2:
        if st.secrets.get("SUPABASE_KEY", ""):
            st.success("✅ Supabase Key configured")
        else:
            st.error("❌ Supabase Key missing")

    st.markdown("---")

    if st.button("🧪 Test Database Connection"):
        try:
            client = db.get_client()
            if client is None:
                st.error("Supabase client could not be created. Check credentials.")
            else:
                client.table("tickets").select("id").limit(1).execute()
                st.success("✅ Database connected and tickets table accessible!")
        except Exception as e:
            st.error(f"Database test failed: {e}")

    if st.button("📄 Test Knowledge Base (PDF)"):
        from qa_engine import load_qa_pairs
        pairs = load_qa_pairs()
        if pairs:
            st.success(f"✅ Knowledge base loaded — {len(pairs)} Q&A pairs found!")
            with st.expander("Preview first 5 questions"):
                for p in pairs[:5]:
                    st.markdown(f"**Q{p['num']}.** {p['question']}")
        else:
            st.error("No Q&A pairs could be loaded.")
