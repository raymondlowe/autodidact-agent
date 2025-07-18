#!/usr/bin/env python3
"""
Test script for OpenRouter provider support
Tests the new provider functionality without requiring real API keys
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_provider_configuration():
    """Test provider configuration and switching"""
    print("Testing provider configuration...")
    
    from utils.config import (
        get_current_provider, set_current_provider, 
        SUPPORTED_PROVIDERS, DEFAULT_PROVIDER
    )
    from utils.providers import get_provider_info, list_available_models
    
    # Test default provider
    assert get_current_provider() == DEFAULT_PROVIDER
    print(f"✅ Default provider: {get_current_provider()}")
    
    # Test provider switching
    for provider in SUPPORTED_PROVIDERS:
        set_current_provider(provider)
        assert get_current_provider() == provider
        
        # Test provider info
        info = get_provider_info(provider)
        assert 'name' in info
        assert 'description' in info
        print(f"✅ {provider}: {info['name']}")
        
        # Test model configuration
        models = list_available_models(provider)
        assert 'chat' in models
        print(f"✅ {provider} models: {models}")
    
    print("✅ Provider configuration tests passed")


def test_api_key_management():
    """Test API key management for multiple providers"""
    print("\nTesting API key management...")
    
    from utils.config import save_api_key, load_api_key, load_config
    from utils.providers import validate_api_key
    
    # Test saving keys for different providers
    test_keys = {
        'openai': 'sk-test-openai-key',
        'openrouter': 'sk-or-test-openrouter-key'
    }
    
    for provider, key in test_keys.items():
        save_api_key(key, provider)
        loaded_key = load_api_key(provider)
        assert loaded_key == key
        print(f"✅ {provider} API key save/load works")
        
        # Test validation (should fail with test keys)
        is_valid = validate_api_key(key, provider)
        assert not is_valid  # Should be False for test keys
        print(f"✅ {provider} API key validation works (correctly rejects test key)")
    
    # Test config structure
    config = load_config()
    assert 'openai_api_key' in config
    assert 'openrouter_api_key' in config
    print("✅ Multi-provider config structure correct")
    
    print("✅ API key management tests passed")


def test_error_handling():
    """Test error handling for missing keys and invalid providers"""
    print("\nTesting error handling...")
    
    from utils.providers import create_client, ProviderError
    from utils.config import set_current_provider
    
    # Test invalid provider
    try:
        from utils.config import SUPPORTED_PROVIDERS
        invalid_provider = 'invalid_provider'
        assert invalid_provider not in SUPPORTED_PROVIDERS
        set_current_provider(invalid_provider)
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✅ Invalid provider correctly rejected")
    
    # Reset to valid provider
    set_current_provider('openai')
    
    # Test client creation with no API key (using fresh config)
    from utils.config import CONFIG_FILE
    if CONFIG_FILE.exists():
        # Backup and clear config temporarily
        import shutil
        backup_path = CONFIG_FILE.with_suffix('.backup')
        shutil.move(CONFIG_FILE, backup_path)
        
        try:
            client = create_client()
            assert False, "Should have raised ProviderError"
        except ProviderError as e:
            print(f"✅ Missing API key correctly handled: {e}")
        
        # Restore config
        shutil.move(backup_path, CONFIG_FILE)
    
    print("✅ Error handling tests passed")


def test_backend_integration():
    """Test backend integration without making actual API calls"""
    print("\nTesting backend integration...")
    
    from backend.jobs import retry_api_call
    from utils.providers import ProviderError
    
    # Test that ProviderError passes through (which is correct behavior)
    def mock_provider_error():
        raise ProviderError("Mock provider error")
    
    try:
        retry_api_call(mock_provider_error)
        assert False, "Should have raised ProviderError"
    except ProviderError:
        print("✅ ProviderError correctly passes through retry mechanism")
    
    # Test successful function call
    def mock_success():
        return "success"
    
    result = retry_api_call(mock_success)
    assert result == "success"
    print("✅ Successful function calls work through retry mechanism")
    
    print("✅ Backend integration tests passed")


def main():
    """Run all tests"""
    print("Running OpenRouter provider support tests...")
    print("=" * 50)
    
    try:
        test_provider_configuration()
        test_api_key_management()
        test_error_handling()
        test_backend_integration()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! OpenRouter provider support is working correctly.")
        print("\nNext steps:")
        print("1. Test with real OpenRouter API key")
        print("2. Verify research workflow with different providers")
        print("3. Test UI provider switching in Streamlit app")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()