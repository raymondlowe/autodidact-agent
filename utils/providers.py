"""
Provider abstraction for different AI providers
Supports OpenAI and OpenRouter APIs
"""

from openai import OpenAI
from typing import Dict, Optional
from utils.config import (
    load_api_key, get_current_provider, get_provider_config, 
    SUPPORTED_PROVIDERS
)


class ProviderError(Exception):
    """Base exception for provider-related errors"""
    pass


def create_client(provider: str = None) -> OpenAI:
    """
    Create an API client for the specified provider.
    OpenRouter is compatible with OpenAI's API, so we can use the same client.
    
    Args:
        provider: Provider name ("openai" or "openrouter"). If None, uses current provider.
        
    Returns:
        OpenAI client configured for the specified provider
        
    Raises:
        ProviderError: If provider is not supported or API key is missing
    """
    if provider is None:
        provider = get_current_provider()
    
    if provider not in SUPPORTED_PROVIDERS:
        raise ProviderError(f"Unsupported provider: {provider}. Supported: {SUPPORTED_PROVIDERS}")
    
    # Get API key for the provider
    api_key = load_api_key(provider)
    if not api_key:
        raise ProviderError(f"No API key found for provider: {provider}")
    
    # Get provider configuration
    config = get_provider_config(provider)
    
    # Create client with appropriate base URL
    client_kwargs = {"api_key": api_key}
    if config.get("base_url"):
        client_kwargs["base_url"] = config["base_url"]
    
    return OpenAI(**client_kwargs)


def get_model_for_task(task: str, provider: str = None) -> str:
    """
    Get the appropriate model for a specific task.
    
    Args:
        task: Task type ("deep_research", "chat", etc.)
        provider: Provider name. If None, uses current provider.
        
    Returns:
        Model name for the specified task
        
    Raises:
        ProviderError: If task is not supported for the provider
    """
    if provider is None:
        provider = get_current_provider()
    
    config = get_provider_config(provider)
    
    # Check for custom overrides first
    from utils.config import get_custom_better_models
    custom_models = get_custom_better_models(provider)
    if task in custom_models:
        return custom_models[task]
    
    if task not in config:
        raise ProviderError(f"Task '{task}' not supported for provider '{provider}'")
    
    return config[task]


def get_better_model_for_task(task: str, provider: str = None) -> str:
    """
    Get the better model for a specific task for retry scenarios.
    
    Args:
        task: Task type ("deep_research", "chat", etc.)
        provider: Provider name. If None, uses current provider.
        
    Returns:
        Better model name for the specified task
    """
    if provider is None:
        provider = get_current_provider()
    
    # Check for custom overrides first
    from utils.config import get_custom_better_models
    custom_models = get_custom_better_models(provider)
    better_task = f"{task}_better"
    if better_task in custom_models:
        return custom_models[better_task]
    
    # Use the config-based better model
    from utils.config import get_better_model_for_task as config_get_better
    return config_get_better(task, provider)


def validate_api_key(api_key: str, provider: str) -> bool:
    """
    Validate an API key for a specific provider.
    
    Args:
        api_key: The API key to validate
        provider: Provider name
        
    Returns:
        True if API key is valid, False otherwise
    """
    try:
        config = get_provider_config(provider)
        
        # Create test client
        client_kwargs = {"api_key": api_key}
        if config.get("base_url"):
            client_kwargs["base_url"] = config["base_url"]
        
        test_client = OpenAI(**client_kwargs)
        
        # Test with a simple API call
        test_client.models.list()
        return True
        
    except Exception:
        return False


def get_provider_info(provider: str) -> Dict:
    """
    Get information about a specific provider.
    
    Args:
        provider: Provider name
        
    Returns:
        Dictionary with provider information
    """
    provider_info = {
        "openai": {
            "name": "OpenAI",
            "description": "Official OpenAI API with access to GPT models and deep research",
            "api_key_prefix": "sk-",
            "signup_url": "https://platform.openai.com/api-keys",
            "pricing_url": "https://openai.com/pricing",
            "supports_deep_research": True,
            "supports_web_search": True,
        },
        "openrouter": {
            "name": "OpenRouter",
            "description": "Access to multiple AI models including Claude, Gemini, and more",
            "api_key_prefix": "sk-or-",
            "signup_url": "https://openrouter.ai/keys",
            "pricing_url": "https://openrouter.ai/models",
            "supports_deep_research": False,  # No equivalent to OpenAI's deep research
            "supports_web_search": False,    # Depends on specific model
        }
    }
    
    return provider_info.get(provider, {})


def list_available_models(provider: str = None) -> Dict:
    """
    Get list of available models for a provider.
    
    Args:
        provider: Provider name. If None, uses current provider.
        
    Returns:
        Dictionary of available models by task
    """
    if provider is None:
        provider = get_current_provider()
    
    config = get_provider_config(provider)
    return {task: model for task, model in config.items() if task != "base_url"}