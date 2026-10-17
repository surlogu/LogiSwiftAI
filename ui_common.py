"""Small shared helpers for the Streamlit multipage application."""
import os
import streamlit as st


def configure_page(title, icon):
    st.set_page_config(page_title=title, page_icon=icon, layout='wide')
    st.markdown('''<style>
    :root { color-scheme: dark; }
    .stApp { background: #0b1220; color: #e8eef7; }
    .block-container { padding-top: 1.6rem; }
    h1,h2,h3,h4 { color: #f8fafc !important; }
    p,[data-testid="stMarkdownContainer"] { color: #dbe5f2; }
    [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *,
    [data-testid="stWidgetLabel"],[data-testid="stWidgetLabel"] *,label,label * { color:#cbd5e1 !important;opacity:1 !important; }
    [data-testid="stMetric"] { background:#172238;border:1px solid #3a4b67;border-radius:14px;padding:15px; }
    [data-testid="stMetricLabel"],[data-testid="stMetricLabel"] *,[data-testid="stMetricValue"],[data-testid="stMetricValue"] * { color:#f1f5f9 !important;opacity:1 !important; }
    [data-testid="stBaseButton-secondary"] { background:#24334a;border:1px solid #475a77;color:#f8fafc !important; }
    [data-testid="stBaseButton-secondary"] * { color:#f8fafc !important; }
    </style>''', unsafe_allow_html=True)


def api_key(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:
        return None
