"""
Autodidact - AI-Powered Learning Assistant
Main Streamlit application
"""

import streamlit as st
import uuid
from pathlib import Path
from typing import Optional

# Import our modules
from backend.db import init_database, get_project
from utils.config import load_api_key, save_api_key, CONFIG_FILE


# Page configuration
st.set_page_config(
    page_title="Autodidact - AI Learning Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_database()


def init_session_state():
    """Initialize Streamlit session state variables"""
    if "project_id" not in st.session_state:
        st.session_state.project_id = None
    if "current_node" not in st.session_state:
        st.session_state.current_node = None
    if "in_session" not in st.session_state:
        st.session_state.in_session = False
    if "api_key" not in st.session_state:
        st.session_state.api_key = load_api_key()


def show_api_key_modal():
    """Show modal for API key setup"""
    with st.container():
        st.markdown("### 🔑 API Key Setup")
        st.info(
            "Autodidact requires an OpenAI API key to function. "
            "Your key will be stored locally and securely on your machine."
        )
        
        api_key = st.text_input(
            "Enter your OpenAI API key:",
            type="password",
            help="Your API key will be stored in ~/.autodidact/.env.json with secure permissions"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save API Key", type="primary"):
                if api_key and api_key.startswith("sk-"):
                    save_api_key(api_key)
                    st.session_state.api_key = api_key
                    st.success("API key saved successfully!")
                    st.rerun()
                else:
                    st.error("Please enter a valid OpenAI API key (should start with 'sk-')")
        
        with col2:
            st.link_button(
                "Get API Key",
                "https://platform.openai.com/api-keys",
                help="Click to open OpenAI's API key page"
            )


def show_welcome_screen():
    """Show the welcome/landing screen"""
    st.markdown("# 🧠 Autodidact")
    st.markdown("### Your AI-Powered Learning Assistant")
    
    st.markdown("""
    Welcome to Autodidact! I'm here to help you learn any topic through:
    - 🔍 **Deep Research**: I'll investigate your topic and create a comprehensive study plan
    - 📊 **Knowledge Graphs**: Visual representation of concepts and their prerequisites  
    - 👨‍🏫 **AI Tutoring**: Personalized 30-minute learning sessions
    - 📈 **Progress Tracking**: Monitor your mastery of each concept
    """)
    
    st.markdown("---")
    
    # Topic input section
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### What would you like to learn?")
        
        topic = st.text_input(
            "Enter a topic:",
            placeholder="e.g., Foundations of Statistical Learning, Bitcoin consensus mechanisms",
            label_visibility="collapsed"
        )
        
        hours = st.number_input(
            "Target study hours (optional):",
            min_value=1,
            max_value=100,
            value=8,
            help="This helps me plan the depth of coverage"
        )
        
        if st.button("Start Learning Journey", type="primary", use_container_width=True):
            if topic:
                # TODO: Implement topic submission flow
                st.info(f"Starting research on: {topic}")
                # This will trigger the clarifier and deep research in Phase 2
            else:
                st.error("Please enter a topic to learn")
    
    # Example topics
    with st.expander("📚 Example Topics"):
        st.markdown("""
        - Foundations of Statistical Learning
        - React Hooks and State Management
        - Bitcoin and Ethereum Internals
        - Quantum Computing Basics
        - Modern World History: 1900-1950
        - Introduction to Neuroscience
        """)


def show_workspace():
    """Show the main workspace with report and graph"""
    # TODO: Implement workspace view
    st.markdown("## Workspace View")
    st.info("Workspace implementation coming in Phase 3")


def show_tutor_session():
    """Show the tutor session interface"""
    # TODO: Implement tutor session
    st.markdown("## Tutor Session")
    st.info("Tutor session implementation coming in Phase 4")


def main():
    """Main application entry point"""
    # Initialize session state
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.markdown("# 🧠 Autodidact")
        
        if st.session_state.api_key:
            st.success("✅ API Key configured")
            
            if st.button("⚙️ Settings"):
                if st.button("Clear API Key"):
                    CONFIG_FILE.unlink(missing_ok=True)
                    st.session_state.api_key = None
                    st.rerun()
        else:
            st.warning("⚠️ API Key not configured")
        
        st.markdown("---")
        
        # Project selection (if any exist)
        if st.session_state.project_id:
            project = get_project(st.session_state.project_id)
            if project:
                st.markdown(f"**Current Project:**")
                st.markdown(f"📚 {project['topic']}")
                
                if st.button("🏠 New Project"):
                    st.session_state.project_id = None
                    st.session_state.current_node = None
                    st.session_state.in_session = False
                    st.rerun()
    
    # Main content area
    if not st.session_state.api_key:
        show_api_key_modal()
    elif not st.session_state.project_id:
        show_welcome_screen()
    elif st.session_state.in_session:
        show_tutor_session()
    else:
        show_workspace()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "Built with ❤️ for autodidacts everywhere | "
        "<a href='https://github.com/yourusername/autodidact'>GitHub</a>"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main() 