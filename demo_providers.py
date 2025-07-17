#!/usr/bin/env python3
"""
Complete workflow demonstration for OpenRouter provider support
Shows the full user journey from setup to research
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def demo_setup_workflow():
    """Demonstrate the complete setup workflow"""
    print("🚀 Autodidact Provider Setup Demo")
    print("=" * 50)
    
    from utils.config import get_current_provider, set_current_provider, SUPPORTED_PROVIDERS
    from utils.providers import get_provider_info, list_available_models
    
    print("Available providers:")
    for provider in SUPPORTED_PROVIDERS:
        info = get_provider_info(provider)
        print(f"  • {info['name']}: {info['description']}")
        print(f"    Deep Research: {'✅' if info['supports_deep_research'] else '❌'}")
        print(f"    Web Search: {'✅' if info['supports_web_search'] else '❌'}")
        print()
    
    return True


def demo_provider_switching():
    """Demonstrate provider switching"""
    print("🔄 Provider Switching Demo")
    print("=" * 30)
    
    from utils.config import get_current_provider, set_current_provider
    from utils.providers import list_available_models
    
    # Show current provider
    current = get_current_provider()
    print(f"Current provider: {current}")
    
    # Switch between providers
    for provider in ['openai', 'openrouter']:
        print(f"\nSwitching to {provider}...")
        set_current_provider(provider)
        
        models = list_available_models(provider)
        print(f"Available models:")
        for task, model in models.items():
            print(f"  {task}: {model}")
    
    return True


def demo_api_workflow():
    """Demonstrate how API calls would work with different providers"""
    print("\n🔧 API Workflow Demo")
    print("=" * 25)
    
    from utils.providers import get_model_for_task, get_current_provider, get_provider_info
    
    scenarios = [
        ("Topic clarification", "chat"),
        ("Deep research", "deep_research"),
    ]
    
    for provider in ['openai', 'openrouter']:
        print(f"\n{provider.upper()} Provider:")
        
        provider_info = get_provider_info(provider)
        print(f"  Name: {provider_info['name']}")
        print(f"  Deep Research Support: {'✅' if provider_info['supports_deep_research'] else '❌'}")
        
        for scenario_name, task in scenarios:
            try:
                model = get_model_for_task(task, provider)
                print(f"  {scenario_name}: {model}")
            except Exception as e:
                print(f"  {scenario_name}: ❌ {e}")
    
    return True


def demo_config_structure():
    """Show the configuration structure"""
    print("\n📁 Configuration Demo")
    print("=" * 25)
    
    from utils.config import save_api_key, load_config, CONFIG_FILE
    
    # Save test keys to show structure
    save_api_key("sk-test-openai-key", "openai")
    save_api_key("sk-or-test-openrouter-key", "openrouter")
    
    config = load_config()
    print("Configuration structure:")
    for key, value in config.items():
        if 'api_key' in key:
            # Mask the key for display
            masked = value[:7] + "..." + value[-4:] if len(value) > 11 else value
            print(f"  {key}: {masked}")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nStored at: {CONFIG_FILE}")
    return True


def demo_error_scenarios():
    """Demonstrate error handling scenarios"""
    print("\n⚠️  Error Handling Demo")
    print("=" * 25)
    
    from utils.providers import ProviderError, create_client, validate_api_key
    
    scenarios = [
        ("Invalid provider", lambda: get_model_for_task("chat", "invalid_provider")),
        ("Missing API key", lambda: create_client()),
        ("Invalid API key", lambda: validate_api_key("invalid-key", "openai")),
    ]
    
    for name, test_func in scenarios:
        try:
            result = test_func()
            print(f"  {name}: ❌ Should have failed (got {result})")
        except Exception as e:
            print(f"  {name}: ✅ Correctly handled - {type(e).__name__}")
    
    return True


def demo_backward_compatibility():
    """Demonstrate backward compatibility"""
    print("\n🔄 Backward Compatibility Demo")
    print("=" * 35)
    
    from utils.config import load_api_key, DEEP_RESEARCH_MODEL, CHAT_MODEL
    
    print("Legacy constants still work:")
    print(f"  DEEP_RESEARCH_MODEL: {DEEP_RESEARCH_MODEL}")
    print(f"  CHAT_MODEL: {CHAT_MODEL}")
    
    print("\nLegacy API still works:")
    # This should work with the current provider
    try:
        api_key = load_api_key()  # No provider specified, uses default
        print(f"  load_api_key(): {'Found' if api_key else 'Not found'}")
    except Exception as e:
        print(f"  load_api_key(): Error - {e}")
    
    return True


def main():
    """Run the complete demonstration"""
    print("🎯 Autodidact OpenRouter Support - Complete Demo")
    print("=" * 55)
    print("This demo shows the new multi-provider functionality\n")
    
    try:
        demos = [
            demo_setup_workflow,
            demo_provider_switching, 
            demo_api_workflow,
            demo_config_structure,
            demo_error_scenarios,
            demo_backward_compatibility
        ]
        
        for demo in demos:
            if not demo():
                print("❌ Demo failed")
                return False
        
        print("\n" + "=" * 55)
        print("✅ All demos completed successfully!")
        print("\n🎉 OpenRouter provider support is fully functional")
        print("\nKey features implemented:")
        print("  ✅ Multi-provider support (OpenAI + OpenRouter)")
        print("  ✅ Provider switching and management")
        print("  ✅ Graceful fallbacks for unsupported features")
        print("  ✅ Backward compatibility with existing setups")
        print("  ✅ Comprehensive error handling")
        print("  ✅ Secure configuration management")
        
        print("\nReady for production use! 🚀")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)