import streamlit as st

st.set_page_config(
    page_title="HelpDesk Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- Custom CSS ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
h1, h2, h3, .stTitle {
    font-family: 'Syne', sans-serif !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0c29, #302b63, #24243e);
    color: white;
}
section[data-testid="stSidebar"] * { color: white !important; }
section[data-testid="stSidebar"] .stRadio label { font-size: 15px; }

/* Main background */
.main { background: #f8f7ff; }

/* Cards */
.card {
    background: white;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 4px 24px rgba(48,43,99,0.08);
    margin-bottom: 20px;
    border-left: 4px solid #7c3aed;
}

/* Answer box */
.answer-box {
    background: linear-gradient(135deg, #ede9fe, #ddd6fe);
    border-radius: 12px;
    padding: 20px;
    border-left: 4px solid #7c3aed;
    font-size: 15px;
    line-height: 1.7;
    color: #1e1b4b;
}

/* No answer box */
.no-answer-box {
    background: #fff7ed;
    border-radius: 12px;
    padding: 16px 20px;
    border-left: 4px solid #f97316;
    color: #7c2d12;
    font-size: 14px;
}

/* Ticket badge */
.badge-open { background: #fef3c7; color: #92400e; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge-inprogress { background: #dbeafe; color: #1e40af; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge-resolved { background: #d1fae5; color: #065f46; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }

/* Priority badge */
.prio-high { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; }
.prio-medium { background: #fef9c3; color: #854d0e; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; }
.prio-low { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; }

/* Primary button */
div.stButton > button {
    background: linear-gradient(135deg, #7c3aed, #5b21b6);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
}
div.stButton > button:hover {
    background: linear-gradient(135deg, #6d28d9, #4c1d95);
    box-shadow: 0 4px 16px rgba(124,58,237,0.4);
}

/* Input fields */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    border-radius: 10px !important;
    border: 1.5px solid #e0e7ff !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #7c3aed !important;
    box-shadow: 0 0 0 3px rgba(124,58,237,0.12) !important;
}

/* Metric cards */
.metric-card {
    background: white;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.metric-number { font-family: 'Syne', sans-serif; font-size: 36px; font-weight: 800; color: #7c3aed; }
.metric-label { font-size: 13px; color: #6b7280; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ---------- Pages ----------
from pages import employee_portal, admin_panel, setup_page

def main():
    with st.sidebar:
        st.markdown("## 🤖 HelpDesk Pro")
        st.markdown("---")
        page = st.radio(
            "Navigation",
            ["🔍 Employee Portal", "🛡️ Admin Panel", "⚙️ Setup / Config"],
            index=0
        )
        st.markdown("---")
        st.markdown(
            "<small style='opacity:0.6'>Powered by Claude AI + Supabase</small>",
            unsafe_allow_html=True
        )

    if page == "🔍 Employee Portal":
        employee_portal.show()
    elif page == "🛡️ Admin Panel":
        admin_panel.show()
    elif page == "⚙️ Setup / Config":
        setup_page.show()

if __name__ == "__main__":
    main()
