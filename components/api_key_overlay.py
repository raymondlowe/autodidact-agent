"""
API Key overlay component
Shows when user needs to configure their AI provider API key
"""

import streamlit as st
from utils.config import (
    load_api_key, save_api_key, get_current_provider, 
    set_current_provider, SUPPORTED_PROVIDERS
)
from utils.providers import validate_api_key, get_provider_info

def check_and_show_api_overlay() -> bool:
    """
    Check if API key is configured and show overlay if not.
    Returns True if API key is configured, False otherwise.
    """
    # Check if API key is already in session state
    if "api_key" not in st.session_state:
        current_provider = get_current_provider()
        st.session_state.api_key = load_api_key(current_provider)
    
    # If API key exists, return True
    if st.session_state.api_key:
        return True
    
    # Otherwise show overlay
    show_api_key_overlay()
    return False


@st.dialog("🔑 AI Provider Setup", width="large")
def show_api_key_overlay():
    """Show modal dialog for API key configuration"""
    st.markdown("""
    ### Welcome to Autodidact!
    
    To use this AI-powered learning assistant, you'll need an API key from a supported AI provider.
    
    **Your API key is stored locally and is never sent anywhere except your chosen provider.**
    """)
    
    # Provider selection
    current_provider = get_current_provider()
    
    provider_col, key_col = st.columns([1, 2])
    
    with provider_col:
        selected_provider = st.selectbox(
            "Choose AI Provider:",
            options=SUPPORTED_PROVIDERS,
            index=SUPPORTED_PROVIDERS.index(current_provider),
            format_func=lambda x: get_provider_info(x).get("name", x.title()),
            help="Select your preferred AI provider"
        )
        
        # Update provider if changed
        if selected_provider != current_provider:
            set_current_provider(selected_provider)
            st.rerun()
    
    # Get provider info
    provider_info = get_provider_info(selected_provider)
    
    # Show provider info
    with st.expander(f"ℹ️ About {provider_info.get('name', selected_provider)}", expanded=False):
        st.markdown(f"""
        **{provider_info.get('description', '')}**
        
        **Features:**
        - Deep Research: {'✅' if provider_info.get('supports_deep_research') else '❌'}
        - Web Search: {'✅' if provider_info.get('supports_web_search') else '❌'}
        """)
    
    with key_col:
        # API key input
        api_key = st.text_input(
            f"Enter your {provider_info.get('name', selected_provider)} API key:",
            type="password",
            placeholder=provider_info.get('api_key_prefix', 'sk-') + "...",
            help=f"Your API key will be stored in ~/.autodidact/.env.json with secure permissions"
        )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save API Key", type="primary", use_container_width=True, disabled=not api_key):
            prefix = provider_info.get('api_key_prefix', 'sk-')
            if api_key and api_key.startswith(prefix):
                with st.spinner("Validating API key..."):
                    if validate_api_key(api_key, selected_provider):
                        # If successful, save it
                        save_api_key(api_key, selected_provider)
                        st.session_state.api_key = api_key
                        st.success("✅ API key validated and saved!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ Invalid API key for {provider_info.get('name', selected_provider)}")
            else:
                st.error(f"Please enter a valid {provider_info.get('name', selected_provider)} API key (should start with '{prefix}')")
    
    with col2:
        st.link_button(
            "🔗 Get API Key",
            provider_info.get('signup_url', '#'),
            help=f"Click to open {provider_info.get('name', selected_provider)}'s API key page",
            use_container_width=True
        )
    
    with col3:
        st.link_button(
            "📖 Pricing Info",
            provider_info.get('pricing_url', '#'),
            help=f"View {provider_info.get('name', selected_provider)}'s pricing details",
            use_container_width=True
        )
    
    # Info section
    with st.expander("ℹ️ About API Keys", expanded=False):
        st.markdown(f"""
        **What is an API key?**
        - It's like a password that lets Autodidact use {provider_info.get('name', selected_provider)}'s AI models
        - You pay {provider_info.get('name', selected_provider)} directly for usage (typically $0.01-0.05 per learning session)
        
        **Privacy & Security:**
        - Your key is stored locally on your computer
        - It's saved with secure file permissions (readable only by you)
        - We never send your key anywhere except to {provider_info.get('name', selected_provider)}'s official API
        
        **Getting Started:**
        1. Click "Get API Key" to create one on {provider_info.get('name', selected_provider)}'s website
        2. Copy the key (it starts with '{provider_info.get('api_key_prefix', 'sk-')}')
        3. Paste it here and click "Save API Key"
        """)
    
    st.markdown("---")
    st.markdown("💡 **Tip:** The homepage is accessible without an API key if you want to explore first!") 