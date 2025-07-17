"""
Settings page
Manage API keys and provider configuration
"""

import streamlit as st
from utils.config import (
    load_api_key, save_api_key, CONFIG_FILE, get_current_provider,
    set_current_provider, SUPPORTED_PROVIDERS
)
from utils.providers import validate_api_key, get_provider_info, list_available_models
from pathlib import Path

# Page header
st.markdown("# ⚙️ Settings")
st.markdown("Manage your Autodidact configuration")

# Back button
if st.button("← Back to Home", key="back_to_home"):
    st.switch_page("pages/home.py")

st.markdown("---")

# AI Provider section
st.markdown("## 🤖 AI Provider Configuration")

current_provider = get_current_provider()
provider_info = get_provider_info(current_provider)

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### Current Provider")
    st.info(f"**{provider_info.get('name', current_provider.title())}**")
    st.markdown(provider_info.get('description', ''))
    
    # Provider selection
    new_provider = st.selectbox(
        "Switch Provider:",
        options=SUPPORTED_PROVIDERS,
        index=SUPPORTED_PROVIDERS.index(current_provider),
        format_func=lambda x: get_provider_info(x).get("name", x.title()),
        help="Select your preferred AI provider"
    )
    
    if new_provider != current_provider:
        if st.button("🔄 Switch Provider", type="secondary"):
            set_current_provider(new_provider)
            st.session_state.api_key = None  # Clear current API key
            st.success(f"Switched to {get_provider_info(new_provider).get('name', new_provider)}")
            st.rerun()

with col2:
    st.markdown("### Available Models")
    try:
        models = list_available_models(current_provider)
        for task, model in models.items():
            st.code(f"{task}: {model}")
    except Exception as e:
        st.warning(f"Could not load models: {e}")

st.markdown("---")

# API Key section
st.markdown(f"## 🔑 {provider_info.get('name', current_provider.title())} API Key")

# Check current API key status
current_key = st.session_state.get('api_key') or load_api_key(current_provider)

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
                # Just remove the current provider's key, not the whole file
                from utils.config import load_config, save_config
                config = load_config()
                key_name = f"{current_provider}_api_key"
                if key_name in config:
                    del config[key_name]
                    save_config(config)
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
                placeholder=provider_info.get('api_key_prefix', 'sk-') + "...",
                help=f"Enter your new {provider_info.get('name', current_provider)} API key"
            )
            
            if st.form_submit_button("Save New Key", type="primary"):
                prefix = provider_info.get('api_key_prefix', 'sk-')
                if new_key and new_key.startswith(prefix):
                    with st.spinner("Validating API key..."):
                        if validate_api_key(new_key, current_provider):
                            # Save it
                            save_api_key(new_key, current_provider)
                            st.session_state.api_key = new_key
                            st.session_state.show_update_key = False
                            st.success("✅ API key updated successfully!")
                            st.rerun()
                        else:
                            st.error(f"❌ Invalid API key for {provider_info.get('name', current_provider)}")
                else:
                    st.error(f"Please enter a valid {provider_info.get('name', current_provider)} API key (should start with '{prefix}')")
else:
    # No API key configured
    st.warning("⚠️ No API Key configured")
    st.markdown(f"""
    To use Autodidact with {provider_info.get('name', current_provider)}, you need an API key. This allows the app to:
    - Generate clarifying questions
    - Conduct research on topics  
    - Power the AI tutor conversations
    """)
    
    # API key input
    api_key = st.text_input(
        f"Enter your {provider_info.get('name', current_provider)} API key:",
        type="password",
        placeholder=provider_info.get('api_key_prefix', 'sk-') + "...",
        help="Your API key will be stored in ~/.autodidact/.env.json"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save API Key", type="primary", use_container_width=True, disabled=not api_key):
            prefix = provider_info.get('api_key_prefix', 'sk-')
            if api_key and api_key.startswith(prefix):
                with st.spinner("Validating API key..."):
                    if validate_api_key(api_key, current_provider):
                        # Save it
                        save_api_key(api_key, current_provider)
                        st.session_state.api_key = api_key
                        st.success("✅ API key saved successfully!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ Invalid API key for {provider_info.get('name', current_provider)}")
            else:
                st.error(f"Please enter a valid {provider_info.get('name', current_provider)} API key (should start with '{prefix}')")

# Model Configuration section (only show if API key is configured)
if current_key:
    st.markdown("---")
    st.markdown(f"## 🧠 Model Configuration")
    
    st.markdown("Configure which models to use for normal research and \"retry with better model\" scenarios.")
    
    from utils.providers import get_model_for_task, get_better_model_for_task
    from utils.config import set_better_model_for_task, get_custom_better_models
    
    # Get current models
    try:
        current_deep_research = get_model_for_task("deep_research", current_provider)
        current_better_deep_research = get_better_model_for_task("deep_research", current_provider)
        current_chat = get_model_for_task("chat", current_provider)
        current_better_chat = get_better_model_for_task("chat", current_provider)
    except Exception as e:
        st.error(f"Error loading model configuration: {e}")
        current_deep_research = "Unknown"
        current_better_deep_research = "Unknown"
        current_chat = "Unknown"
        current_better_chat = "Unknown"
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Current Models")
        st.code(f"Deep Research: {current_deep_research}")
        st.code(f"Chat: {current_chat}")
    
    with col2:
        st.markdown("### Better Models (for retry)")
        st.code(f"Deep Research: {current_better_deep_research}")
        st.code(f"Chat: {current_better_chat}")
    
    # Model customization
    with st.expander("🛠️ Customize Better Models"):
        st.markdown("You can override the default \"better models\" used when retrying with a better model.")
        
        # Get custom models
        custom_models = get_custom_better_models(current_provider)
        
        with st.form("model_config"):
            st.markdown("#### Better Model for Deep Research")
            new_better_deep_research = st.text_input(
                "Model ID:",
                value=custom_models.get("deep_research_better", current_better_deep_research),
                help="Enter the model ID for better deep research (e.g., 'o3-deep-research' for OpenAI or 'deepseek/deepseek-r1-0528' for OpenRouter)"
            )
            
            st.markdown("#### Better Model for Chat")
            new_better_chat = st.text_input(
                "Model ID:",
                value=custom_models.get("chat_better", current_better_chat),
                help="Enter the model ID for better chat responses"
            )
            
            col1_form, col2_form = st.columns(2)
            with col1_form:
                if st.form_submit_button("💾 Save Model Configuration", type="primary"):
                    try:
                        if new_better_deep_research != current_better_deep_research:
                            set_better_model_for_task("deep_research", new_better_deep_research, current_provider)
                        if new_better_chat != current_better_chat:
                            set_better_model_for_task("chat", new_better_chat, current_provider)
                        st.success("✅ Model configuration updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving configuration: {e}")
            
            with col2_form:
                if st.form_submit_button("🔄 Reset to Defaults"):
                    try:
                        # Clear custom configurations
                        from utils.config import load_config, save_config
                        config = load_config()
                        custom_models_key = f"{current_provider}_custom_better_models"
                        if custom_models_key in config:
                            del config[custom_models_key]
                            save_config(config)
                        st.success("✅ Reset to default model configuration!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error resetting configuration: {e}")
        
        # Model recommendations based on provider
        st.markdown("#### 💡 Recommended Better Models")
        if current_provider == "openai":
            st.info("""
            **For OpenAI:**
            - Deep Research Better: `o3-deep-research` (higher cost but better reasoning)
            - Chat Better: `gpt-4o` (more capable than gpt-4o-mini)
            """)
        elif current_provider == "openrouter":
            st.info("""
            **For OpenRouter:**
            - Deep Research Better: `deepseek/deepseek-r1-0528` (excellent reasoning), `deepseek/deepseek-r1` (latest), or `anthropic/claude-3.5-sonnet`
            - Chat Better: `anthropic/claude-3.5-sonnet` (more capable than haiku)
            
            **Other good options:** `kimi/k2-large`, `qwen/qwen-2.5-72b-instruct`
            """)
    
    with col2:
        st.link_button(
            "🔗 Get API Key",
            provider_info.get('signup_url', '#'),
            help=f"Create an API key on {provider_info.get('name', current_provider)}'s website",
            use_container_width=True
        )
    
    with col3:
        st.link_button(
            "📖 Pricing Info",
            provider_info.get('pricing_url', '#'),
            help=f"View {provider_info.get('name', current_provider)}'s pricing details",
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
    st.markdown(f"""
    **Q: How much does it cost to use Autodidact?**
    
    A: Autodidact itself is free. You only pay for API usage to your chosen provider:
    - **OpenAI**: $0.01-0.02 for topic clarification, $0.50-2.00 for deep research, $0.02-0.05 per tutoring session
    - **OpenRouter**: Varies by model, typically $0.001-0.05 per request depending on the model chosen
    
    **Q: Where is my data stored?**
    
    A: All data is stored locally in `~/.autodidact/` on your computer. Nothing is sent to any servers except your API calls to your chosen provider.
    
    **Q: What's the difference between providers?**
    
    A: 
    - **OpenAI**: Access to GPT models and deep research capabilities with web search
    - **OpenRouter**: Access to multiple AI models (Claude, Gemini, etc.) but no deep research mode
    
    **Q: Can I switch between providers?**
    
    A: Yes! You can configure API keys for multiple providers and switch between them in Settings.
    
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