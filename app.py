"""
Autodidact - AI-Powered Learning Assistant
Main entry point with Streamlit navigation
"""

import streamlit as st
from components.sidebar import show_sidebar
from components.api_key_overlay import check_and_show_api_overlay
from utils.config import load_api_key

# Page configuration
st.set_page_config(
    page_title="Autodidact - AI Learning Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
from backend.db import init_database
init_database()

# Initialize session state
if "api_key" not in st.session_state:
    st.session_state.api_key = load_api_key()

# Define pages
home = st.Page("pages/home.py", title="Home", url_path="", default=True)
new_project = st.Page("pages/new_project.py", title="New Project", url_path="new")
project = st.Page("pages/project_detail.py", title="Project", url_path="project")
session = st.Page("pages/session_detail.py", title="Session", url_path="session") 
settings = st.Page("pages/settings.py", title="Settings", url_path="settings")

# Create navigation with all pages
# We'll hide Project and Session from the sidebar using CSS
pg = st.navigation([home, new_project, project, session, settings])

# Always hide Project and Session page from sidebar
st.markdown("""
<style>
/* Hide header and auto generated nav from sidebar (this does mean you cannot close the sidebar) */
[data-testid="stSidebarHeader"] {
    display: none !important;
}
[data-testid="stSidebarNav"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

# Show sidebar on all pages
show_sidebar()

# Check API key for protected pages
current_path = st.query_params.get("page", "")
if current_path not in ["", "home", "settings"] and not st.session_state.api_key:
    if not check_and_show_api_overlay():
        st.stop()

# Run selected page
pg.run() 