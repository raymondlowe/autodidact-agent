"""
API Key overlay component
Shows when user needs to configure their OpenAI API key
"""

import streamlit as st
from utils.config import load_api_key, save_api_key
from openai import OpenAI

def check_and_show_api_overlay() -> bool:
    """
    Check if API key is configured and show overlay if not.
    Returns True if API key is configured, False otherwise.
    """
    # Check if API key is already in session state
    if "api_key" not in st.session_state:
        st.session_state.api_key = load_api_key()
    
    # If API key exists, return True
    if st.session_state.api_key:
        return True
    
    # Otherwise show overlay
    show_api_key_overlay()
    return False


@st.dialog("🔑 OpenAI API Key Required", width="large")
def show_api_key_overlay():
    """Show modal dialog for API key configuration"""
    st.markdown("""
    ### Welcome to Autodidact!
    
    To use this AI-powered learning assistant, you'll need an OpenAI API key.
    
    **Your API key is stored locally and is never sent anywhere except OpenAI.**
    """)
    
    # API key input
    api_key = st.text_input(
        "Enter your OpenAI API key:",
        type="password",
        placeholder="sk-...",
        help="Your API key will be stored in ~/.autodidact/.env.json with secure permissions"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save API Key", type="primary", use_container_width=True, disabled=not api_key):
            if api_key and api_key.startswith("sk-"):
                with st.spinner("Validating API key..."):
                    try:
                        # Test the API key
                        test_client = OpenAI(api_key=api_key)
                        test_client.models.list()  # Quick test call
                        
                        # If successful, save it
                        save_api_key(api_key)
                        st.session_state.api_key = api_key
                        st.success("✅ API key validated and saved!")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Invalid API key: {str(e)}")
            else:
                st.error("Please enter a valid OpenAI API key (should start with 'sk-')")
    
    with col2:
        st.link_button(
            "🔗 Get API Key",
            "https://platform.openai.com/api-keys",
            help="Click to open OpenAI's API key page",
            use_container_width=True
        )
    
    with col3:
        st.link_button(
            "📖 Pricing Info",
            "https://openai.com/pricing",
            help="View OpenAI's pricing details",
            use_container_width=True
        )
    
    # Info section
    with st.expander("ℹ️ About API Keys", expanded=False):
        st.markdown("""
        **What is an API key?**
        - It's like a password that lets Autodidact use OpenAI's AI models
        - You pay OpenAI directly for usage (typically $0.01-0.05 per learning session)
        
        **Privacy & Security:**
        - Your key is stored locally on your computer
        - It's saved with secure file permissions (readable only by you)
        - We never send your key anywhere except to OpenAI's official API
        
        **Getting Started:**
        1. Click "Get API Key" to create one on OpenAI's website
        2. Copy the key (it starts with 'sk-')
        3. Paste it here and click "Save API Key"
        """)
    
    st.markdown("---")
    st.markdown("💡 **Tip:** The homepage is accessible without an API key if you want to explore first!") 