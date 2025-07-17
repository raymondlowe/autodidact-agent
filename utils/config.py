"""
Configuration module for Autodidact
Handles API key management, paths, and environment settings
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
APP_NAME = "autodidact"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
CONFIG_FILE = CONFIG_DIR / ".env.json"
PROJECTS_DIR = CONFIG_DIR / "projects"

# Provider settings
DEFAULT_PROVIDER = "openai"  # Default to OpenAI for backward compatibility
SUPPORTED_PROVIDERS = ["openai", "openrouter"]

# Model configurations per provider
PROVIDER_MODELS = {
    "openai": {
        "deep_research": "o4-mini-deep-research-2025-06-26",
        "deep_research_better": "o3-deep-research",  # Better model for retry
        "chat": "gpt-4o-mini",
        "chat_better": "gpt-4o",  # Better model for retry
        "base_url": None,  # Use default OpenAI base URL
    },
    "openrouter": {
        "deep_research": "anthropic/claude-3.5-sonnet",  # No deep research equivalent, use best reasoning model
        "deep_research_better": "deepseek/deepseek-r1-0528",  # Better reasoning model for retry
        "chat": "anthropic/claude-3.5-haiku",
        "chat_better": "anthropic/claude-3.5-sonnet",  # Better model for retry
        "base_url": "https://openrouter.ai/api/v1",
    }
}

# Backward compatibility - these will use the default provider
DEEP_RESEARCH_MODEL = PROVIDER_MODELS[DEFAULT_PROVIDER]["deep_research"]
CHAT_MODEL = PROVIDER_MODELS[DEFAULT_PROVIDER]["chat"]
DEEP_RESEARCH_POLL_INTERVAL = 10  # seconds

# Mastery settings
MASTERY_THRESHOLD = 0.7


def ensure_config_directory():
    """Ensure configuration directory exists with proper permissions"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def save_config(config_data: Dict):
    """Save configuration data to config file"""
    ensure_config_directory()
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    # Set file permissions to 600 (rw-------)
    CONFIG_FILE.chmod(0o600)


def save_api_key(api_key: str, provider: str = DEFAULT_PROVIDER):
    """Save API key for a specific provider to config file"""
    # Load existing config or create new one
    config = load_config()
    
    # Set the API key for the provider
    config[f"{provider}_api_key"] = api_key
    
    # If this is the first provider being configured, set it as default
    if "provider" not in config:
        config["provider"] = provider
    
    save_config(config)


def load_config() -> Dict:
    """Load configuration from config file"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    return {}


def load_api_key(provider: str = None) -> Optional[str]:
    """Load API key from config file for a specific provider"""
    config = load_config()
    
    # If no provider specified, use the configured default or system default
    if provider is None:
        provider = config.get("provider", DEFAULT_PROVIDER)
    
    # Try to get the API key for the specified provider
    api_key = config.get(f"{provider}_api_key")
    
    # Fallback to legacy openai_api_key for backward compatibility
    if not api_key and provider == "openai":
        api_key = config.get("openai_api_key")
    
    return api_key


def get_current_provider() -> str:
    """Get the currently configured provider"""
    config = load_config()
    return config.get("provider", DEFAULT_PROVIDER)


def set_current_provider(provider: str):
    """Set the current provider"""
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    
    config = load_config()
    config["provider"] = provider
    save_config(config)


def get_provider_config(provider: str = None) -> Dict:
    """Get model configuration for a specific provider"""
    if provider is None:
        provider = get_current_provider()
    
    if provider not in PROVIDER_MODELS:
        raise ValueError(f"No configuration found for provider: {provider}")
    
    return PROVIDER_MODELS[provider]


def get_better_model_for_task(task: str, provider: str = None) -> str:
    """Get the better model for a specific task for retry scenarios"""
    if provider is None:
        provider = get_current_provider()
    
    config = get_provider_config(provider)
    better_task = f"{task}_better"
    
    if better_task not in config:
        # Fallback to regular model if no better model configured
        return config.get(task, config.get("chat"))
    
    return config[better_task]


def set_better_model_for_task(task: str, model: str, provider: str = None):
    """Set the better model for a specific task"""
    if provider is None:
        provider = get_current_provider()
    
    # Load current config
    config = load_config()
    
    # Store custom better model configuration
    custom_models_key = f"{provider}_custom_better_models"
    if custom_models_key not in config:
        config[custom_models_key] = {}
    
    config[custom_models_key][f"{task}_better"] = model
    save_config(config)


def get_custom_better_models(provider: str = None) -> Dict:
    """Get custom better model configurations"""
    if provider is None:
        provider = get_current_provider()
    
    config = load_config()
    custom_models_key = f"{provider}_custom_better_models"
    return config.get(custom_models_key, {})


def get_project_directory(project_id: str) -> Path:
    """Get the directory path for a specific project"""
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def get_report_path(project_id: str) -> Path:
    """Get the report markdown file path for a project"""
    return get_project_directory(project_id) / "report.md"


def get_graph_path(project_id: str) -> Path:
    """Get the graph JSON file path for a project"""
    return get_project_directory(project_id) / "graph.json"


def get_deep_research_response_path(project_id: str) -> Path:
    """Get the raw deep research response file path"""
    return get_project_directory(project_id) / "deep_research_response.json"


def save_project_files(project_id: str, report_markdown: str, graph_data: Dict, full_result: Dict) -> str:
    """
    Save project files to disk
    
    Args:
        project_id: UUID for the project
        report_markdown: The markdown report content
        graph_data: The graph dictionary
        full_result: Full Deep Research result for backup
    
    Returns:
        Path to the saved report file
    """
    # Create project directory
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Save report
    report_path = project_dir / "report.md"
    report_path.write_text(report_markdown, encoding='utf-8')
    
    # Save graph
    graph_path = project_dir / "graph.json"
    with open(graph_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2)
    
    # Save full result as backup
    backup_path = project_dir / "deep_research_result.json"
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(full_result, f, indent=2)
    
    return str(report_path)


# Initialize configuration on import
ensure_config_directory() 