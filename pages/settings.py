"""
Settings page
Manage API key and other application settings
"""

import streamlit as st
from utils.config import load_api_key, save_api_key, CONFIG_FILE
from openai import OpenAI
from pathlib import Path

# Page header
st.markdown("# ⚙️ Settings")
st.markdown("Manage your Autodidact configuration")

# Back button
if st.button("← Back to Home", key="back_to_home"):
    st.switch_page("pages/home.py")

st.markdown("---")

# API Key section
st.markdown("## 🔑 OpenAI API Key")

# Check current API key status
current_key = st.session_state.get('api_key') or load_api_key()

if current_key:
    # API key is configured
    st.success("✅ API Key is configured")
    
    # Show masked key
    masked_key = current_key[:7] + "..." + current_key[-4:]
    st.code(masked_key)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Update API Key", use_container_width=True):
            st.session_state.show_update_key = True
    
    with col2:
        if st.button("🗑️ Remove API Key", type="secondary", use_container_width=True):
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
            st.session_state.api_key = None
            st.success("API key removed successfully!")
            st.rerun()
    
    # Update key form
    if st.session_state.get('show_update_key', False):
        with st.form("update_api_key"):
            st.markdown("### Update API Key")
            new_key = st.text_input(
                "New API Key:",
                type="password",
                placeholder="sk-...",
                help="Enter your new OpenAI API key"
            )
            
            if st.form_submit_button("Save New Key", type="primary"):
                if new_key and new_key.startswith("sk-"):
                    with st.spinner("Validating API key..."):
                        try:
                            # Test the API key
                            test_client = OpenAI(api_key=new_key)
                            test_client.models.list()
                            
                            # Save it
                            save_api_key(new_key)
                            st.session_state.api_key = new_key
                            st.session_state.show_update_key = False
                            st.success("✅ API key updated successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Invalid API key: {str(e)}")
                else:
                    st.error("Please enter a valid OpenAI API key (should start with 'sk-')")
else:
    # No API key configured
    st.warning("⚠️ No API Key configured")
    st.markdown("""
    To use Autodidact, you need an OpenAI API key. This allows the app to:
    - Generate clarifying questions
    - Conduct deep research on topics
    - Power the AI tutor conversations
    """)
    
    # API key input
    api_key = st.text_input(
        "Enter your OpenAI API key:",
        type="password",
        placeholder="sk-...",
        help="Your API key will be stored in ~/.autodidact/.env.json"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save API Key", type="primary", use_container_width=True, disabled=not api_key):
            if api_key and api_key.startswith("sk-"):
                with st.spinner("Validating API key..."):
                    try:
                        # Test the API key
                        test_client = OpenAI(api_key=api_key)
                        test_client.models.list()
                        
                        # Save it
                        save_api_key(api_key)
                        st.session_state.api_key = api_key
                        st.success("✅ API key saved successfully!")
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
            help="Create an API key on OpenAI's website",
            use_container_width=True
        )
    
    with col3:
        st.link_button(
            "📖 Pricing Info",
            "https://openai.com/pricing",
            help="View OpenAI's pricing details",
            use_container_width=True
        )

# Storage location section
st.markdown("---")
st.markdown("## 📁 Data Storage")

config_dir = Path.home() / ".autodidact"
st.info(f"**Configuration directory:** `{config_dir}`")

if config_dir.exists():
    # Calculate directory size
    total_size = sum(f.stat().st_size for f in config_dir.rglob('*') if f.is_file())
    size_mb = total_size / (1024 * 1024)
    
    st.markdown(f"**Total size:** {size_mb:.1f} MB")
    
    # Show subdirectories
    with st.expander("View storage details"):
        st.markdown("**Directory structure:**")
        st.code(f"""
{config_dir}/
├── .env.json          # API key storage
├── autodidact.db      # Project database
└── projects/          # Project files
    └── [project-id]/
        ├── report.md
        ├── graph.json
        └── deep_research_response.json
        """)

# About section
st.markdown("---")
st.markdown("## ℹ️ About Autodidact")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    ### Version
    **v0.1** - Topic Mode
    
    ### Features
    - 🔍 Deep Research on any topic
    - 📊 Visual knowledge graphs
    - 👨‍🏫 AI-powered tutoring
    - 📈 Progress tracking
    """)

with col2:
    st.markdown("""
    ### Privacy
    - ✅ Runs entirely locally
    - ✅ Data never leaves your computer
    - ✅ API key stored securely
    - ✅ Open source
    """)

# Help section
st.markdown("---")
st.markdown("## 🆘 Need Help?")

with st.expander("Frequently Asked Questions"):
    st.markdown("""
    **Q: How much does it cost to use Autodidact?**
    
    A: Autodidact itself is free. You only pay for OpenAI API usage, which typically costs:
    - $0.01-0.02 for topic clarification
    - $0.50-2.00 for deep research (one-time per topic)
    - $0.02-0.05 per 30-minute tutoring session
    
    **Q: Where is my data stored?**
    
    A: All data is stored locally in `~/.autodidact/` on your computer. Nothing is sent to any servers except your API calls to OpenAI.
    
    **Q: Can I use a different AI provider?**
    
    A: Currently, Autodidact only supports OpenAI's API. Future versions may support other providers.
    
    **Q: How do I report bugs or request features?**
    
    A: Please visit our GitHub repository to open issues or contribute to the project.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; font-size: 0.9rem;'>
    Made with ❤️ for autodidacts everywhere
</div>
""", unsafe_allow_html=True) 