# styles.py
import streamlit as st

def apply_global_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=EB+Garamond:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap');

    :root {
        --rust: #8b3a2a;
        --sage: #3d5a4a;
        --gold: #8b6914;
        --paper: #faf7f2;
        --ink: #1a1612;
        --border: #d4c9bc;
    }

    .stApp {
        background: var(--paper);
    }

    h1, h2, h3, h4 {
        font-family: 'Playfair Display', serif;
        color: var(--ink);
        letter-spacing: -0.02em;
    }

    /* Cards */
    .card, .doc-card, .inbox-card {
        background: white;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(139, 58, 42, 0.08);
        transition: all 0.3s ease;
    }
    .card:hover, .doc-card:hover, .inbox-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 30px rgba(139, 58, 42, 0.15);
    }

    /* Buttons */
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(139, 58, 42, 0.25);
    }

    /* Metrics */
    .metric-card {
        background: white;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }

    /* Status Badges */
    .status-pending, .status-granted, .status-rejected, .status-expired, .status-revoked {
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 700;
        font-family: 'DM Mono', monospace;
        letter-spacing: 0.5px;
    }

    /* Hierarchy Bar */
    .hierarchy-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        margin: 16px 0;
    }
    .hier-role {
        padding: 8px 16px;
        border-radius: 9999px;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }

    /* Expander */
    .stExpander {
        border-radius: 12px;
        border: 1px solid var(--border);
    }
    </style>
    """, unsafe_allow_html=True)
